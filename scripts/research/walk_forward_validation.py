"""
Walk-Forward Validation Framework (#495)

Address P-Hacking Concerns in Backtesting Methodology.

Key features:
- Anchored walk-forward: train 2016-2020, test 2021-2024
- Multiple testing corrections: Bonferroni, Benjamini-Hochberg
- Causal mechanism documentation framework

Usage:
    python scripts/research/walk_forward_validation.py
"""

import datetime
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml


def now_iso() -> str:
    """Get current timestamp as ISO string."""
    return datetime.datetime.now().isoformat()


# Use main repo database path
GEX_DB_PATH = Path("a:/Projects/AutoGen-Trader/.cache/gex_research.db")


@dataclass
class ValidationResult:
    """Container for walk-forward validation results."""

    strategy_name: str
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_return: float
    out_of_sample_return: float
    in_sample_trades: int
    out_of_sample_trades: int
    degradation_pct: float  # (IS - OOS) / IS
    passes_validation: bool
    p_value: Optional[float] = None
    adjusted_p_value: Optional[float] = None


@dataclass
class CausalMechanism:
    """Document WHO -> WHOM -> WHAT for validated patterns."""

    who: str  # Market participant (e.g., "market makers", "retail", "institutions")
    whom: str  # Target or receiver (e.g., "hedging gamma exposure", "momentum followers")
    what: str  # Observable effect (e.g., "price pinning at max gamma strike")
    evidence: List[str] = field(default_factory=list)
    confidence: str = "low"  # low, medium, high


# =============================================================================
# DATA FETCHING
# =============================================================================


def fetch_price_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily price data from GEX database."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ?
          AND underlying_price IS NOT NULL
          AND trading_date BETWEEN ? AND ?
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
    conn.close()

    if df.empty:
        raise ValueError(f"No data for {symbol} between {start_date} and {end_date}")

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    df = df.rename(columns={"underlying_price": "close"})
    df["returns"] = df["close"].pct_change()

    # Estimate high/low for stochastic calculations
    df["high"] = df["close"] * 1.01
    df["low"] = df["close"] * 0.99

    return df


def fetch_gex_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch GEX metrics from database."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price, total_gex, net_call_gex,
               net_put_gex, zero_gamma_level, max_gamma_strike, regime,
               data_quality_score
        FROM options_daily_summary
        WHERE symbol = ?
          AND trading_date BETWEEN ? AND ?
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
    conn.close()

    if df.empty:
        raise ValueError(f"No GEX data for {symbol}")

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    return df


# =============================================================================
# WALK-FORWARD VALIDATION
# =============================================================================


def walk_forward_split(
    df: pd.DataFrame,
    train_start: str = "2016-01-01",
    train_end: str = "2020-12-31",
    test_start: str = "2021-01-01",
    test_end: str = "2024-12-31",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data into in-sample (training) and out-of-sample (testing) periods.

    Default split:
    - In-sample: 2016-2020 (5 years)
    - Out-of-sample: 2021-2024 (4 years)
    """
    train_mask = (df.index >= train_start) & (df.index <= train_end)
    test_mask = (df.index >= test_start) & (df.index <= test_end)

    return df[train_mask], df[test_mask]


def calculate_backtest_metrics(
    df: pd.DataFrame, signals: pd.Series, initial_capital: float = 10000
) -> Dict[str, float]:
    """
    Run simple backtest and return metrics.

    Returns:
        dict with: total_return, sharpe_ratio, trades, win_rate, max_drawdown
    """
    position = 0
    cash = initial_capital
    holdings = 0.0
    trades = []
    portfolio_values = []
    prices = df["close"]

    for i in range(len(df)):
        price = prices.iloc[i]
        signal = signals.iloc[i] if i < len(signals) else 0

        pv = cash + holdings * price
        portfolio_values.append(pv)

        # Entry signal > 0.5
        if signal > 0.5 and position == 0:
            shares = cash * 0.95 / price
            cash -= shares * price
            holdings = shares
            position = 1
            trades.append({"action": "BUY", "price": price, "idx": i})

        # Exit signal < -0.3
        elif signal < -0.3 and position == 1:
            cash += holdings * price
            if trades:
                trades[-1]["pnl"] = (price - trades[-1]["price"]) / trades[-1]["price"]
            holdings = 0
            position = 0

    # Close final position
    if holdings > 0:
        cash += holdings * prices.iloc[-1]
        portfolio_values[-1] = cash

    pv_series = pd.Series(portfolio_values, index=df.index)
    strategy_returns = pv_series.pct_change().dropna()

    total_return = (pv_series.iloc[-1] - initial_capital) / initial_capital * 100
    sharpe = (
        np.sqrt(252) * strategy_returns.mean() / strategy_returns.std()
        if strategy_returns.std() > 0
        else 0
    )

    # Max drawdown
    rolling_max = pv_series.cummax()
    drawdowns = (pv_series - rolling_max) / rolling_max
    max_drawdown = drawdowns.min() * 100

    # Win rate
    sell_trades = [t for t in trades if "pnl" in t]
    win_rate = (
        sum(1 for t in sell_trades if t["pnl"] > 0) / len(sell_trades) * 100 if sell_trades else 0
    )

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "trades": len([t for t in trades if t["action"] == "BUY"]),
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
    }


def validate_strategy(
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    symbol: str,
    strategy_name: str,
    train_start: str = "2016-01-01",
    train_end: str = "2020-12-31",
    test_start: str = "2021-01-01",
    test_end: str = "2024-12-31",
    min_sharpe_threshold: float = 0.3,
    max_degradation: float = 0.5,
) -> ValidationResult:
    """
    Validate a strategy using walk-forward methodology.

    A strategy passes if:
    1. Out-of-sample Sharpe > min_sharpe_threshold
    2. Degradation (IS - OOS) / IS < max_degradation

    Args:
        strategy_fn: Function that takes DataFrame and returns signals Series
        symbol: Ticker symbol
        strategy_name: Name for logging
        min_sharpe_threshold: Minimum acceptable OOS Sharpe
        max_degradation: Maximum acceptable performance degradation

    Returns:
        ValidationResult with all metrics
    """
    # Fetch full data range
    df = fetch_price_data(symbol, train_start, test_end)

    # Split into train/test
    train_df, test_df = walk_forward_split(df, train_start, train_end, test_start, test_end)

    if len(train_df) < 60 or len(test_df) < 60:
        raise ValueError(
            f"Insufficient data for {symbol}: train={len(train_df)}, test={len(test_df)}"
        )

    # Generate signals for both periods
    train_signals = strategy_fn(train_df)
    test_signals = strategy_fn(test_df)

    # Calculate metrics
    train_metrics = calculate_backtest_metrics(train_df, train_signals)
    test_metrics = calculate_backtest_metrics(test_df, test_signals)

    # Calculate degradation
    if train_metrics["sharpe_ratio"] != 0:
        degradation = (train_metrics["sharpe_ratio"] - test_metrics["sharpe_ratio"]) / abs(
            train_metrics["sharpe_ratio"]
        )
    else:
        degradation = 1.0 if test_metrics["sharpe_ratio"] < 0 else -1.0

    # Validation criteria
    passes = test_metrics["sharpe_ratio"] > min_sharpe_threshold and degradation < max_degradation

    return ValidationResult(
        strategy_name=strategy_name,
        in_sample_sharpe=train_metrics["sharpe_ratio"],
        out_of_sample_sharpe=test_metrics["sharpe_ratio"],
        in_sample_return=train_metrics["total_return"],
        out_of_sample_return=test_metrics["total_return"],
        in_sample_trades=train_metrics["trades"],
        out_of_sample_trades=test_metrics["trades"],
        degradation_pct=degradation * 100,
        passes_validation=passes,
    )


# =============================================================================
# MULTIPLE TESTING CORRECTIONS
# =============================================================================


def bonferroni_correction(
    p_values: List[float], alpha: float = 0.05
) -> Tuple[List[float], List[bool]]:
    """
    Apply Bonferroni correction for multiple hypothesis testing.

    The most conservative correction: adjusted_alpha = alpha / n_tests

    Returns:
        adjusted_p_values, significant_flags
    """
    n_tests = len(p_values)
    adjusted_alpha = alpha / n_tests

    adjusted = [min(p * n_tests, 1.0) for p in p_values]
    significant = [p < adjusted_alpha for p in p_values]

    return adjusted, significant


def benjamini_hochberg_correction(
    p_values: List[float], alpha: float = 0.05
) -> Tuple[List[float], List[bool]]:
    """
    Apply Benjamini-Hochberg FDR correction.

    Less conservative than Bonferroni, controls False Discovery Rate.

    Returns:
        adjusted_p_values, significant_flags
    """
    n_tests = len(p_values)
    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]

    # Calculate adjusted p-values
    adjusted = np.zeros(n_tests)
    for i, idx in enumerate(sorted_indices):
        rank = i + 1
        adjusted[idx] = sorted_p[i] * n_tests / rank

    # Ensure monotonicity (each adjusted p-value >= previous)
    for i in range(n_tests - 2, -1, -1):
        adjusted[sorted_indices[i]] = min(
            adjusted[sorted_indices[i]], adjusted[sorted_indices[i + 1]]
        )

    adjusted = np.minimum(adjusted, 1.0)

    # Determine significance
    significant = [adj_p < alpha for adj_p in adjusted]

    return adjusted.tolist(), significant


def estimate_p_value_from_sharpe(sharpe: float, n_observations: int) -> float:
    """
    Estimate p-value for Sharpe ratio under null hypothesis of zero mean.

    Uses the fact that Sharpe ~ N(0, 1/sqrt(n)) under null.
    """
    from scipy import stats

    se = 1 / np.sqrt(n_observations)
    z_score = sharpe / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
    return p_value


def apply_multiple_testing_corrections(
    results: List[ValidationResult], n_observations: int = 252
) -> List[ValidationResult]:
    """
    Apply Benjamini-Hochberg multiple testing correction to validation results.

    Estimates p-values from OOS Sharpe ratios and applies the BH correction
    to control the False Discovery Rate.
    """
    # Estimate p-values
    p_values = [
        estimate_p_value_from_sharpe(r.out_of_sample_sharpe, n_observations) for r in results
    ]

    # Apply corrections
    bh_adjusted, bh_sig = benjamini_hochberg_correction(p_values)

    # Update results with BH-adjusted p-values (less conservative)
    for i, result in enumerate(results):
        result.p_value = p_values[i]
        result.adjusted_p_value = bh_adjusted[i]
        # Update passes_validation to require statistical significance
        result.passes_validation = result.passes_validation and bh_sig[i]

    return results


# =============================================================================
# CAUSAL MECHANISM DOCUMENTATION
# =============================================================================


# Pre-defined causal mechanisms for common patterns
KNOWN_CAUSAL_MECHANISMS = {
    "gamma_pinning": CausalMechanism(
        who="Market makers (dealers)",
        whom="Options sellers via delta hedging",
        what="Price gravitates toward max gamma strike as dealers hedge",
        evidence=[
            "Academic: Ni, Pearson, Poteshman (2005) - Stock price clustering",
            "Market microstructure: dealer hedging creates supply/demand imbalance",
            "Empirical: OpEx days show higher pinning probability at max OI strikes",
        ],
        confidence="high",
    ),
    "negative_gamma_volatility": CausalMechanism(
        who="Market makers (short gamma exposure)",
        whom="All market participants",
        what="Negative gamma amplifies moves as dealers hedge in same direction",
        evidence=[
            "Dealer hedging feedback loop well documented",
            "Visible in VIX regime correlation with gamma exposure",
            "Academic: Barbon & Buraschi (2021) on dealer gamma hedging",
        ],
        confidence="high",
    ),
    "momentum_effect": CausalMechanism(
        who="Trend-following institutions and CTAs",
        whom="All market participants",
        what="Time-series momentum persists due to slow information diffusion",
        evidence=[
            "Academic: Moskowitz, Ooi, Pedersen (2012) - TSMOM paper",
            "Behavioral: underreaction to news and slow capital allocation",
            "Empirical: 12-month momentum profitable across asset classes",
        ],
        confidence="high",
    ),
    "macd_crossover": CausalMechanism(
        who="Technical traders and algorithmic systems",
        whom="Other technical traders",
        what="MACD crossovers create self-fulfilling prophecy through correlated action",
        evidence=[
            "Widely used indicator across retail and institutional trading",
            "Observable volume spikes on crossover signals",
            "Note: Edge may be arbitraged away in liquid markets",
        ],
        confidence="medium",
    ),
    "rsi_mean_reversion": CausalMechanism(
        who="Mean-reversion traders",
        whom="Momentum traders (counterparty)",
        what="Extreme RSI levels indicate overextension, profit-taking follows",
        evidence=[
            "Bounded nature of price moves in absence of fundamental change",
            "Empirical: extreme RSI (>80, <20) shows reversion tendency",
            "Caution: Can fail in strong trends",
        ],
        confidence="medium",
    ),
}


def document_causal_mechanism(pattern_name: str) -> Optional[CausalMechanism]:
    """Look up known causal mechanism for a pattern."""
    return KNOWN_CAUSAL_MECHANISMS.get(pattern_name)


def format_causal_mechanism(mechanism: CausalMechanism) -> str:
    """Format causal mechanism for reporting."""
    lines = [
        f"WHO: {mechanism.who}",
        f"WHOM: {mechanism.whom}",
        f"WHAT: {mechanism.what}",
        f"Confidence: {mechanism.confidence}",
        "Evidence:",
    ]
    for ev in mechanism.evidence:
        lines.append(f"  - {ev}")
    return "\n".join(lines)


# =============================================================================
# EXAMPLE STRATEGIES FOR VALIDATION
# =============================================================================


def macd_rsi_strategy(df: pd.DataFrame) -> pd.Series:
    """VoterAgent baseline: MACD(13/34/8) + RSI(14)."""
    prices = df["close"]

    # MACD
    ema_fast = prices.ewm(span=13, adjust=False).mean()
    ema_slow = prices.ewm(span=34, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=8, adjust=False).mean()
    histogram = macd_line - signal_line

    # RSI
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))

    signals = pd.Series(0.0, index=df.index)

    for i in range(35, len(df)):
        macd_bull = histogram.iloc[i] > 0
        rsi_ok = 30 < rsi.iloc[i] < 70

        if macd_bull and rsi_ok:
            signals.iloc[i] = 1.0
        elif not macd_bull:
            signals.iloc[i] = -0.5

    return signals


def tsmom_strategy(df: pd.DataFrame, lookback: int = 252) -> pd.Series:
    """Time-Series Momentum: 12-month return signals."""
    prices = df["close"]

    signals = pd.Series(0.0, index=df.index)

    for i in range(lookback, len(df)):
        past_return = (prices.iloc[i] - prices.iloc[i - lookback]) / prices.iloc[i - lookback]

        if past_return > 0:
            signals.iloc[i] = 1.0
        else:
            signals.iloc[i] = -1.0

    return signals


def gex_regime_strategy(df: pd.DataFrame, symbol: str) -> pd.Series:
    """GEX regime-based strategy: long in positive gamma, cautious in negative."""
    # Get GEX data
    try:
        gex_df = fetch_gex_data(
            symbol, df.index[0].strftime("%Y-%m-%d"), df.index[-1].strftime("%Y-%m-%d")
        )
    except ValueError:
        return pd.Series(0.0, index=df.index)

    signals = pd.Series(0.0, index=df.index)

    for date in df.index:
        if date not in gex_df.index:
            continue

        regime = gex_df.loc[date, "regime"]

        if regime == "POSITIVE_GAMMA":
            signals.loc[date] = 0.7  # Moderate long bias
        elif regime == "NEGATIVE_GAMMA":
            signals.loc[date] = -0.5  # Exit/short bias
        else:
            signals.loc[date] = 0.0  # Neutral

    return signals


def _test_strategy_batch(
    strategy_fn: Callable[[pd.DataFrame], pd.Series],
    strategy_prefix: str,
    symbols: List[str],
    description: str,
) -> List[ValidationResult]:
    """Helper to run validation on a batch of symbols for a specific strategy."""
    print("\n" + "-" * 50)
    print(f"Testing: {description}")
    print("-" * 50)

    results = []
    for symbol in symbols:
        try:
            result = validate_strategy(
                strategy_fn=strategy_fn,
                symbol=symbol,
                strategy_name=f"{strategy_prefix}_{symbol}",
            )
            results.append(result)
            status = "PASS" if result.passes_validation else "FAIL"
            print(f"\n{symbol}:")
            print(
                f"  IS Sharpe: {result.in_sample_sharpe:.3f}, OOS Sharpe: {result.out_of_sample_sharpe:.3f}"
            )
            print(f"  Degradation: {result.degradation_pct:.1f}%")
            print(f"  Status: {status}")
        except Exception as e:
            print(f"\n{symbol}: ERROR - {e}")
    return results


# =============================================================================
# MAIN VALIDATION RUN
# =============================================================================


def convert_to_native(obj: Any) -> Any:
    """Convert numpy types for YAML serialization."""
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer, np.floating)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: convert_to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_to_native(i) for i in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return convert_to_native(obj.__dict__)
    return obj


def run_walk_forward_validation():
    """Run walk-forward validation on multiple strategies."""
    print("=" * 70)
    print("WALK-FORWARD VALIDATION FRAMEWORK (#495)")
    print("=" * 70)
    print("\nIn-Sample Period: 2016-01-01 to 2020-12-31 (5 years)")
    print("Out-of-Sample Period: 2021-01-01 to 2024-12-31 (4 years)")
    print("Validation Criteria: OOS Sharpe > 0.3, Degradation < 50%")

    symbols = ["QQQ", "SPY", "IWM"]
    all_results = []

    # Test MACD+RSI strategy
    all_results.extend(
        _test_strategy_batch(
            macd_rsi_strategy, "MACD_RSI", symbols, "MACD+RSI Voting Strategy (VoterAgent Baseline)"
        )
    )

    # Test TSMOM strategy
    all_results.extend(
        _test_strategy_batch(
            tsmom_strategy, "TSMOM", symbols, "Time-Series Momentum (12-month)"
        )
    )

    # Apply multiple testing corrections
    print("\n" + "=" * 70)
    print("MULTIPLE TESTING CORRECTIONS")
    print("=" * 70)

    all_results = apply_multiple_testing_corrections(all_results)

    print("\nAfter Benjamini-Hochberg FDR Correction:")
    for result in all_results:
        status = "SIGNIFICANT" if result.passes_validation else "NOT SIGNIFICANT"
        print(
            f"  {result.strategy_name}: p={result.p_value:.4f}, "
            f"adj_p={result.adjusted_p_value:.4f} [{status}]"
        )

    # Document causal mechanisms
    print("\n" + "=" * 70)
    print("CAUSAL MECHANISM DOCUMENTATION")
    print("=" * 70)

    for pattern in ["macd_crossover", "momentum_effect"]:
        mechanism = document_causal_mechanism(pattern)
        if mechanism:
            print(f"\n{pattern.upper()}:")
            print(format_causal_mechanism(mechanism))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = [r for r in all_results if r.passes_validation]
    print(f"\nStrategies tested: {len(all_results)}")
    print(f"Passed validation: {len(passed)}")
    print(f"Failed validation: {len(all_results) - len(passed)}")

    if passed:
        print("\nValidated strategies:")
        for r in passed:
            print(f"  - {r.strategy_name}: OOS Sharpe = {r.out_of_sample_sharpe:.3f}")

    # Save results
    results_dict = {
        "run_timestamp": now_iso(),
        "issue": "#495",
        "description": "Walk-Forward Validation with Multiple Testing Corrections",
        "methodology": {
            "in_sample": "2016-01-01 to 2020-12-31",
            "out_of_sample": "2021-01-01 to 2024-12-31",
            "validation_criteria": {
                "min_oos_sharpe": 0.3,
                "max_degradation_pct": 50,
            },
            "multiple_testing": "Benjamini-Hochberg FDR correction",
        },
        "results": [convert_to_native(r) for r in all_results],
        "summary": {
            "total_tested": len(all_results),
            "passed": len(passed),
            "pass_rate": len(passed) / len(all_results) * 100 if all_results else 0,
        },
        "causal_mechanisms": {k: convert_to_native(v) for k, v in KNOWN_CAUSAL_MECHANISMS.items()},
    }

    output = Path("docs/08_research/03_strategy_research/walk_forward_results.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(results_dict, f, default_flow_style=False, sort_keys=False)
    print(f"\nResults saved to: {output}")

    return results_dict


def main():
    return run_walk_forward_validation()


if __name__ == "__main__":
    main()
