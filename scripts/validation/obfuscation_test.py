#!/usr/bin/env python3
"""
V4 Obfuscation Validation Test

Tests V4 LLM sentiment agent with and without date/ticker obfuscation
to detect potential data leakage from training knowledge.

If performance drops significantly with obfuscation, it indicates the LLM
may be relying on memorized patterns rather than genuine analysis.
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.validation.obfuscation_validator import ObfuscationValidator


async def run_obfuscation_test(symbol: str = "AAPL",
                               start_date: str = "2024-01-15",
                               end_date: str = "2024-01-19",
                               verbose: bool = True):
    """
    Run obfuscation validation test for V4 sentiment agent.

    Args:
        symbol: Stock symbol to test (default: AAPL)
        start_date: Start date for test period (default: 2024-01-15)
        end_date: End date for test period (default: 2024-01-19)
        verbose: Print detailed results
    """
    if verbose:
        print("🔍 V4 OBFUSCATION VALIDATION TEST")
        print("=" * 50)
        print(f"Symbol: {symbol}")
        print(f"Period: {start_date} to {end_date}")
        print("Testing: V4 LLM performance with/without date-ticker obfuscation")
        print("=" * 50)

    try:
        # Initialize validator
        validator = ObfuscationValidator()

        # Run validation comparison
        if verbose:
            print("🤖 Running V4 sentiment analysis...")
            print("   - Normal mode: Real dates and ticker")
            print("   - Obfuscated mode: [DATE] markers and TICKER_001")

        results = await validator.run_validation_comparison(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if verbose:
            print("\n📊 VALIDATION RESULTS")
            print("-" * 30)

            # Print comparison metrics
            if 'comparison_metrics' in results:
                metrics = results['comparison_metrics']
                print(f"Performance Impact: {metrics.get('performance_impact_pct', 'N/A')}%")
                print(f"Decision Consistency: {metrics.get('decision_consistency_pct', 'N/A')}%")

            # Print scenario results
            if 'normal_scenario' in results:
                normal = results['normal_scenario']['metrics']
                print(f"\nNormal Mode:")
                print(f"  Return: {normal.get('total_return', 'N/A')}%")
                print(f"  Trades: {normal.get('num_trades', 'N/A')}")

            if 'obfuscated_scenario' in results:
                obfuscated = results['obfuscated_scenario']['metrics']
                print(f"\nObfuscated Mode:")
                print(f"  Return: {obfuscated.get('total_return', 'N/A')}%")
                print(f"  Trades: {obfuscated.get('num_trades', 'N/A')}")

            # Interpretation
            print(f"\n💡 INTERPRETATION")
            print("-" * 20)

            if 'comparison_metrics' in results:
                impact = results['comparison_metrics'].get('performance_impact_pct', 0)
                if abs(impact) < 10:
                    print("✅ GOOD: Similar performance suggests genuine analysis")
                elif impact < -20:
                    print("⚠️  WARNING: Significant performance drop may indicate data leakage")
                else:
                    print("🔍 MIXED: Some performance variation detected")
            else:
                print("❌ Could not complete comparison analysis")

        return results

    except Exception as e:
        if verbose:
            print(f"❌ Validation test failed: {e}")
        return {'error': str(e)}


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description='V4 Obfuscation Validation Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validation/obfuscation_test.py                    # Quick test with defaults
  python scripts/validation/obfuscation_test.py --symbol AAPL      # Test AAPL
  python scripts/validation/obfuscation_test.py --start 2024-01-15 --end 2024-01-19
  python scripts/validation/obfuscation_test.py --quiet            # Minimal output
        """
    )

    parser.add_argument('--symbol', default='AAPL',
                        help='Stock symbol to test (default: AAPL)')
    parser.add_argument('--start', default='2024-01-15',
                        help='Start date (default: 2024-01-15)')
    parser.add_argument('--end', default='2024-01-19',
                        help='End date (default: 2024-01-19)')
    parser.add_argument('--quiet', action='store_true',
                        help='Minimal output mode')

    args = parser.parse_args()

    # Run the test
    results = asyncio.run(run_obfuscation_test(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        verbose=not args.quiet
    ))

    # Exit with error code if test failed
    if 'error' in results:
        sys.exit(1)
    else:
        if not args.quiet:
            print("\n✅ Obfuscation validation test completed")


if __name__ == "__main__":
    main()
