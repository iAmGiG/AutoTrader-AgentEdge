"""
TSMOM vs GEX Comparative Analysis (#421)

Compare Time-Series Momentum signals with GEX regime indicators to:
1. Measure signal overlap and divergence
2. Identify complementary value
3. Test if GEX regime improves TSMOM performance

References:
- TSMOM: Moskowitz et al. (2012) Time-Series Momentum
- GEX validation: docs/08_research/03_gex_research/gex_regime_validation.md
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.trading.instruments.indicators import calculate_macd, calculate_rsi

DB_PATH = Path(".cache/gex_research.db")


@dataclass
class ComparisonResult:
    """Results from TSMOM vs GEX comparison."""

    symbol: str
    date_range: str
    total_days: int

    # Signal overlap metrics
    tsmom_bullish_days: int
    gex_positive_days: int
    overlap_days: int  # Both bullish/positive
    divergence_days: int  # Opposite signals

    # Performance by regime
    tsmom_return_positive_gex: float
    tsmom_return_negative_gex: float
    tsmom_sharpe_positive_gex: float
    tsmom_sharpe_negative_gex: float

    # Signal quality
    tsmom_win_rate_positive_gex: float
    tsmom_win_rate_negative_gex: float


def get_price_data(conn: sqlite3.Connection, symbol: str) -> pd.DataFrame:
    """Get underlying price data from options_daily_summary."""
    query = """
        SELECT trading_date, underlying_price, regime
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df.set_index("trading_date", inplace=True)
    return df


def calculate_tsmom_signals(prices: pd.Series, lookback: int = 12) -> pd.DataFrame:
    """
    Calculate TSMOM signals using MACD+RSI voting.

    Args:
        prices: Price series
        lookback: Lookback period for momentum (months, but we use daily proxy)

    Returns:
        DataFrame with TSMOM signals and returns
    """
    if len(prices) < 34:
        return pd.DataFrame()

    # Calculate indicators
    macd_data = calculate_macd(prices)
    rsi_data = calculate_rsi(prices)

    # TSMOM signal: MACD bullish AND RSI bullish
    tsmom_signal = macd_data["bullish"] & rsi_data["bullish"]

    # Calculate daily returns
    returns = prices.pct_change()

    # Strategy return: signal * next day return
    strategy_return = tsmom_signal.shift(1) * returns

    df = pd.DataFrame(
        {
            "price": prices,
            "return": returns,
            "tsmom_signal": tsmom_signal,
            "strategy_return": strategy_return,
            "macd_histogram": macd_data["histogram"],
            "rsi": rsi_data["rsi"],
        }
    )

    return df


def calculate_comparison_metrics(tsmom_df: pd.DataFrame, gex_df: pd.DataFrame) -> Dict:
    """Calculate TSMOM vs GEX comparison metrics."""
    # Merge on date
    merged = tsmom_df.join(gex_df[["regime"]], how="inner")

    if len(merged) < 30:
        return None

    # Binary regime flags
    merged["gex_positive"] = merged["regime"] == "POSITIVE_GAMMA"
    merged["gex_negative"] = merged["regime"] == "NEGATIVE_GAMMA"

    # Signal overlap
    tsmom_bullish = merged["tsmom_signal"].sum()
    gex_positive = merged["gex_positive"].sum()
    overlap = (merged["tsmom_signal"] & merged["gex_positive"]).sum()
    divergence = (merged["tsmom_signal"] & merged["gex_negative"]).sum()

    # Performance by GEX regime
    positive_gex_mask = merged["gex_positive"]
    negative_gex_mask = merged["gex_negative"]

    # TSMOM returns in positive gamma
    pos_returns = merged.loc[positive_gex_mask, "strategy_return"].dropna()
    neg_returns = merged.loc[negative_gex_mask, "strategy_return"].dropna()

    # Annualized metrics
    tsmom_return_pos = pos_returns.mean() * 252 if len(pos_returns) > 0 else 0
    tsmom_return_neg = neg_returns.mean() * 252 if len(neg_returns) > 0 else 0

    tsmom_sharpe_pos = (
        (pos_returns.mean() / pos_returns.std()) * np.sqrt(252) if len(pos_returns) > 1 else 0
    )
    tsmom_sharpe_neg = (
        (neg_returns.mean() / neg_returns.std()) * np.sqrt(252) if len(neg_returns) > 1 else 0
    )

    # Win rates
    win_rate_pos = (pos_returns > 0).mean() if len(pos_returns) > 0 else 0
    win_rate_neg = (neg_returns > 0).mean() if len(neg_returns) > 0 else 0

    return {
        "total_days": len(merged),
        "tsmom_bullish_days": int(tsmom_bullish),
        "gex_positive_days": int(gex_positive),
        "overlap_days": int(overlap),
        "divergence_days": int(divergence),
        "tsmom_return_positive_gex": round(tsmom_return_pos * 100, 2),
        "tsmom_return_negative_gex": round(tsmom_return_neg * 100, 2),
        "tsmom_sharpe_positive_gex": round(tsmom_sharpe_pos, 3),
        "tsmom_sharpe_negative_gex": round(tsmom_sharpe_neg, 3),
        "tsmom_win_rate_positive_gex": round(win_rate_pos * 100, 1),
        "tsmom_win_rate_negative_gex": round(win_rate_neg * 100, 1),
    }


def analyze_symbol(conn: sqlite3.Connection, symbol: str) -> Optional[Dict]:
    """Analyze TSMOM vs GEX for a single symbol."""
    # Get GEX data
    gex_df = get_price_data(conn, symbol)
    if len(gex_df) < 50:
        return None

    # Calculate TSMOM signals
    tsmom_df = calculate_tsmom_signals(gex_df["underlying_price"])
    if len(tsmom_df) < 50:
        return None

    # Compare
    metrics = calculate_comparison_metrics(tsmom_df, gex_df)
    if not metrics:
        return None

    metrics["symbol"] = symbol
    metrics["date_range"] = f"{gex_df.index.min().date()} to {gex_df.index.max().date()}"

    return metrics


def generate_report(results: List[Dict]) -> str:
    """Generate markdown report from analysis results."""
    report = []
    report.append("# TSMOM vs GEX Comparative Analysis")
    report.append("")
    report.append("## Executive Summary")
    report.append("")

    # Aggregate metrics
    total_overlap = sum(r["overlap_days"] for r in results)
    total_divergence = sum(r["divergence_days"] for r in results)
    avg_sharpe_pos = np.mean([r["tsmom_sharpe_positive_gex"] for r in results])
    avg_sharpe_neg = np.mean([r["tsmom_sharpe_negative_gex"] for r in results])

    report.append("**Key Findings:**")
    report.append(f"- Signal overlap days: {total_overlap:,}")
    report.append(f"- Signal divergence days: {total_divergence:,}")
    report.append(f"- Avg TSMOM Sharpe (Positive GEX): {avg_sharpe_pos:.3f}")
    report.append(f"- Avg TSMOM Sharpe (Negative GEX): {avg_sharpe_neg:.3f}")
    report.append(
        f"- Sharpe improvement in positive gamma: {((avg_sharpe_pos/avg_sharpe_neg - 1) * 100 if avg_sharpe_neg != 0 else 0):.1f}%"
    )
    report.append("")

    # Detail by symbol
    report.append("## Results by Symbol")
    report.append("")
    report.append(
        "| Symbol | Days | Overlap | Divergence | Sharpe (Pos GEX) | Sharpe (Neg GEX) | Win Rate (Pos) | Win Rate (Neg) |"
    )
    report.append(
        "|--------|------|---------|------------|------------------|------------------|----------------|----------------|"
    )

    for r in sorted(results, key=lambda x: x["total_days"], reverse=True):
        report.append(
            f"| {r['symbol']} | {r['total_days']} | {r['overlap_days']} | {r['divergence_days']} | "
            f"{r['tsmom_sharpe_positive_gex']:.3f} | {r['tsmom_sharpe_negative_gex']:.3f} | "
            f"{r['tsmom_win_rate_positive_gex']:.1f}% | {r['tsmom_win_rate_negative_gex']:.1f}% |"
        )

    report.append("")
    report.append("## Interpretation")
    report.append("")

    if avg_sharpe_pos > avg_sharpe_neg:
        report.append("**TSMOM performs better during positive gamma regimes.**")
        report.append("")
        report.append("This suggests:")
        report.append("1. GEX regime can filter TSMOM signals (only trade in positive gamma)")
        report.append("2. Negative gamma amplifies reversals that hurt momentum strategies")
        report.append("3. GEX provides complementary value as a risk filter")
    else:
        report.append("**TSMOM performs similarly or better during negative gamma regimes.**")
        report.append("")
        report.append("This suggests:")
        report.append("1. Momentum captures large moves in volatile (negative gamma) periods")
        report.append("2. GEX may not add value as a directional filter")
        report.append("3. Consider GEX for position sizing rather than signal filtering")

    return "\n".join(report)


def main():
    """Main entry point."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        # Get symbols with GEX data
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT symbol, COUNT(*) as days
            FROM options_daily_summary
            WHERE underlying_price IS NOT NULL
            GROUP BY symbol
            HAVING days >= 50
            ORDER BY days DESC
        """
        )
        symbols = [(row[0], row[1]) for row in cursor.fetchall()]

        print("=" * 70)
        print("TSMOM vs GEX COMPARATIVE ANALYSIS (#421)")
        print("=" * 70)
        print(f"Symbols with sufficient data: {len(symbols)}")
        print("=" * 70)

        results = []
        for symbol, days in symbols:
            print(f"\nAnalyzing {symbol} ({days} days)...")
            result = analyze_symbol(conn, symbol)
            if result:
                results.append(result)
                print(
                    f"  [OK] Overlap: {result['overlap_days']}, Divergence: {result['divergence_days']}"
                )
                print(
                    f"  [OK] Sharpe (Pos GEX): {result['tsmom_sharpe_positive_gex']:.3f}, (Neg GEX): {result['tsmom_sharpe_negative_gex']:.3f}"
                )

        if not results:
            print("\nNo symbols have sufficient data for analysis.")
            print("Run batch_gex_calculator.py first to populate options_daily_summary.")
            sys.exit(1)

        # Generate report
        report = generate_report(results)

        # Save report
        report_path = Path("docs/08_research/03_gex_research/tsmom_vs_gex_analysis.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)
        print(f"\n[OK] Report saved: {report_path}")

        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Symbols analyzed: {len(results)}")
        avg_sharpe_pos = np.mean([r["tsmom_sharpe_positive_gex"] for r in results])
        avg_sharpe_neg = np.mean([r["tsmom_sharpe_negative_gex"] for r in results])
        print(f"Avg TSMOM Sharpe (Positive GEX): {avg_sharpe_pos:.3f}")
        print(f"Avg TSMOM Sharpe (Negative GEX): {avg_sharpe_neg:.3f}")

        if avg_sharpe_pos > avg_sharpe_neg:
            print(
                f"\n→ TSMOM performs {((avg_sharpe_pos/avg_sharpe_neg - 1) * 100 if avg_sharpe_neg != 0 else 0):.1f}% better in positive gamma regimes"
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
