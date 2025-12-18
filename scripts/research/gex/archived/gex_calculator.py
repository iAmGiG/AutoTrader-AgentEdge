"""
GEX Calculator: Calculate daily Gamma Exposure metrics from options chains data.

This module aggregates options Greeks data to compute Gamma Exposure (GEX) metrics
for use in volatility regime analysis and trading signal generation.

Daily metrics calculated:
- Total gamma exposure (sum of all gamma, weighted by open interest)
- Call vs Put gamma breakdown
- Net gamma exposure (call gamma - put gamma)
- Zero-gamma strike level (where option market maker is delta-neutral)
- Regime classification (bullish/bearish/neutral/extreme)
- Data quality score
"""

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gex_calculation.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class DailyGEXMetrics:
    """Daily GEX calculation results."""

    symbol: str
    trading_date: str
    total_gamma: float
    call_gamma: float
    put_gamma: float
    net_gamma: float
    zero_gamma_strike: Optional[float]
    regime: str
    data_quality_score: float
    total_contracts: int
    call_contracts: int
    put_contracts: int


class GEXCalculator:
    """Calculate daily Gamma Exposure metrics from options chains."""

    # Regime classification thresholds (in terms of gamma per contract)
    GAMMA_PER_CONTRACT_THRESHOLDS = {
        "extreme_bullish": 0.015,
        "bullish": 0.010,
        "neutral": 0.005,
        "bearish": 0.0,  # negative net gamma
        "extreme_bearish": -0.005,
    }

    def __init__(self, db_path: Path):
        """Initialize calculator with database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_trading_dates(self) -> List[str]:
        """Get all trading dates in the database."""
        self.cursor.execute(
            "SELECT DISTINCT trading_date FROM options_chains ORDER BY trading_date"
        )
        return [row[0] for row in self.cursor.fetchall()]

    def calculate_daily_gex(self, symbol: str, trading_date: str) -> DailyGEXMetrics:
        """Calculate GEX metrics for a single trading date."""
        # Fetch all options for the date
        self.cursor.execute(
            """
            SELECT
                option_type,
                strike,
                gamma,
                delta,
                underlying_price,
                open_interest,
                volume
            FROM options_chains
            WHERE symbol = ? AND trading_date = ?
            ORDER BY strike
        """,
            (symbol, trading_date),
        )

        rows = self.cursor.fetchall()
        if not rows:
            logger.warning(f"No data found for {symbol} on {trading_date}")
            return None

        # Aggregate metrics
        total_gamma = 0.0
        call_gamma = 0.0
        put_gamma = 0.0
        total_oi = 0
        call_oi = 0
        put_oi = 0
        call_count = 0
        put_count = 0
        weighted_zero_gamma_strike = 0.0
        zero_gamma_weight = 0.0

        for row in rows:
            option_type = row["option_type"]
            gamma = row["gamma"]
            oi = row["open_interest"] if row["open_interest"] else 1
            strike = row["strike"]

            # Weight gamma by open interest (proxy for market maker presence)
            weighted_gamma = gamma * oi

            total_gamma += weighted_gamma
            total_oi += oi

            if option_type == "call":
                call_gamma += weighted_gamma
                call_oi += oi
                call_count += 1
            elif option_type == "put":
                put_gamma += weighted_gamma
                put_oi += oi
                put_count += 1

            # Find zero-gamma strike (where gamma = 0 or delta ≈ 0.5)
            delta = row["delta"]
            if 0.4 <= abs(delta) <= 0.6:  # Near delta-neutral
                zero_gamma_weight += oi
                weighted_zero_gamma_strike += strike * oi

        # Normalize by OI (to get unweighted average where possible)
        if total_oi > 0:
            avg_gamma = total_gamma / total_oi
            avg_call_gamma = call_gamma / call_oi if call_oi > 0 else 0
            avg_put_gamma = put_gamma / put_oi if put_oi > 0 else 0
            net_gamma = avg_call_gamma - abs(avg_put_gamma)  # Put gamma is negative
        else:
            avg_gamma = 0
            avg_call_gamma = 0
            avg_put_gamma = 0
            net_gamma = 0

        # Calculate zero-gamma strike
        zero_gamma_strike = None
        if zero_gamma_weight > 0:
            zero_gamma_strike = weighted_zero_gamma_strike / zero_gamma_weight

        # Classify regime
        regime = self._classify_regime(net_gamma, len(rows))

        # Data quality score (0-1, higher is better)
        quality_score = self._calculate_quality_score(len(rows), total_oi, net_gamma)

        return DailyGEXMetrics(
            symbol=symbol,
            trading_date=trading_date,
            total_gamma=round(avg_gamma, 8),
            call_gamma=round(avg_call_gamma, 8),
            put_gamma=round(avg_put_gamma, 8),
            net_gamma=round(net_gamma, 8),
            zero_gamma_strike=zero_gamma_strike,
            regime=regime,
            data_quality_score=round(quality_score, 3),
            total_contracts=len(rows),
            call_contracts=call_count,
            put_contracts=put_count,
        )

    def _classify_regime(self, net_gamma: float, contract_count: int) -> str:
        """Classify volatility regime based on net gamma.

        Schema constraint requires: POSITIVE_GAMMA, NEGATIVE_GAMMA, or NEUTRAL
        """
        if contract_count < 100:
            return "NEUTRAL"

        # Map to schema enum values
        if net_gamma > 0:
            return "POSITIVE_GAMMA"
        elif net_gamma < 0:
            return "NEGATIVE_GAMMA"
        else:
            return "NEUTRAL"

    def _calculate_quality_score(
        self, contract_count: int, total_oi: int, net_gamma: float
    ) -> float:
        """Calculate data quality score (0-1)."""
        score = 1.0

        # Penalize low contract count
        if contract_count < 100:
            score *= 0.5
        elif contract_count < 500:
            score *= 0.75

        # Penalize low open interest
        if total_oi < 1000:
            score *= 0.7
        elif total_oi < 5000:
            score *= 0.85

        # Penalize extreme gamma (possible data errors)
        if abs(net_gamma) > 0.05:
            score *= 0.8

        return min(max(score, 0.0), 1.0)

    def calculate_all_daily_metrics(
        self, symbol: str, batch_size: int = 100
    ) -> List[DailyGEXMetrics]:
        """Calculate GEX metrics for all trading dates."""
        trading_dates = self.get_trading_dates()
        metrics_list = []

        logger.info(f"Calculating GEX for {symbol} ({len(trading_dates)} trading dates)...")

        for i, trading_date in enumerate(trading_dates, 1):
            metrics = self.calculate_daily_gex(symbol, trading_date)
            if metrics:
                metrics_list.append(metrics)

            if i % batch_size == 0:
                logger.info(f"  Processed {i}/{len(trading_dates)} dates")

        logger.info(f"Calculation complete: {len(metrics_list)} days processed")
        return metrics_list

    def save_to_database(self, metrics_list: List[DailyGEXMetrics]) -> bool:
        """Save metrics to options_daily_summary table."""
        try:
            logger.info(f"Inserting {len(metrics_list)} daily summary records...")

            insert_query = """
                INSERT INTO options_daily_summary (
                    symbol, trading_date, total_gex, net_call_gex, net_put_gex,
                    zero_gamma_level, regime, data_quality_score, asset_class
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            for metrics in metrics_list:
                self.cursor.execute(
                    insert_query,
                    (
                        metrics.symbol,
                        metrics.trading_date,
                        metrics.total_gamma,
                        metrics.call_gamma,
                        metrics.put_gamma,
                        metrics.zero_gamma_strike,
                        metrics.regime,
                        metrics.data_quality_score,
                        "equity",  # SPY is equity
                    ),
                )

            self.conn.commit()
            logger.info("Successfully inserted all records")
            return True

        except Exception as e:
            logger.error(f"Failed to insert records: {e}")
            self.conn.rollback()
            return False

    def get_summary_statistics(self) -> Dict:
        """Get summary statistics from options_daily_summary."""
        self.cursor.execute(
            """
            SELECT
                symbol,
                COUNT(*) as days,
                MIN(trading_date) as first_date,
                MAX(trading_date) as last_date,
                ROUND(AVG(total_gex), 8) as avg_total_gex,
                ROUND(AVG(net_call_gex - ABS(net_put_gex)), 8) as avg_net_gex,
                COUNT(CASE WHEN regime = 'bullish' OR regime = 'extreme_bullish'
                      THEN 1 END) as bullish_days,
                COUNT(CASE WHEN regime = 'bearish' OR regime = 'extreme_bearish'
                      THEN 1 END) as bearish_days,
                COUNT(CASE WHEN regime = 'neutral' THEN 1 END) as neutral_days,
                ROUND(AVG(data_quality_score), 3) as avg_quality_score
            FROM options_daily_summary
            GROUP BY symbol
        """
        )

        row = self.cursor.fetchone()
        if not row:
            return None

        return {
            "symbol": row["symbol"],
            "trading_days": row["days"],
            "date_range": f"{row['first_date']} to {row['last_date']}",
            "avg_total_gamma": row["avg_total_gex"],
            "avg_net_gamma": row["avg_net_gex"],
            "bullish_days": row["bullish_days"],
            "bearish_days": row["bearish_days"],
            "neutral_days": row["neutral_days"],
            "regime_distribution": {
                "bullish": f"{100*row['bullish_days']/row['days']:.1f}%",
                "bearish": f"{100*row['bearish_days']/row['days']:.1f}%",
                "neutral": f"{100*row['neutral_days']/row['days']:.1f}%",
            },
            "avg_data_quality": row["avg_quality_score"],
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Calculate daily GEX metrics from options chains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Calculate and save GEX metrics
  python gex_calculator.py --db .cache/gex_research.db --symbol SPY

  # Calculate with summary statistics
  python gex_calculator.py --db .cache/gex_research.db --symbol SPY --summary

  # Save results to JSON file
  python gex_calculator.py --db .cache/gex_research.db --symbol SPY --save-report gex_results.json
        """,
    )

    parser.add_argument("--db", type=Path, default=Path(".cache/gex_research.db"))
    parser.add_argument("--symbol", type=str, default="SPY")
    parser.add_argument("--summary", action="store_true", help="Show summary statistics")
    parser.add_argument("--save-report", type=Path, help="Save metrics report to JSON file")

    args = parser.parse_args()

    # Verify database exists
    if not args.db.exists():
        logger.error(f"Database not found: {args.db}")
        sys.exit(1)

    # Initialize calculator
    calculator = GEXCalculator(args.db)

    try:
        # Calculate daily metrics
        metrics_list = calculator.calculate_all_daily_metrics(args.symbol)

        if not metrics_list:
            logger.error("No metrics calculated")
            sys.exit(1)

        # Save to database
        if calculator.save_to_database(metrics_list):
            logger.info(f"Successfully calculated GEX for {args.symbol}")

            # Show summary if requested
            if args.summary:
                logger.info("\n" + "=" * 70)
                logger.info("GEX CALCULATION SUMMARY")
                logger.info("=" * 70)

                summary = calculator.get_summary_statistics()
                if summary:
                    print(f"\nSymbol: {summary['symbol']}")
                    print(f"Trading days: {summary['trading_days']}")
                    print(f"Date range: {summary['date_range']}")
                    print(f"Avg total gamma: {summary['avg_total_gamma']:.8f}")
                    print(f"Avg net gamma: {summary['avg_net_gamma']:.8f}")
                    print(f"Data quality: {summary['avg_data_quality']:.3f}")
                    print("\nRegime distribution:")
                    for regime, pct in summary["regime_distribution"].items():
                        print(f"  {regime}: {pct}")

            # Save report if requested
            if args.save_report:
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "symbol": args.symbol,
                    "metrics_count": len(metrics_list),
                    "summary": summary if args.summary else None,
                }
                with open(args.save_report, "w") as f:
                    json.dump(report, f, indent=2)
                logger.info(f"Report saved: {args.save_report}")

            sys.exit(0)
        else:
            logger.error("Failed to save metrics to database")
            sys.exit(1)

    finally:
        calculator.close()


if __name__ == "__main__":
    main()
