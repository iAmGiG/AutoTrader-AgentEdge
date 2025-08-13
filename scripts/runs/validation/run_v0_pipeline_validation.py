"""
Comprehensive V0 Test - Full Pipeline with Real Tools
Tests the complete orchestrator with actual API calls and tools
This validates the foundation before implementing V1-V4 sentiment agents
"""

import sys
import os
import pandas as pd
import json

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.agents.strategy_agent import StrategyAgent


def run_v0_comprehensive_test():
    """Run comprehensive V0 test with real tools and API calls."""
    print("=" * 70)
    print("V0 COMPREHENSIVE TEST - Full Pipeline with Real Tools")
    print("=" * 70)
    print("This test validates:")
    print("- TechAgent: Real market data fetching + MACD calculation")
    print("- V0 SentimentAgent: Fixed 1.0 baseline")
    print("- StrategyAgent: Orchestration + trading decisions")
    print("- Complete multi-agent communication pipeline")
    print("=" * 70)

    # Test parameters
    symbol = "AAPL"
    test_dates = [
        "2024-01-15",
        "2024-01-16",
        "2024-01-17"
    ]
    base_price = 150.0

    try:
        # Initialize V0 strategy
        print(f"\n1. Initializing StrategyAgent with V0 sentiment...")
        strategy = StrategyAgent(sentiment_version="V0")
        print(f"   ✓ Strategy: {strategy.name}")
        print(f"   ✓ Version: {strategy.sentiment_version}")
        print(f"   ✓ Tech Agent: {type(strategy.tech_agent).__name__}")
        print(f"   ✓ Sentiment Agent: {type(strategy.sentiment_agent).__name__}")

        # Test individual agents first
        print(f"\n2. Testing individual agent responses...")

        # Test TechAgent
        print(f"   Testing TechAgent...")
        tech_message = f"Get MACD data for {symbol} on {test_dates[0]}"
        print(f"   -> Sending: {tech_message}")

        try:
            tech_response = strategy.tech_agent.generate_reply(tech_message)
            tech_data = json.loads(tech_response)
            print(f"   ✓ TechAgent response: {tech_data}")
        except Exception as e:
            print(f"   ✗ TechAgent failed: {str(e)}")
            return False

        # Test SentimentAgent
        print(f"   Testing V0 SentimentAgent...")
        sentiment_message = f"Get sentiment for {symbol} on {test_dates[0]}"
        print(f"   -> Sending: {sentiment_message}")

        try:
            sentiment_response = strategy.sentiment_agent.generate_reply(sentiment_message)
            sentiment_data = json.loads(sentiment_response)
            print(f"   ✓ SentimentAgent response: {sentiment_data}")
        except Exception as e:
            print(f"   ✗ SentimentAgent failed: {str(e)}")
            return False

        # Run orchestrated backtest
        print(f"\n3. Running orchestrated backtest...")
        print(f"   Symbol: {symbol}")
        print(f"   Dates: {test_dates}")
        print(f"   Strategy: V0 (fixed sentiment = 1.0)")

        print(
            f"\n   {'Date':<12} {'Price':<8} {'Action':<6} {'MACD_T':<8} {'MACD_Y':<8} {'Sentiment':<9} {'Reason'}")
        print("   " + "-" * 85)

        decisions = []
        for i, date in enumerate(test_dates):
            price = base_price + i * 2  # Slight price increase

            print(f"   Processing {date} at ${price:.2f}...")

            try:
                # This is the key test - orchestrated decision making
                decision = strategy.decide_trade(symbol, date, price)
                decisions.append(decision)

                # Format output
                action = decision.get('action', 'N/A')
                macd_t = decision.get('macd_today')
                macd_y = decision.get('macd_yest')
                sentiment = decision.get('sentiment', 0)
                reason = decision.get('reason', 'N/A')[:25]

                macd_t_str = f"{macd_t:.3f}" if macd_t is not None else "None"
                macd_y_str = f"{macd_y:.3f}" if macd_y is not None else "None"

                print(
                    f"   {date:<12} ${price:<7.2f} {action:<6} {macd_t_str:<8} {macd_y_str:<8} {sentiment:<9.1f} {reason}")

            except Exception as e:
                print(f"   {date:<12} ${price:<7.2f} ERROR  Failed: {str(e)}")
                decisions.append({'action': 'ERROR', 'error': str(e)})

        # Analyze results
        print(f"\n4. Results Analysis...")

        # Decision summary
        actions = [d.get('action', 'ERROR') for d in decisions]
        action_counts = pd.Series(actions).value_counts()
        print(f"   Decision Summary:")
        for action, count in action_counts.items():
            print(f"   - {action}: {count}")

        # Strategy state
        print(f"   \n   Final Strategy State:")
        print(f"   - Position: {strategy.position} (0=flat, 1=long)")
        print(f"   - Entry Price: {strategy.entry_price}")
        print(f"   - Entry Date: {strategy.entry_date}")
        print(f"   - Completed Trades: {len(strategy.trades)}")

        # Trade log
        if strategy.trade_log:
            print(f"   \n   Trade Log ({len(strategy.trade_log)} entries):")
            for i, log_entry in enumerate(strategy.trade_log[-3:]):  # Show last 3
                print(f"   [{i+1}] {log_entry['date']}: {log_entry['action']} - {log_entry['reason'][:30]}")

        # Validation checks
        print(f"\n5. Validation Checks...")

        checks_passed = 0
        total_checks = 4

        # Check 1: All decisions processed
        if len(decisions) == len(test_dates):
            print(f"   ✓ All {len(test_dates)} dates processed")
            checks_passed += 1
        else:
            print(f"   ✗ Only {len(decisions)}/{len(test_dates)} dates processed")

        # Check 2: No errors in decisions
        error_count = sum(1 for d in decisions if d.get('action') == 'ERROR')
        if error_count == 0:
            print(f"   ✓ No decision errors")
            checks_passed += 1
        else:
            print(f"   ✗ {error_count} decision errors")

        # Check 3: V0 sentiment always 1.0
        sentiments = [d.get('sentiment') for d in decisions if 'sentiment' in d]
        if all(s == 1.0 for s in sentiments):
            print(f"   ✓ V0 sentiment consistently 1.0")
            checks_passed += 1
        else:
            print(f"   ✗ V0 sentiment not consistent: {sentiments}")

        # Check 4: MACD values present
        macd_values = [d for d in decisions if d.get('macd_today') is not None]
        if len(macd_values) > 0:
            print(f"   ✓ MACD calculations successful ({len(macd_values)} entries)")
            checks_passed += 1
        else:
            print(f"   ✗ No MACD calculations successful")

        # Overall result
        print(f"\n6. Overall Result...")
        print(f"   Validation: {checks_passed}/{total_checks} checks passed")

        if checks_passed == total_checks:
            print(f"   🎉 V0 COMPREHENSIVE TEST PASSED!")
            print(f"   ✓ Complete pipeline working correctly")
            print(f"   ✓ Ready for V1-V4 implementation")
            return True
        else:
            print(f"   ⚠️  V0 test completed with {total_checks - checks_passed} issues")
            print(f"   - Pipeline functional but needs attention")
            return False

    except Exception as e:
        print(f"\n✗ V0 Comprehensive Test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_prerequisites():
    """Check if we have the necessary API keys and dependencies."""
    print("Checking prerequisites...")

    try:
        # Load config file
        config_path = os.path.join(os.path.dirname(__file__), '../../..', 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Check required keys
        required_keys = ['OPEN_AI_KEY']
        optional_keys = ['POLYGON_IO', 'ALPHA_VANTAGE_KEY']

        missing_required = []
        missing_optional = []

        for key in required_keys:
            if key in config and config[key]:
                print(f"✓ {key} found in config")
            else:
                missing_required.append(key)

        for key in optional_keys:
            if key in config and config[key]:
                print(f"✓ {key} found in config")
            else:
                missing_optional.append(key)

        if missing_required:
            print(f"✗ Missing required config keys: {missing_required}")
            print("  Please add these to config/config.json")
            return False

        if missing_optional:
            print(f"⚠  Missing optional config keys: {missing_optional}")
            print("  Tests may use fallback data sources")

        print("✓ Prerequisites check passed - API keys loaded from config")
        return True

    except FileNotFoundError:
        print("✗ config/config.json not found")
        return False
    except json.JSONDecodeError:
        print("✗ config/config.json is not valid JSON")
        return False
    except Exception as e:
        print(f"✗ Error loading config: {str(e)}")
        return False


if __name__ == "__main__":
    print("V0 Comprehensive Pipeline Test")
    print("Testing complete orchestrator with real tools and API calls")

    # Check prerequisites
    if not check_prerequisites():
        print("\nSkipping test due to missing prerequisites")
        print("Set required environment variables and try again")
        sys.exit(1)

    # Run comprehensive test
    success = run_v0_comprehensive_test()

    if success:
        print("\n" + "=" * 70)
        print("🎉 V0 PIPELINE FULLY VALIDATED!")
        print("Ready to implement V1-V4 sentiment agents!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("⚠️  V0 pipeline needs attention before proceeding")
        print("=" * 70)
        sys.exit(1)
