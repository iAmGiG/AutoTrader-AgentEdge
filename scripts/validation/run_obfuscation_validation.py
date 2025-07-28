#!/usr/bin/env python3
"""
Run Obfuscation Validation Tests - Issue #134

This script runs the critical validation to determine if our LLM is using
training knowledge vs genuine analysis by comparing performance with/without
date and ticker obfuscation.

If performance drops dramatically with obfuscation, we have data leakage.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation.obfuscation_validator import ObfuscationValidator


async def run_critical_validation_tests():
    """
    Run the critical validation tests to detect data leakage.
    
    These tests will determine if our impressive backtest results
    are due to genuine LLM analysis or memorized training data.
    """
    print("🚨 CRITICAL VALIDATION: Testing for LLM Data Leakage")
    print("=" * 70)
    print("Issue #134: Date Obfuscation Testing")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize validator
    validator = ObfuscationValidator(use_cached_data=True)
    
    # Test scenarios - using periods where we previously saw good performance
    test_scenarios = [
        {
            'symbol': 'SPY',
            'start_date': '2022-07-01',
            'end_date': '2022-08-31',
            'description': '2022 Summer Bear Market (Previous +2.37% return)'
        },
        {
            'symbol': 'AAPL', 
            'start_date': '2022-07-01',
            'end_date': '2022-08-31',
            'description': '2022 AAPL Summer Period (Previous outperformance)'
        },
        {
            'symbol': 'TSLA',
            'start_date': '2022-07-01', 
            'end_date': '2022-08-31',
            'description': '2022 TSLA Summer Period (Previous capital preservation)'
        }
    ]
    
    print("📋 Test Scenarios:")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"   {i}. {scenario['symbol']}: {scenario['description']}")
    print()
    
    # Run validation tests
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"🧪 Running Test {i}/{len(test_scenarios)}: {scenario['symbol']}")
        print(f"   Period: {scenario['start_date']} to {scenario['end_date']}")
        print(f"   Context: {scenario['description']}")
        
        try:
            # Run comparison test
            test_result = await validator.run_comparison_test(
                symbol=scenario['symbol'],
                start_date=scenario['start_date'],
                end_date=scenario['end_date'],
                test_name=f"Test_{i}_{scenario['symbol']}"
            )
            
            results.append(test_result)
            
            # Quick summary
            perf_comp = test_result['performance_comparison']
            leak_assess = test_result['data_leakage_assessment']
            
            print(f"   📊 Real Return: {perf_comp['real_return']:+.2f}%")
            print(f"   📊 Obfuscated Return: {perf_comp['obfuscated_return']:+.2f}%")
            print(f"   📊 Performance Degradation: {perf_comp['performance_degradation_pct']:+.1f}%")
            print(f"   🔍 Assessment: {leak_assess['assessment']}")
            print()
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            print()
            continue
    
    # Generate comprehensive report
    print("📄 Generating validation report...")
    
    # Create output directory
    output_dir = Path('.cache/validation/obfuscation')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save detailed results
    results_file = output_dir / f'obfuscation_results_{timestamp}.json'
    validator.save_results(str(results_file))
    
    # Generate validation report
    report_file = output_dir / f'obfuscation_validation_report_{timestamp}.md'
    report_content = validator.generate_validation_report(str(report_file))
    
    # Print summary to console
    print("\n" + "=" * 70)
    print("🎯 VALIDATION SUMMARY")
    print("=" * 70)
    
    if results:
        # Overall assessment
        high_risk_count = sum(1 for r in results if r['data_leakage_assessment']['likely_data_leakage'])
        total_tests = len(results)
        
        print(f"Total Tests: {total_tests}")
        print(f"High Risk (Likely Data Leakage): {high_risk_count}")
        print(f"Clean Tests: {total_tests - high_risk_count}")
        print(f"Data Leakage Rate: {high_risk_count/total_tests*100:.1f}%")
        print()
        
        # Critical assessment
        if high_risk_count > total_tests * 0.5:
            print("🚨 CRITICAL FINDING: Majority of tests show data leakage")
            print("   ❌ Previous backtest results are INVALID")
            print("   🔄 Must switch to live trading validation")
        elif high_risk_count > 0:
            print("⚠️  WARNING: Some tests suggest data leakage")
            print("   🔍 Results are QUESTIONABLE - need more validation")
            print("   🎯 Recommend focusing on clean test scenarios")
        else:
            print("✅ CLEAN: No evidence of data leakage detected")
            print("   ✨ Previous results appear to be legitimate")
            print("   🚀 Can proceed with confidence in LLM system")
        
        print()
        print("📁 Detailed Results:")
        print(f"   JSON: {results_file}")
        print(f"   Report: {report_file}")
        
    else:
        print("❌ No validation tests completed successfully")
        print("🔧 Check system configuration and try again")
    
    print(f"\n✅ Validation complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return results


async def run_quick_validation_test():
    """Run a single quick validation test for immediate feedback."""
    print("⚡ Quick Validation Test")
    print("=" * 40)
    
    validator = ObfuscationValidator(use_cached_data=True)
    
    # Test with SPY data that we know exists
    result = await validator.run_comparison_test(
        symbol='SPY',
        start_date='2022-07-01',
        end_date='2022-08-31',
        test_name='QuickTest_SPY'
    )
    
    # Print results
    perf_comp = result['performance_comparison']
    leak_assess = result['data_leakage_assessment']
    
    print(f"Real Return: {perf_comp['real_return']:+.2f}%")
    print(f"Obfuscated Return: {perf_comp['obfuscated_return']:+.2f}%")
    print(f"Performance Degradation: {perf_comp['performance_degradation_pct']:+.1f}%")
    print(f"Assessment: {leak_assess['assessment']}")
    
    return result


def print_usage():
    """Print usage instructions."""
    print("Usage:")
    print("  python run_obfuscation_validation.py [mode]")
    print()
    print("Modes:")
    print("  full    - Run complete validation suite (default)")
    print("  quick   - Run single quick test")
    print("  help    - Show this help message")
    print()
    print("Examples:")
    print("  python run_obfuscation_validation.py")
    print("  python run_obfuscation_validation.py quick")


async def main():
    """Main execution function."""
    import sys
    
    # Parse command line arguments
    mode = 'full'
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    if mode == 'help':
        print_usage()
        return
    elif mode == 'quick':
        await run_quick_validation_test()
    elif mode == 'full':
        await run_critical_validation_tests()
    else:
        print(f"Unknown mode: {mode}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Validation interrupted by user")
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        sys.exit(1)