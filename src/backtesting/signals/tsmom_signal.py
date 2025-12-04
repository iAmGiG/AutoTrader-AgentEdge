"""
Time Series Momentum (TSMOM) Signal Generator

Implements the academic time series momentum strategy from:
Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012).
"Time series momentum." Journal of Financial Economics, 104(2), 228-250.

Key Findings from Paper:
- Sharpe Ratio: 0.48-0.79 (varies by asset class and lookback period)
- Lookback: 12-month momentum most common
- Holding: 1-month rebalancing
- Works across 58 futures, stocks, currencies, commodities

Implementation for AutoGen-Trader:
- Lookback: 12 months (252 trading days)
- Signal: BUY if 12m return > threshold, SELL if < -threshold, HOLD otherwise
- Threshold: 10% absolute return (configurable)
- Position sizing: Full position (1.0) for strong signals
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd


class TSMOMSignalGenerator:
    """
    Time Series Momentum signal generator.

    Compatible with BacktestEngine.run() signature.

    Usage:
        ```python
        from src.backtesting import BacktestEngine
        from src.backtesting.signals import TSMOMSignalGenerator

        tsmom = TSMOMSignalGenerator(lookback_days=252, threshold=0.10)
        engine = BacktestEngine()
        results = engine.run(
            signal_generator=tsmom.generate_signal,
            symbol="AAPL",
            start_date="2016-01-01",
            end_date="2024-12-31"
        )
        ```

    Attributes:
        lookback_days: Number of trading days to lookback (default: 252 = 12 months)
        threshold: Minimum return threshold to trigger signal (default: 0.10 = 10%)
    """

    def __init__(self, lookback_days: int = 252, threshold: float = 0.10):
        """
        Initialize TSMOM signal generator.

        Args:
            lookback_days: Lookback period in trading days (default: 252 = 12 months)
            threshold: Return threshold to trigger BUY/SELL (default: 0.10 = 10%)
        """
        self.lookback_days = lookback_days
        self.threshold = threshold

    def calculate_momentum(self, prices: pd.Series) -> float:
        """
        Calculate momentum as trailing return over lookback period.

        Momentum = (Price_today / Price_lookback) - 1

        Args:
            prices: Pandas Series of closing prices

        Returns:
            Momentum as decimal return (0.15 = 15% gain)
        """
        if len(prices) < self.lookback_days + 1:
            return 0.0  # Insufficient data

        current_price = prices.iloc[-1]
        lookback_price = prices.iloc[-(self.lookback_days + 1)]

        if lookback_price == 0 or pd.isna(lookback_price) or pd.isna(current_price):
            return 0.0

        momentum = (current_price / lookback_price) - 1
        return momentum

    def generate_signal(self, _symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate TSMOM trading signal.

        Args:
            _symbol: Ticker symbol (currently unused - momentum is symbol-agnostic)
            data: DataFrame with 'close' column and datetime index

        Returns:
            Decision dictionary with keys:
            - action: "BUY", "SELL", or "HOLD"
            - position_size: 0.0 to 1.0 (fraction of capital)
            - confidence: 0.0 to 1.0
            - reasoning: Explanation string
        """
        if "close" not in data.columns:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "Missing 'close' price data",
            }

        prices = data["close"]

        # Calculate 12-month momentum
        momentum = self.calculate_momentum(prices)

        # Insufficient data check
        if len(prices) < self.lookback_days + 1:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": f"Insufficient data: {len(prices)} days < {self.lookback_days + 1} required",
            }

        # Generate signal based on momentum threshold
        if momentum > self.threshold:
            # Strong positive momentum -> BUY
            confidence = min(0.9, 0.5 + (momentum - self.threshold) * 2)  # Scale confidence
            return {
                "action": "BUY",
                "position_size": 1.0,
                "confidence": confidence,
                "reasoning": f"TSMOM BUY: 12m momentum = {momentum:.2%} > {self.threshold:.2%} threshold",
            }

        elif momentum < -self.threshold:
            # Strong negative momentum -> SELL
            confidence = min(0.9, 0.5 + abs(momentum + self.threshold) * 2)
            return {
                "action": "SELL",
                "position_size": 1.0,
                "confidence": confidence,
                "reasoning": f"TSMOM SELL: 12m momentum = {momentum:.2%} < -{self.threshold:.2%} threshold",
            }

        else:
            # Weak momentum -> HOLD
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.3,
                "reasoning": f"TSMOM HOLD: 12m momentum = {momentum:.2%} within ±{self.threshold:.2%} threshold",
            }


def run_tsmom_validation():
    """
    Validation test: Run TSMOM on AAPL 2016-2024 and check Sharpe > 0.6.

    This tests the TSMOM signal generator and validates the research approach.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from src.backtesting.backtest_engine import BacktestEngine

    print("\n" + "=" * 70)
    print("TSMOM VALIDATION TEST")
    print("=" * 70)
    print("\nStrategy: Time Series Momentum (TSMOM)")
    print("Parameters:")
    print("  Lookback: 252 days (12 months)")
    print("  Threshold: 10% absolute return")
    print("  Position: Full (1.0) for strong signals")
    print("\nExpected Results (from academic research):")
    print("  Sharpe Ratio: 0.48-0.79 (varies by asset/period)")
    print("  Our Target: Sharpe > 0.6 for validation")
    print("\nRunning backtest on AAPL 2016-2024...\n")

    # Initialize TSMOM signal generator
    tsmom = TSMOMSignalGenerator(lookback_days=252, threshold=0.10)

    # Initialize BacktestEngine
    engine = BacktestEngine(initial_capital=10000, commission_per_share=0.005)

    # Note: This will fail if SQLite cache doesn't have data
    # User will need to run populate_historical_cache.py first
    try:
        results = engine.run(
            signal_generator=tsmom.generate_signal,
            symbol="AAPL",
            start_date="2016-01-01",
            end_date="2024-12-31",
        )

        print(results)

        # Validation check
        print("\n" + "=" * 70)
        print("VALIDATION RESULT")
        print("=" * 70)

        target_sharpe = 0.6
        actual_sharpe = results.sharpe_ratio

        if actual_sharpe >= target_sharpe:
            print("\n✅ VALIDATION PASSED")
            print(f"   Target Sharpe: >= {target_sharpe:.3f}")
            print(f"   Actual Sharpe:    {actual_sharpe:.3f}")
            print(f"   Difference:    +{actual_sharpe - target_sharpe:.3f}")
            print("\n   TSMOM signal generator is VALIDATED.")
            print("   Ready for Issue #420 (TSMOM research).")
            return True
        else:
            print("\n⚠️ VALIDATION MARGINAL")
            print(f"   Target Sharpe: >= {target_sharpe:.3f}")
            print(f"   Actual Sharpe:    {actual_sharpe:.3f}")
            print(f"   Difference:    {actual_sharpe - target_sharpe:.3f}")
            print("\n   TSMOM shows promise but below target.")
            print("   May need parameter tuning (lookback/threshold).")
            return False

    except ValueError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        print("\nTo run TSMOM validation:")
        print(
            "  1. Populate cache: python scripts/populate_historical_cache.py --symbols AAPL --type stock --start 2016-01-01"
        )
        print("  2. Re-run: python -m src.backtesting.signals.tsmom_signal")
        return False


if __name__ == "__main__":
    # Run validation test when executed directly
    success = run_tsmom_validation()
    sys.exit(0 if success else 1)
