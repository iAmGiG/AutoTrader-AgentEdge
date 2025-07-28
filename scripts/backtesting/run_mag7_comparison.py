#!/usr/bin/env python3
"""Run comprehensive three-way comparison on MAG7 stocks.

This script generates evidence for the paper by testing Buy & Hold vs Mechanical vs LLM
strategies across MAG7 stocks over multiple time periods.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

import asyncio
import logging
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any
import pandas as pd

from src.agents.coordinator_agent import CoordinatorAgent
from src.utils.parallel_strategy_tester import ParallelStrategyTester
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from config.config_loader import ConfigLoader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MAG7_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

TEST_PERIODS = [
    ("2024-01-01", "2024-06-30", "Recent 6 months"),  # Recent 6 months
    ("2023-01-01", "2023-12-31", "Full 2023"),        # Full 2023
    ("2022-06-01", "2022-12-31", "Bear market")       # Bear market
]

# Output directory
OUTPUT_DIR = Path(".cache/backtests/mag7_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class MAG7ComparisonRunner:
    """Runs three-way strategy comparison for MAG7 stocks."""

    def __init__(self):
        config_loader = ConfigLoader()
        self.config = config_loader.config
        self.coordinator = CoordinatorAgent()
        self.market_tool = MarketDataTool()
        self.results = []
        self.summary_data = []

        # Load model client for LLM strategy
        try:
            from autogen_ext.models import OpenAIChatCompletionClient
            api_key = self.config.get("openai_api_key") or self.config.get("OPENAI_API_KEY")
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o-mini",
                api_key=api_key
            )
            self.llm_available = True
        except (ImportError, AttributeError):
            logger.warning("OpenAI client not available. LLM strategy will use fallback.")
            self.model_client = None
            self.llm_available = False

    async def run_single_comparison(self, symbol: str, start_date: str,
                                    end_date: str, period_name: str) -> Dict[str, Any]:
        """Run three-way comparison for a single stock and period."""

        logger.info(f"Running comparison for {symbol} from {start_date} to {end_date}")

        # Initialize tester
        tester = ParallelStrategyTester(initial_capital=10000)

        # Fetch market data
        prices = self.market_tool.fetch_market_data(symbol, start_date, end_date)

        if prices.empty:
            logger.error(f"No market data for {symbol} in period {start_date} to {end_date}")
            return {
                "symbol": symbol,
                "period": period_name,
                "start_date": start_date,
                "end_date": end_date,
                "error": "No market data available",
                "status": "failed"
            }

        logger.info(f"Processing {len(prices)} trading days for {symbol}")

        # Track progress
        total_days = len(prices)
        processed = 0
        errors = 0

        # Process each trading day
        for date, row in prices.iterrows():
            date_str = date.strftime("%Y-%m-%d")
            price = float(row['Close'])

            try:
                # Get signals from agents
                signals = await self.coordinator.get_signals(date_str, symbol)

                if not signals.get("ok"):
                    errors += 1
                    logger.warning(f"Error getting signals for {symbol} on {date_str}")
                    continue

                # Run three-way comparison
                comparison = tester.run_three_way_comparison(signals, price, date_str)
                processed += 1

                # Log progress every 20 days
                if processed % 20 == 0:
                    logger.info(f"{symbol}: Processed {processed}/{total_days} days")

            except Exception as e:
                errors += 1
                logger.error(f"Error processing {symbol} on {date_str}: {e}")
                continue

        # Get final performance comparison
        performance = tester.get_three_way_comparison()

        # Save detailed results
        run_name = f"{symbol}_{start_date}_{end_date}"
        output_path = tester.save_results(run_name)

        # Compile results
        result = {
            "symbol": symbol,
            "period": period_name,
            "start_date": start_date,
            "end_date": end_date,
            "days_processed": processed,
            "days_with_errors": errors,
            "performance": performance,
            "output_path": str(output_path),
            "status": "completed"
        }

        # Log summary
        logger.info(f"Completed {symbol} for {period_name}:")
        logger.info(f"  Buy & Hold: {performance['buy_hold']['total_return_pct']:.2f}%")
        logger.info(f"  Mechanical: {performance['mechanical']['total_return_pct']:.2f}%")
        logger.info(f"  LLM: {performance['llm']['total_return_pct']:.2f}%")

        return result

    async def run_all_comparisons(self):
        """Run comparisons for all MAG7 stocks across all periods."""

        print(f"\n{'='*80}")
        print("MAG7 THREE-WAY STRATEGY COMPARISON")
        print(f"{'='*80}")
        print(f"Stocks: {', '.join(MAG7_STOCKS)}")
        print(f"Periods: {len(TEST_PERIODS)}")
        print(f"Total tests: {len(MAG7_STOCKS) * len(TEST_PERIODS)}")
        print(f"Output directory: {OUTPUT_DIR}")
        print(f"{'='*80}\n")

        # Track overall progress
        total_tests = len(MAG7_STOCKS) * len(TEST_PERIODS)
        completed = 0

        # Run each stock/period combination
        for symbol in MAG7_STOCKS:
            for start_date, end_date, period_name in TEST_PERIODS:
                print(f"\n[{completed + 1}/{total_tests}] Testing {symbol} - {period_name}")

                try:
                    result = await self.run_single_comparison(
                        symbol, start_date, end_date, period_name
                    )
                    self.results.append(result)

                    # Extract summary data
                    if result["status"] == "completed":
                        perf = result["performance"]
                        self.summary_data.append({
                            "symbol": symbol,
                            "period": period_name,
                            "start_date": start_date,
                            "end_date": end_date,
                            "bh_return": perf["buy_hold"]["total_return_pct"],
                            "mech_return": perf["mechanical"]["total_return_pct"],
                            "llm_return": perf["llm"]["total_return_pct"],
                            "mech_vs_bh": perf["comparisons"]["mechanical_vs_bh"]["outperformance"],
                            "llm_vs_bh": perf["comparisons"]["llm_vs_bh"]["outperformance"],
                            "llm_vs_mech": perf["comparisons"]["llm_vs_mechanical"]["outperformance"],
                            "bh_sharpe": perf["buy_hold"]["sharpe_ratio"],
                            "mech_sharpe": perf["mechanical"]["sharpe_ratio"],
                            "llm_sharpe": perf["llm"]["sharpe_ratio"],
                            "bh_drawdown": perf["buy_hold"]["max_drawdown"],
                            "mech_drawdown": perf["mechanical"]["max_drawdown"],
                            "llm_drawdown": perf["llm"]["max_drawdown"],
                            "bh_trades": perf["buy_hold"]["num_trades"],
                            "mech_trades": perf["mechanical"]["num_trades"],
                            "llm_trades": perf["llm"]["num_trades"]
                        })

                except Exception as e:
                    logger.error(f"Failed to run comparison for {symbol} - {period_name}: {e}")
                    self.results.append({
                        "symbol": symbol,
                        "period": period_name,
                        "start_date": start_date,
                        "end_date": end_date,
                        "error": str(e),
                        "status": "failed"
                    })

                completed += 1

                # Progress update
                print(f"Progress: {completed}/{total_tests} ({completed/total_tests*100:.1f}%)")

        # Save all results
        self.save_all_results()

        # Generate summary report
        self.generate_summary_report()

        print(f"\n{'='*80}")
        print("COMPARISON COMPLETE")
        print(f"{'='*80}")
        print(f"Total tests run: {completed}")
        print(f"Successful: {len([r for r in self.results if r['status'] == 'completed'])}")
        print(f"Failed: {len([r for r in self.results if r['status'] == 'failed'])}")
        print(f"\nResults saved to: {OUTPUT_DIR}")
        print(f"{'='*80}\n")

    def save_all_results(self):
        """Save all results to JSON and CSV files."""

        # Save detailed results as JSON
        with open(OUTPUT_DIR / "all_results.json", "w") as f:
            json.dump(self.results, f, indent=2)

        # Save summary data as CSV
        if self.summary_data:
            df = pd.DataFrame(self.summary_data)
            df.to_csv(OUTPUT_DIR / "summary_data.csv", index=False)

            # Also save as formatted Excel if possible
            try:
                df.to_excel(OUTPUT_DIR / "summary_data.xlsx", index=False)
            except ImportError:
                logger.warning("openpyxl not installed, skipping Excel output")

    def generate_summary_report(self):
        """Generate a markdown summary report."""

        report_path = OUTPUT_DIR / "summary_report.md"

        with open(report_path, "w") as f:
            f.write("# MAG7 Three-Way Strategy Comparison Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Executive Summary
            f.write("## Executive Summary\n\n")

            if self.summary_data:
                # Calculate aggregate statistics
                df = pd.DataFrame(self.summary_data)

                # Average outperformance
                avg_mech_vs_bh = df["mech_vs_bh"].mean()
                avg_llm_vs_bh = df["llm_vs_bh"].mean()
                avg_llm_vs_mech = df["llm_vs_mech"].mean()

                f.write(f"- **Average Mechanical vs Buy & Hold**: {avg_mech_vs_bh:+.2f}%\n")
                f.write(f"- **Average LLM vs Buy & Hold**: {avg_llm_vs_bh:+.2f}%\n")
                f.write(f"- **Average LLM vs Mechanical**: {avg_llm_vs_mech:+.2f}%\n\n")

                # Win rates
                mech_wins_bh = (df["mech_vs_bh"] > 0).sum() / len(df) * 100
                llm_wins_bh = (df["llm_vs_bh"] > 0).sum() / len(df) * 100
                llm_wins_mech = (df["llm_vs_mech"] > 0).sum() / len(df) * 100

                f.write(f"### Win Rates\n\n")
                f.write(f"- Mechanical beats Buy & Hold: {mech_wins_bh:.1f}% of tests\n")
                f.write(f"- LLM beats Buy & Hold: {llm_wins_bh:.1f}% of tests\n")
                f.write(f"- LLM beats Mechanical: {llm_wins_mech:.1f}% of tests\n\n")

            # Detailed Results by Stock
            f.write("## Results by Stock\n\n")

            for symbol in MAG7_STOCKS:
                f.write(f"### {symbol}\n\n")

                stock_results = [r for r in self.results
                                 if r["symbol"] == symbol and r["status"] == "completed"]

                if stock_results:
                    f.write(
                        "| Period | Buy & Hold | Mechanical | LLM | Mech vs B&H | LLM vs B&H | LLM vs Mech |\n")
                    f.write(
                        "|--------|------------|------------|-----|-------------|------------|-------------|\n")

                    for result in stock_results:
                        perf = result["performance"]
                        comp = perf["comparisons"]

                        f.write(f"| {result['period']} | "
                                f"{perf['buy_hold']['total_return_pct']:+.2f}% | "
                                f"{perf['mechanical']['total_return_pct']:+.2f}% | "
                                f"{perf['llm']['total_return_pct']:+.2f}% | "
                                f"{comp['mechanical_vs_bh']['outperformance']:+.2f}% | "
                                f"{comp['llm_vs_bh']['outperformance']:+.2f}% | "
                                f"{comp['llm_vs_mechanical']['outperformance']:+.2f}% |\n")

                    f.write("\n")
                else:
                    f.write("No successful results for this stock.\n\n")

            # Results by Period
            f.write("## Results by Period\n\n")

            for _, _, period_name in TEST_PERIODS:
                f.write(f"### {period_name}\n\n")

                period_results = [r for r in self.results
                                  if r["period"] == period_name and r["status"] == "completed"]

                if period_results:
                    # Calculate period statistics
                    period_df = pd.DataFrame([{
                        "symbol": r["symbol"],
                        "mech_vs_bh": r["performance"]["comparisons"]["mechanical_vs_bh"]["outperformance"],
                        "llm_vs_bh": r["performance"]["comparisons"]["llm_vs_bh"]["outperformance"],
                        "llm_vs_mech": r["performance"]["comparisons"]["llm_vs_mechanical"]["outperformance"]
                    } for r in period_results])

                    f.write(
                        f"- Average Mechanical vs B&H: {period_df['mech_vs_bh'].mean():+.2f}%\n")
                    f.write(f"- Average LLM vs B&H: {period_df['llm_vs_bh'].mean():+.2f}%\n")
                    f.write(
                        f"- Average LLM vs Mechanical: {period_df['llm_vs_mech'].mean():+.2f}%\n\n")

            # Conclusion
            f.write("## Conclusion\n\n")

            if self.summary_data:
                if avg_mech_vs_bh > 0 and avg_llm_vs_bh > 0 and avg_llm_vs_mech > 0:
                    f.write("✅ **Success!** The results demonstrate the progression:\n")
                    f.write("**LLM > Mechanical > Buy & Hold**\n\n")
                    f.write("This proves that:\n")
                    f.write("1. Rule-based strategies add value over passive investing\n")
                    f.write("2. AI-powered strategies add even more value\n")
                else:
                    f.write("⚠️ **Mixed Results**\n\n")
                    f.write("The progression was not consistently demonstrated across all tests.\n")
                    f.write("Further analysis and optimization may be needed.\n")

        logger.info(f"Summary report saved to: {report_path}")


async def main():
    """Main function to run MAG7 comparison."""

    runner = MAG7ComparisonRunner()
    await runner.run_all_comparisons()


if __name__ == "__main__":
    asyncio.run(main())
