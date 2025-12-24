"""
Weekly KAMA MA Crossover Research (#467)

Evaluate weekly KAMA adaptive moving average crossover as alternative to daily
MACD+RSI voting. Tests if weekly timeframe alone filters choppy sideways markets.

Key Research Questions:
1. Does weekly KAMA achieve Sharpe > 0.6 with <10 trades/year?
2. Does weekly timeframe reduce false signals in ranging markets vs daily MACD?
3. Can KAMA adaptivity handle regime changes without explicit filter?

Output: Voter profile defaults for VoterAgent integration.

Usage:
    python scripts/research/weekly_kama_strategy.py
    python scripts/research/weekly_kama_strategy.py --symbol SPY --output results.yaml
"""

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.trading.instruments.indicators import calculate_fold_ma, calculate_kama
from src.utils.date_utils import now_iso


def convert_to_native_types(obj: Any) -> Any:
    """Convert numpy types to native Python types for YAML serialization."""
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating)):
        if np.isnan(obj):
            return None
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_to_native_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_to_native_types(item) for item in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


RESULTS_DB_PATH = Path(".cache/backtest_results.db")
CACHE_DB_PATH = Path(".cache/trading_cache.db")

# Test symbols
DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

# Regime periods for analysis (2020-2025 from GEX database)
REGIME_PERIODS = {
    "bull_2020_2021": ("2020-01-01", "2021-12-31"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "bull_2023_2025": ("2023-01-01", "2025-12-31"),
}


@dataclass
class BacktestResult:
    """Results from a strategy backtest."""

    name: str
    symbol: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    avg_trade_return: float
    trades_per_year: float
    holding_period_avg: float = 0.0
    regime_performance: Dict[str, float] = field(default_factory=dict)


GEX_DB_PATH = Path(".cache/gex_research.db")


def fetch_weekly_data(
    symbol: str, start: str = "2016-01-01", end: str = "2025-12-31"
) -> pd.DataFrame:
    """
    Fetch weekly price data from GEX database or yfinance.

    Priority: GEX database (has 2020-2025 data) -> yfinance (with rate limiting)
    """
    # First try GEX database (has daily prices we can resample)
    if GEX_DB_PATH.exists():
        try:
            df = fetch_from_gex_db(symbol, start, end)
            if len(df) >= 52:  # At least 1 year of weekly data
                print(f"  Using GEX database ({len(df)} weekly bars)")
                return df
        except (ValueError, sqlite3.Error) as e:
            print(f"  GEX DB: {e}")

    # Fall back to Alpha Vantage (adjusted prices)
    return fetch_from_alpha_vantage(symbol, start, end)


def fetch_from_gex_db(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily prices from GEX database and resample to weekly."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ?
        AND trading_date >= ? AND trading_date <= ?
        AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol, start, end))
    conn.close()

    if df.empty or len(df) < 20:
        raise ValueError(f"Insufficient data for {symbol} in GEX DB")

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    df = df.rename(columns={"underlying_price": "close"})

    # Resample daily to weekly (use close for OHLC since we only have close)
    weekly = df.resample("W").agg({"close": "last"}).dropna()

    # Estimate OHLC from close (simplified)
    # WARNING: This creates synthetic High/Low/Open data.
    # Do NOT use this for strategies relying on true High/Low (e.g. ATR, Stochastic).
    weekly["open"] = weekly["close"].shift(1).fillna(weekly["close"])
    weekly["high"] = weekly["close"] * 1.02  # Estimate
    weekly["low"] = weekly["close"] * 0.98
    weekly["volume"] = 0  # Not available

    weekly["returns"] = weekly["close"].pct_change()

    return weekly[["open", "high", "low", "close", "volume", "returns"]]


def fetch_from_alpha_vantage(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fetch weekly data from Alpha Vantage TIME_SERIES_WEEKLY_ADJUSTED."""
    # Load API key from config
    config_path = Path("config/config.json")
    if not config_path.exists():
        raise FileNotFoundError("config/config.json not found - Alpha Vantage API key required")

    with open(config_path) as f:
        config = json.load(f)

    api_key = config.get("ALPHA_VANTAGE_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_KEY not found in config/config.json")

    # Rate limit: Alpha Vantage free tier = 5 calls/min
    time.sleep(12)

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_WEEKLY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",
        "apikey": api_key,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "Weekly Adjusted Time Series" not in data:
        if "Note" in data:
            raise ValueError(f"Alpha Vantage rate limit: {data['Note']}")
        raise ValueError(f"No weekly data for {symbol}: {data.get('Error Message', 'Unknown error')}")

    # Parse weekly data
    rows = []
    for date_str, daily_data in data["Weekly Adjusted Time Series"].items():
        if start <= date_str <= end:
            rows.append({
                "date": date_str,
                "open": float(daily_data["1. open"]),
                "high": float(daily_data["2. high"]),
                "low": float(daily_data["3. low"]),
                "close": float(daily_data["5. adjusted close"]),  # Use adjusted close
                "volume": int(daily_data["6. volume"]),
            })

    if not rows:
        raise ValueError(f"No data in range {start} to {end} for {symbol}")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["returns"] = df["close"].pct_change()

    print(f"  Using Alpha Vantage ({len(df)} weekly bars)")

    return df[["open", "high", "low", "close", "volume", "returns"]]


def fetch_from_cache(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily data from cache and resample to weekly."""
    if not CACHE_DB_PATH.exists():
        raise FileNotFoundError(f"Cache database not found: {CACHE_DB_PATH}")

    conn = sqlite3.connect(CACHE_DB_PATH)
    query = """
        SELECT date, open, high, low, close, volume
        FROM price_data
        WHERE symbol = ? AND date >= ? AND date <= ?
        ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(symbol, start, end))
    conn.close()

    if df.empty:
        raise ValueError(f"No cached data for {symbol}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    # Resample daily to weekly
    weekly = (
        df.resample("W")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    weekly["returns"] = weekly["close"].pct_change()

    return weekly


def generate_kama_signals(
    df: pd.DataFrame,
    lookback: int = 10,
    fast_period: int = 2,
    slow_period: int = 30,
    fold_periods: int = 5,
) -> pd.DataFrame:
    """
    Generate trading signals from Weekly KAMA + Fold MA crossover.

    Signal Logic:
    - BUY: KAMA slope positive, Fold MA slope positive, price > both MAs
    - SELL: KAMA slope negative, Fold MA slope negative, price < both MAs
    - HOLD: Otherwise

    Returns dataframe with signals and indicator values.
    """
    prices = df["close"]

    # Calculate KAMA
    kama_data = calculate_kama(
        prices,
        lookback=lookback,
        fast_period=fast_period,
        slow_period=slow_period,
        timeframe="1w",
    )

    # Calculate Fold MA
    fold_ma = calculate_fold_ma(prices, periods=fold_periods, fold_index=2)

    # Calculate Fold MA slope
    fold_slope = fold_ma.diff(3)

    # Create result dataframe
    result = df.copy()
    result["kama"] = kama_data["kama"]
    result["kama_slope"] = kama_data["slope"]
    result["efficiency_ratio"] = kama_data["efficiency_ratio"]
    result["fold_ma"] = fold_ma
    result["fold_slope"] = fold_slope

    # Generate signals
    signals = pd.Series(0.0, index=df.index)

    for i in range(max(lookback, fold_periods) + 6, len(df)):
        kama_val = kama_data["kama"].iloc[i]
        fold_val = fold_ma.iloc[i]
        price = prices.iloc[i]
        kama_slope_val = kama_data["slope"].iloc[i]
        fold_slope_val = fold_slope.iloc[i]

        # Skip if NaN
        if pd.isna(kama_val) or pd.isna(fold_val) or pd.isna(kama_slope_val):
            continue

        # Bullish: both slopes positive, price above both MAs
        if kama_slope_val > 0 and fold_slope_val > 0 and price > kama_val and price > fold_val:
            signals.iloc[i] = 1.0
        # Bearish: both slopes negative, price below both MAs
        elif kama_slope_val < 0 and fold_slope_val < 0 and price < kama_val and price < fold_val:
            signals.iloc[i] = -1.0
        # Otherwise hold
        else:
            signals.iloc[i] = 0.0

    result["signal"] = signals

    return result


def backtest_strategy(
    df: pd.DataFrame,
    signal_col: str = "signal",
    initial_capital: float = 10000,
) -> BacktestResult:
    """
    Run backtest on strategy signals.

    Uses weekly bars, tracks trades, calculates metrics.
    """
    position = 0  # 0 = flat, 1 = long
    cash = initial_capital
    holdings = 0.0
    trades: List[Dict] = []
    portfolio_values = []
    holding_periods = []
    entry_date = None

    prices = df["close"]
    signals = df[signal_col]

    # Shift signals to avoid lookahead bias (Signal t-1 -> Trade t)
    signals = signals.shift(1).fillna(0)

    for i in range(len(df)):
        price = prices.iloc[i]
        signal = signals.iloc[i]
        date = df.index[i]

        # Track portfolio value
        portfolio_value = cash + holdings * price
        portfolio_values.append(portfolio_value)

        # Trading logic
        if signal > 0.5 and position == 0:
            # Buy
            shares = cash * 0.95 / price  # 95% of cash
            if shares > 0:
                cost = shares * price
                cash -= cost
                holdings = shares
                position = 1
                entry_date = date
                trades.append(
                    {
                        "date": date,
                        "action": "BUY",
                        "price": price,
                        "shares": shares,
                    }
                )

        elif signal < -0.5 and position == 1:
            # Sell
            if holdings > 0:
                revenue = holdings * price
                entry_price = trades[-1]["price"]
                pnl = revenue - (entry_price * holdings)
                pnl_pct = (price - entry_price) / entry_price * 100

                # Calculate holding period
                if entry_date is not None:
                    holding_days = (date - entry_date).days
                    holding_periods.append(holding_days)

                cash += revenue
                trades.append(
                    {
                        "date": date,
                        "action": "SELL",
                        "price": price,
                        "shares": holdings,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    }
                )
                holdings = 0.0
                position = 0
                entry_date = None

    # Close any remaining position
    if holdings > 0:
        final_price = prices.iloc[-1]
        cash += holdings * final_price
        portfolio_values[-1] = cash
        if entry_date is not None:
            holding_days = (df.index[-1] - entry_date).days
            holding_periods.append(holding_days)

    # Calculate metrics
    pv = pd.Series(portfolio_values)
    returns = pv.pct_change().dropna()

    # Total return
    total_return = (pv.iloc[-1] - initial_capital) / initial_capital * 100

    # Sharpe ratio (annualized for weekly: sqrt(52))
    sharpe = np.sqrt(52) * returns.mean() / returns.std() if returns.std() > 0 else 0

    # Max drawdown
    cummax = pv.cummax()
    drawdown = (pv - cummax) / cummax
    max_dd = drawdown.min() * 100

    # Win rate
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    winning_trades = [t for t in sell_trades if t.get("pnl", 0) > 0]
    win_rate = len(winning_trades) / len(sell_trades) * 100 if sell_trades else 0

    # Average trade return
    trade_returns = [t.get("pnl_pct", 0) for t in sell_trades]
    avg_trade = np.mean(trade_returns) if trade_returns else 0

    # Trades per year
    years = len(df) / 52  # Weekly data
    trades_per_year = len(sell_trades) / years if years > 0 else 0

    # Average holding period
    avg_holding = np.mean(holding_periods) if holding_periods else 0

    return BacktestResult(
        name="WEEKLY_KAMA",
        symbol="",
        total_return=total_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        num_trades=len(trades),
        avg_trade_return=avg_trade,
        trades_per_year=trades_per_year,
        holding_period_avg=avg_holding,
    )


def analyze_regime_performance(
    df: pd.DataFrame,
    signal_col: str = "signal",
) -> Dict[str, Dict[str, float]]:
    """Analyze strategy performance across different market regimes."""
    regime_results = {}

    for regime_name, (start, end) in REGIME_PERIODS.items():
        mask = (df.index >= start) & (df.index <= end)
        regime_df = df[mask]

        if len(regime_df) < 10:
            continue

        result = backtest_strategy(regime_df, signal_col)
        regime_results[regime_name] = {
            "sharpe": result.sharpe_ratio,
            "return": result.total_return,
            "max_dd": result.max_drawdown,
            "trades": result.num_trades,
        }

    return regime_results


def generate_weekly_macd_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate weekly MACD+RSI voting signals for comparison.

    This is the VoterAgent baseline adapted for weekly timeframe.
    Uses continuous position holding, not just crossover triggers.
    """
    from src.trading.instruments.indicators import calculate_macd, calculate_rsi

    prices = df["close"]

    # Calculate indicators
    macd_data = calculate_macd(prices, fast=13, slow=34, signal=8)
    rsi_data = calculate_rsi(prices, period=14)

    signals = pd.Series(0.0, index=df.index)

    for i in range(34, len(df)):
        # MACD: bullish if histogram > 0, bearish if < 0
        macd_bullish = macd_data["histogram"].iloc[i] > 0

        # RSI: bullish if not overbought, bearish if overbought
        rsi_val = rsi_data["rsi"].iloc[i]
        rsi_bullish = rsi_val < 70  # Not overbought
        rsi_bearish = rsi_val > 70

        # Voting with continuous signal
        if macd_bullish and rsi_bullish:
            signals.iloc[i] = 1.0  # Strong bullish
        elif not macd_bullish and rsi_bearish:
            signals.iloc[i] = -1.0  # Strong bearish
        elif macd_bullish:
            signals.iloc[i] = 0.5  # Weak bullish
        elif not macd_bullish:
            signals.iloc[i] = -0.5  # Weak bearish

    result = df.copy()
    result["signal"] = signals

    return result


def generate_voter_profile(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate voter profile defaults from backtest results.

    This creates a ready-to-use configuration for VoterAgent integration.
    """
    # Extract best performing parameters
    symbol_results = results.get("symbol_results", {})

    # Find symbols where KAMA outperforms MACD
    kama_wins = []
    macd_wins = []

    for symbol, data in symbol_results.items():
        kama_sharpe = data.get("kama", {}).get("sharpe_ratio", 0)
        macd_sharpe = data.get("macd_weekly", {}).get("sharpe_ratio", 0)

        if kama_sharpe > macd_sharpe:
            kama_wins.append(symbol)
        else:
            macd_wins.append(symbol)

    # Calculate averages
    kama_sharpes = [
        symbol_results[s]["kama"]["sharpe_ratio"]
        for s in symbol_results
        if "kama" in symbol_results[s]
    ]

    avg_kama_sharpe = np.mean(kama_sharpes) if kama_sharpes else 0

    # Regime performance summary (2020-2025 periods)
    regime_perf = results.get("regime_analysis", {})
    trending_sharpe = np.mean(
        [
            regime_perf.get("bull_2020_2021", {}).get("sharpe", 0),
            regime_perf.get("bull_2023_2025", {}).get("sharpe", 0),
        ]
    )

    # Bear/choppy is 2022
    choppy_sharpe = regime_perf.get("bear_2022", {}).get("sharpe", 0)

    # Generate profile
    profile = {
        "name": "weekly_kama_crossover",
        "description": "Weekly KAMA MA Crossover - Trend Filter for Low-Frequency Trading",
        "issue": "#467",
        "validated": True,
        "validation_date": now_iso(),
        # Core parameters
        "parameters": {
            "timeframe": "1w",
            "kama_lookback": 10,
            "kama_fast": 2,
            "kama_slow": 30,
            "fold_periods": 5,
            "fold_index": 2,
        },
        # Performance metrics
        "performance": {
            "avg_sharpe": round(avg_kama_sharpe, 3),
            "trending_sharpe": round(trending_sharpe, 3),
            "choppy_sharpe": round(choppy_sharpe, 3),
            "trades_per_year": results.get("avg_trades_per_year", 0),
        },
        # Use cases
        "recommended_for": kama_wins,
        "not_recommended_for": macd_wins,
        # Integration guidance
        "integration": {
            "use_as": "trend_filter",
            "combine_with": "daily_macd_rsi",
            "check_frequency": "weekly",
            "signal_interpretation": {
                "bullish": "KAMA slope > 0 AND Fold MA slope > 0 AND price > both",
                "bearish": "KAMA slope < 0 AND Fold MA slope < 0 AND price < both",
                "neutral": "Mixed signals - defer to daily indicators",
            },
        },
        # Hybrid strategy recommendation
        "hybrid_strategy": {
            "enabled": choppy_sharpe < trending_sharpe * 0.5,
            "logic": "Use weekly KAMA as trend filter, only trade daily signals when weekly confirms",
            "expected_improvement": "Reduce false signals in choppy markets",
        },
    }

    return profile


def run_full_analysis(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run full Weekly KAMA analysis across all symbols."""
    if symbols is None:
        symbols = DEFAULT_SYMBOLS

    print("=" * 70)
    print("WEEKLY KAMA MA CROSSOVER RESEARCH (#467)")
    print("=" * 70)
    print()

    all_results = {
        "run_timestamp": now_iso(),
        "issue": "#467",
        "description": "Weekly KAMA vs Daily MACD+RSI Voting",
        "timeframe": "2016-2024 (weekly bars)",
        "symbol_results": {},
        "summary": {},
    }

    kama_sharpes = []
    macd_sharpes = []
    all_trades_per_year = []

    for symbol in symbols:
        print(f"\n{'=' * 50}")
        print(f"Processing: {symbol}")
        print("=" * 50)

        try:
            # Fetch weekly data
            df = fetch_weekly_data(symbol)
            print(f"Data: {len(df)} weekly bars ({df.index[0].date()} to {df.index[-1].date()})")

            # Generate KAMA signals
            kama_df = generate_kama_signals(df)
            kama_result = backtest_strategy(kama_df, "signal")
            kama_result.symbol = symbol

            # Generate weekly MACD signals for comparison
            macd_df = generate_weekly_macd_signals(df)
            macd_result = backtest_strategy(macd_df, "signal")
            macd_result.symbol = symbol

            # Regime analysis
            regime_perf = analyze_regime_performance(kama_df, "signal")

            # Print results
            print("\nKAMA Strategy:")
            print(f"  Sharpe: {kama_result.sharpe_ratio:.3f}")
            print(f"  Return: {kama_result.total_return:.1f}%")
            print(f"  Max DD: {kama_result.max_drawdown:.1f}%")
            print(f"  Trades/yr: {kama_result.trades_per_year:.1f}")
            print(f"  Win Rate: {kama_result.win_rate:.1f}%")

            print("\nWeekly MACD+RSI (baseline):")
            print(f"  Sharpe: {macd_result.sharpe_ratio:.3f}")
            print(f"  Return: {macd_result.total_return:.1f}%")

            # Comparison
            sharpe_diff = kama_result.sharpe_ratio - macd_result.sharpe_ratio
            print(f"\nKAMA vs MACD: {sharpe_diff:+.3f} Sharpe")

            # Store results
            all_results["symbol_results"][symbol] = {
                "kama": {
                    "sharpe_ratio": kama_result.sharpe_ratio,
                    "total_return": kama_result.total_return,
                    "max_drawdown": kama_result.max_drawdown,
                    "win_rate": kama_result.win_rate,
                    "trades_per_year": kama_result.trades_per_year,
                    "avg_holding_days": kama_result.holding_period_avg,
                },
                "macd_weekly": {
                    "sharpe_ratio": macd_result.sharpe_ratio,
                    "total_return": macd_result.total_return,
                    "max_drawdown": macd_result.max_drawdown,
                },
                "regime_performance": regime_perf,
                "kama_outperforms": sharpe_diff > 0,
            }

            kama_sharpes.append(kama_result.sharpe_ratio)
            macd_sharpes.append(macd_result.sharpe_ratio)
            all_trades_per_year.append(kama_result.trades_per_year)

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    # Summary statistics
    if kama_sharpes:
        kama_wins = sum(1 for k, m in zip(kama_sharpes, macd_sharpes) if k > m)
        all_results["summary"] = {
            "avg_kama_sharpe": np.mean(kama_sharpes),
            "avg_macd_sharpe": np.mean(macd_sharpes),
            "kama_win_rate": kama_wins / len(kama_sharpes) * 100,
            "avg_trades_per_year": np.mean(all_trades_per_year),
            "symbols_tested": len(kama_sharpes),
        }
        # Aggregate regime analysis
        all_regimes = {}
        for symbol_data in all_results["symbol_results"].values():
            for regime, perf in symbol_data.get("regime_performance", {}).items():
                if regime not in all_regimes:
                    all_regimes[regime] = {"sharpes": [], "returns": [], "dds": []}
                all_regimes[regime]["sharpes"].append(perf.get("sharpe", 0))
                all_regimes[regime]["returns"].append(perf.get("return", 0))
                all_regimes[regime]["dds"].append(perf.get("max_dd", 0))

        all_results["regime_analysis"] = {
            regime: {
                "sharpe": np.mean(data["sharpes"]),
                "return": np.mean(data["returns"]),
                "max_dd": np.mean(data["dds"]),
            }
            for regime, data in all_regimes.items()
        }

        all_results["avg_trades_per_year"] = np.mean(all_trades_per_year)

    # Generate voter profile
    all_results["voter_profile"] = generate_voter_profile(all_results)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if "summary" in all_results and "avg_kama_sharpe" in all_results["summary"]:
        s = all_results["summary"]
        print(f"\nAvg KAMA Sharpe: {s['avg_kama_sharpe']:.3f}")
        print(f"Avg MACD Sharpe: {s['avg_macd_sharpe']:.3f}")
        print(f"KAMA Win Rate: {s['kama_win_rate']:.0f}%")
        print(f"Avg Trades/Year: {s['avg_trades_per_year']:.1f}")
    else:
        print("\nNo successful backtests to summarize")

    print("\nRegime Performance (KAMA):")
    for regime, perf in all_results.get("regime_analysis", {}).items():
        print(f"  {regime}: Sharpe={perf['sharpe']:.3f}, Return={perf['return']:.1f}%")

    print("\n" + "-" * 70)
    print("VOTER PROFILE GENERATED")
    print("-" * 70)
    profile = all_results["voter_profile"]
    print(f"Name: {profile['name']}")
    print(f"Avg Sharpe: {profile['performance']['avg_sharpe']}")
    print(f"Trending Sharpe: {profile['performance']['trending_sharpe']}")
    print(f"Choppy Sharpe: {profile['performance']['choppy_sharpe']}")
    print(f"Recommended for: {', '.join(profile['recommended_for'])}")
    print(f"Hybrid enabled: {profile['hybrid_strategy']['enabled']}")

    return convert_to_native_types(all_results)


def save_results(results: Dict[str, Any], output_path: Optional[str] = None) -> None:
    """Save results to YAML file."""
    if output_path is None:
        output_path = "docs/08_research/03_strategy_research/weekly_kama_results.yaml"

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False)

    print(f"\nResults saved to: {output_file}")


def save_voter_profile(profile: Dict[str, Any]) -> None:
    """Save voter profile to config defaults."""
    output_path = Path("config_defaults/voter_profiles/weekly_kama.yaml")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False)

    print(f"Voter profile saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Weekly KAMA MA Crossover Research")
    parser.add_argument("--symbol", "-s", help="Single symbol to test")
    parser.add_argument("--symbols", nargs="+", help="List of symbols to test")
    parser.add_argument("--output", "-o", help="Output YAML file path")
    parser.add_argument("--save-profile", action="store_true", help="Save voter profile to config")

    args = parser.parse_args()

    # Determine symbols
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    else:
        symbols = DEFAULT_SYMBOLS

    try:
        results = run_full_analysis(symbols)

        # Save results
        save_results(results, args.output)

        # Save voter profile if requested
        if args.save_profile:
            save_voter_profile(results["voter_profile"])

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
