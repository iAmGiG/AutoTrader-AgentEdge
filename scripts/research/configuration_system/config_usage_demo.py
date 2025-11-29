#!/usr/bin/env python3
"""
Configuration Usage Demo
Shows the benefits of having a flexible configuration system.
"""

import sys
from pathlib import Path

# Add project root to path (scripts/research/configuration_system -> project root is 3 levels up)
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config_defaults.trading_config import TradingConfig


def get_config():
    """Get trading configuration instance."""
    return TradingConfig()


def demo_basic_usage():
    """Show basic configuration usage."""
    print("=" * 60)
    print("BASIC CONFIGURATION USAGE")
    print("=" * 60)

    # Get configuration
    config = get_config()

    # Get MACD parameters
    macd = config.get_macd_config()
    print("\nMACD Configuration:")
    print(f"  Fast: {macd.fast}")
    print(f"  Slow: {macd.slow}")
    print(f"  Signal: {macd.signal}")

    # Get RSI parameters
    rsi = config.get_rsi_config()
    print("\nRSI Configuration:")
    print(f"  Period: {rsi.period}")
    print(f"  Oversold: {rsi.oversold}")
    print(f"  Overbought: {rsi.overbought}")

    # Get exit strategy
    exit_cfg = config.get_exit_config("balanced")
    print("\nBalanced Exit Strategy:")
    print(f"  Take Profit: {exit_cfg.take_profit:.1%}")
    print(f"  Stop Loss: {exit_cfg.stop_loss:.1%}")
    print(f"  Expected Value (50% WR): {exit_cfg.expected_value_50wr:.1%}")
    print(f"  Breakeven Win Rate: {exit_cfg.breakeven_win_rate:.1%}")


def demo_strategy_comparison():
    """Compare different exit strategies."""
    print("\n" + "=" * 60)
    print("EXIT STRATEGY COMPARISON")
    print("=" * 60)

    config = get_config()
    strategies = config.get_all_exit_strategies()

    print(f"\n{'Strategy':<15} {'TP':<8} {'SL':<8} {'EV@50%':<10} {'Breakeven'}")
    print("-" * 60)

    for name, strategy in strategies.items():
        print(
            f"{name:<15} {strategy.take_profit:>6.1%}  {strategy.stop_loss:>6.1%}  "
            f"{strategy.expected_value_50wr:>8.2%}  {strategy.breakeven_win_rate:>8.1%}"
        )


def demo_benefits():
    """Demonstrate the benefits of configuration system."""
    print("\n" + "=" * 60)
    print("BENEFITS OF CONFIGURATION SYSTEM")
    print("=" * 60)

    print(
        """
1. EASY PARAMETER TUNING:
   - Change parameters in JSON without touching code
   - Test different MACD periods (e.g., 12/26/9 vs 13/34/8)
   - Adjust exit strategies based on market conditions

2. A/B TESTING:
   - Run parallel backtests with different configs
   - Compare performance systematically
   - Find optimal parameters for different assets

3. ENVIRONMENT-SPECIFIC SETTINGS:
   - config_dev.json for aggressive testing
   - config_prod.json for conservative live trading
   - config_test.json for unit tests

4. AUDIT TRAIL:
   - Version control config changes
   - Track what parameters were used when
   - Reproduce historical results

5. CONSISTENCY:
   - All components use same parameters
   - No hardcoded values scattered in code
   - Single source of truth

Example Usage in Code:
```python
from config.trading_config import get_config

config = get_config()
macd = config.get_macd_config()

# Use in your strategy
fast_ema = prices.ewm(span=macd.fast).mean()
slow_ema = prices.ewm(span=macd.slow).mean()
```
    """
    )


def demo_dynamic_adjustment():
    """Show how to dynamically adjust configuration."""
    print("\n" + "=" * 60)
    print("DYNAMIC CONFIGURATION ADJUSTMENT")
    print("=" * 60)

    config = get_config()

    print("\nScenario: Market becomes more volatile")
    print("Action: Switch from balanced to conservative exits")

    # Get current strategy
    current = config.get_exit_config("balanced")
    print("\nCurrent (Balanced):")
    print(f"  TP: {current.take_profit:.1%}, SL: {current.stop_loss:.1%}")

    # Switch to conservative
    conservative = config.get_exit_config("conservative")
    print("\nSwitched to Conservative:")
    print(f"  TP: {conservative.take_profit:.1%}, SL: {conservative.stop_loss:.1%}")
    print("  Note: Wider stop loss for volatile conditions")

    print("\n✅ No code changes needed - just specify different strategy!")


def main():
    """Run all demonstrations."""
    demo_basic_usage()
    demo_strategy_comparison()
    demo_benefits()
    demo_dynamic_adjustment()

    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print(
        """
YES, there are significant benefits to using a configuration system:

1. Flexibility without code changes
2. Easy optimization and testing
3. Clear documentation of parameters
4. Reproducible results
5. Production-ready parameter management

Start with the 'balanced' exit strategy (8% TP / 5% SL)
as it has the best expected value at realistic win rates.
"""
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
