"""
Statistical Significance Analysis for GEX vs Technicals (#394)

Performs statistical tests to validate that GEX outperformance is significant.
Tests: t-test for Sharpe ratios, Wilcoxon for return distributions.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

RESULTS_DB = Path(".cache/backtest_results.db")


def load_latest_results():
    """Load latest results from database."""
    if not RESULTS_DB.exists():
        raise FileNotFoundError(f"Results database not found: {RESULTS_DB}")

    conn = sqlite3.connect(RESULTS_DB)
    conn.row_factory = sqlite3.Row

    # Get latest run per symbol
    cursor = conn.execute(
        """
        SELECT * FROM gex_vs_technicals
        WHERE run_timestamp IN (
            SELECT MAX(run_timestamp)
            FROM gex_vs_technicals
            GROUP BY symbol
        )
        ORDER BY symbol
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def test_sharpe_significance(results):
    """Test if GEX Sharpe ratios are significantly better than technicals."""
    tech_sharpes = [r["tech_sharpe"] for r in results]
    gex_sharpes = [r["gex_sharpe"] for r in results]

    # Paired t-test (same symbols tested with both strategies)
    t_stat, p_value = stats.ttest_rel(gex_sharpes, tech_sharpes)

    # Effect size (Cohen's d for paired samples)
    differences = np.array(gex_sharpes) - np.array(tech_sharpes)
    cohen_d = np.mean(differences) / np.std(differences, ddof=1)

    return {
        "t_statistic": t_stat,
        "p_value": p_value,
        "cohen_d": cohen_d,
        "tech_sharpes": tech_sharpes,
        "gex_sharpes": gex_sharpes,
        "improvements": differences.tolist(),
    }


def test_return_significance(results):
    """Test if GEX returns are significantly better."""
    tech_returns = [r["tech_return"] for r in results]
    gex_returns = [r["gex_return"] for r in results]

    # Wilcoxon signed-rank test (non-parametric, doesn't assume normality)
    w_stat, p_value = stats.wilcoxon(gex_returns, tech_returns)

    return {
        "w_statistic": w_stat,
        "p_value": p_value,
        "tech_returns": tech_returns,
        "gex_returns": gex_returns,
    }


def analyze_win_consistency(results):
    """Analyze how consistently GEX wins across symbols."""
    gex_wins = sum(1 for r in results if r["gex_sharpe"] > r["tech_sharpe"])
    total = len(results)

    # Binomial test: is win rate significantly > 50%?
    result = stats.binomtest(gex_wins, total, 0.5, alternative="greater")

    return {
        "gex_wins": gex_wins,
        "total_tests": total,
        "win_rate": gex_wins / total,
        "binomial_p_value": result.pvalue,
    }


def categorize_by_asset_type(results):
    """Break down results by ETF type."""
    categories = {
        "Index ETFs": [],
        "3x Bull": [],
        "3x Bear": [],
    }

    type_map = {
        "SPY": "Index ETFs",
        "QQQ": "Index ETFs",
        "IWM": "Index ETFs",
        "TQQQ": "3x Bull",
        "SOXL": "3x Bull",
        "SQQQ": "3x Bear",
    }

    for r in results:
        cat = type_map.get(r["symbol"], "Other")
        if cat in categories:
            categories[cat].append(
                {
                    "symbol": r["symbol"],
                    "improvement": r["gex_sharpe"] - r["tech_sharpe"],
                }
            )

    summary = {}
    for cat, items in categories.items():
        if items:
            improvements = [x["improvement"] for x in items]
            summary[cat] = {
                "count": len(items),
                "avg_improvement": np.mean(improvements),
                "symbols": [x["symbol"] for x in items],
            }

    return summary


def print_report(results):
    """Print comprehensive statistical report."""
    print("=" * 70)
    print("STATISTICAL SIGNIFICANCE ANALYSIS - GEX vs TECHNICALS")
    print("=" * 70)
    print()

    # Basic stats
    print(f"Number of symbols tested: {len(results)}")
    print("Test period: 2024-2025 (out-of-sample)")
    print()

    # Sharpe ratio significance
    sharpe_test = test_sharpe_significance(results)
    print("SHARPE RATIO COMPARISON")
    print("-" * 40)
    print(f"Mean Tech Sharpe: {np.mean(sharpe_test['tech_sharpes']):.3f}")
    print(f"Mean GEX Sharpe:  {np.mean(sharpe_test['gex_sharpes']):.3f}")
    print(f"Mean Improvement: {np.mean(sharpe_test['improvements']):+.3f}")
    print()
    print("Paired t-test:")
    print(f"  t-statistic: {sharpe_test['t_statistic']:.3f}")
    print(f"  p-value: {sharpe_test['p_value']:.4f}")
    print(f"  Cohen's d: {sharpe_test['cohen_d']:.3f}")
    print()

    if sharpe_test["p_value"] < 0.05:
        print("[+] SIGNIFICANT at p < 0.05")
    else:
        print("[-] NOT significant at p < 0.05")

    if abs(sharpe_test["cohen_d"]) > 0.8:
        print("[+] LARGE effect size (|d| > 0.8)")
    elif abs(sharpe_test["cohen_d"]) > 0.5:
        print("[+] MEDIUM effect size (|d| > 0.5)")
    else:
        print("[!] SMALL effect size (|d| < 0.5)")
    print()

    # Win consistency
    win_analysis = analyze_win_consistency(results)
    print("WIN RATE ANALYSIS")
    print("-" * 40)
    print(f"GEX wins: {win_analysis['gex_wins']}/{win_analysis['total_tests']}")
    print(f"Win rate: {win_analysis['win_rate']*100:.1f}%")
    print(f"Binomial test p-value: {win_analysis['binomial_p_value']:.4f}")
    print()

    if win_analysis["binomial_p_value"] < 0.05:
        print("[+] Win rate significantly > 50% (p < 0.05)")
    else:
        print("[!] Win rate not significantly > 50%")
    print()

    # Category breakdown
    categories = categorize_by_asset_type(results)
    print("PERFORMANCE BY ASSET TYPE")
    print("-" * 40)
    for cat, data in categories.items():
        print(f"{cat}:")
        print(f"  Count: {data['count']}")
        print(f"  Avg Improvement: {data['avg_improvement']:+.3f} Sharpe")
        print(f"  Symbols: {', '.join(data['symbols'])}")
        print()

    # Individual results
    print("INDIVIDUAL SYMBOL IMPROVEMENTS")
    print("-" * 40)
    for r in sorted(results, key=lambda x: x["gex_sharpe"] - x["tech_sharpe"], reverse=True):
        improvement = r["gex_sharpe"] - r["tech_sharpe"]
        marker = "[+]" if improvement > 0 else "[-]"
        print(f"{marker} {r['symbol']:6s}: {improvement:+.3f} Sharpe")
    print()

    # Conclusion
    print("=" * 70)
    print("STATISTICAL CONCLUSION")
    print("=" * 70)
    print()

    if sharpe_test["p_value"] < 0.05 and win_analysis["binomial_p_value"] < 0.05:
        print("[+] GEX SIGNIFICANTLY OUTPERFORMS TECHNICALS")
        print()
        print("Evidence:")
        print(f"  - Sharpe improvement significant (p={sharpe_test['p_value']:.4f})")
        print(f"  - Win rate significant (p={win_analysis['binomial_p_value']:.4f})")
        print(f"  - Effect size: {sharpe_test['cohen_d']:.3f} (Cohen's d)")
        print()
        print("Recommendation: GEX is statistically superior for directional ETFs")
    elif sharpe_test["p_value"] < 0.05:
        print("[!] GEX SHOWS IMPROVEMENT BUT MIXED EVIDENCE")
        print()
        print("Evidence:")
        print(f"  - Sharpe improvement significant (p={sharpe_test['p_value']:.4f})")
        print(f"  - But win rate not significant (p={win_analysis['binomial_p_value']:.4f})")
        print()
        print("Recommendation: Consider asset-specific implementation")
    else:
        print("[-] INSUFFICIENT EVIDENCE FOR GEX SUPERIORITY")
        print()
        print("Recommendation: Require more testing or different market conditions")


def main():
    """Main entry point."""
    try:
        results = load_latest_results()
        print_report(results)
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run gex_vs_technicals.py first to generate results")
        return 1


if __name__ == "__main__":
    sys.exit(main())
