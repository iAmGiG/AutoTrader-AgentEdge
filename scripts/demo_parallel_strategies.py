#!/usr/bin/env python3
"""Demonstrate parallel strategy comparison - Mechanical vs LLM.

This script shows how LLM-based trading decisions compare to mechanical rules.
"""

import sys
import logging
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.coordinator_agent import CoordinatorAgent
from src.utils.parallel_strategy_tester import ParallelStrategyTester
from src.tools.cache.market_data_cache import MarketDataCache
from src.tools.data_sources.market.market_data_tool import MarketDataTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run parallel strategy comparison."""
    
    # Parameters
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "2025-01-15"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "2025-01-20"
    
    print(f"\n{'='*60}")
    print(f"Parallel Strategy Comparison: Mechanical vs LLM")
    print(f"{'='*60}")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date} to {end_date}")
    print(f"{'='*60}\n")
    
    # Initialize components
    coordinator = CoordinatorAgent()
    tester = ParallelStrategyTester()
    cache = MarketDataCache()
    
    # Get market data
    print("Fetching market data...")
    market_tool = MarketDataTool()
    prices = market_tool.fetch_market_data(symbol, start_date, end_date)
    
    if prices.empty:
        print("Error: No market data available")
        return
    
    # Process each trading day
    print(f"\nProcessing {len(prices)} trading days...\n")
    
    for idx, (date, row) in enumerate(prices.iterrows()):
        date_str = date.strftime("%Y-%m-%d")
        price = float(row['Close'])
        
        print(f"Day {idx+1}/{len(prices)}: {date_str} - Price: ${price:.2f}")
        
        try:
            # Get signals from agents
            signals = await coordinator.get_signals(date_str, symbol)
            
            if not signals.get("ok"):
                print(f"  ⚠️  Error getting signals: {signals.get('error', 'Unknown error')}")
                continue
            
            # Run parallel comparison
            comparison = tester.run_parallel_decision(signals, price, date_str)
            
            # Display results
            mech_action = comparison["mechanical"]["action"]
            llm_action = comparison["llm"]["action"]
            agree = comparison["agreement"]
            
            print(f"  📊 Mechanical: {mech_action}")
            print(f"  🤖 LLM: {llm_action} (confidence: {comparison['llm'].get('confidence', 'N/A')})")
            print(f"  {'✅ AGREE' if agree else '❌ DISAGREE'}")
            
            if not agree:
                # Show reasoning for disagreements
                if isinstance(comparison["llm"]["reasoning"], dict):
                    rationale = comparison["llm"]["reasoning"].get("decision_rationale", "No rationale")
                    print(f"  💭 LLM reasoning: {rationale}")
                
                if comparison["mechanical"].get("filtered"):
                    print(f"  🔧 Mechanical filter: {comparison['mechanical']['filtered']}")
            
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            logger.error(f"Error processing {date_str}: {e}", exc_info=True)
    
    # Display final comparison
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}\n")
    
    # Get performance comparison
    perf = tester.get_performance_comparison()
    
    print("📊 Performance Metrics:")
    print(f"  Mechanical Return: {perf['mechanical']['total_return_pct']:.2f}%")
    print(f"  LLM Return: {perf['llm']['total_return_pct']:.2f}%")
    print(f"  LLM Outperformance: {perf['comparison']['llm_outperformance']:.2f}%\n")
    
    print("📈 Risk Metrics:")
    print(f"  Mechanical Sharpe: {perf['mechanical']['sharpe_ratio']:.2f}")
    print(f"  LLM Sharpe: {perf['llm']['sharpe_ratio']:.2f}")
    print(f"  {'✅' if perf['comparison']['llm_better_sharpe'] else '❌'} LLM has better risk-adjusted returns\n")
    
    print("🤝 Agreement Statistics:")
    print(f"  Total Decisions: {tester.agreement_stats['total_decisions']}")
    print(f"  Agreement Rate: {tester.agreement_stats['agreement_rate']:.1%}")
    print(f"  Disagreements: {tester.agreement_stats['disagreements']}\n")
    
    # Analyze disagreements
    disagreement_analysis = tester.analyze_disagreements()
    if disagreement_analysis.get("total_disagreements", 0) > 0:
        print("🔍 Disagreement Analysis:")
        for pattern, count in disagreement_analysis.get("by_action", {}).items():
            print(f"  {pattern}: {count} times")
        
        if disagreement_analysis.get("common_patterns"):
            print("\n  Common patterns:")
            for pattern in disagreement_analysis["common_patterns"]:
                print(f"  - {pattern}")
    
    # Save results
    output_dir = tester.save_results(f"{symbol}_{start_date}_{end_date}")
    print(f"\n💾 Results saved to: {output_dir}")
    
    print(f"\n{'='*60}")
    print("✅ Comparison complete!")
    print(f"{'='*60}\n")


# Fix for async in script
if __name__ == "__main__":
    import asyncio
    
    async def async_main():
        """Async wrapper for main."""
        # Parameters
        symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
        start_date = sys.argv[2] if len(sys.argv) > 2 else "2025-01-15"
        end_date = sys.argv[3] if len(sys.argv) > 3 else "2025-01-20"
        
        print(f"\n{'='*60}")
        print(f"Parallel Strategy Comparison: Mechanical vs LLM")
        print(f"{'='*60}")
        print(f"Symbol: {symbol}")
        print(f"Period: {start_date} to {end_date}")
        print(f"{'='*60}\n")
        
        # Initialize components
        coordinator = CoordinatorAgent()
        tester = ParallelStrategyTester()
        
        # Get market data
        print("Fetching market data...")
        market_tool = MarketDataTool()
        prices = market_tool.fetch_market_data(symbol, start_date, end_date)
        
        if prices.empty:
            print("Error: No market data available")
            return
        
        # Process each trading day
        print(f"\nProcessing {len(prices)} trading days...\n")
        
        for idx, (date, row) in enumerate(prices.iterrows()):
            date_str = date.strftime("%Y-%m-%d")
            price = float(row['Close'])
            
            print(f"Day {idx+1}/{len(prices)}: {date_str} - Price: ${price:.2f}")
            
            try:
                # Get signals from agents
                signals = await coordinator.get_signals(date_str, symbol)
                
                if not signals.get("ok"):
                    print(f"  ⚠️  Error getting signals: {signals.get('error', 'Unknown error')}")
                    continue
                
                # Run parallel comparison
                comparison = tester.run_parallel_decision(signals, price, date_str)
                
                # Display results
                mech_action = comparison["mechanical"]["action"]
                llm_action = comparison["llm"]["action"]
                agree = comparison["agreement"]
                
                print(f"  📊 Mechanical: {mech_action}")
                print(f"  🤖 LLM: {llm_action} (confidence: {comparison['llm'].get('confidence', 'N/A')})")
                print(f"  {'✅ AGREE' if agree else '❌ DISAGREE'}")
                
                if not agree:
                    # Show reasoning for disagreements
                    if isinstance(comparison["llm"]["reasoning"], dict):
                        rationale = comparison["llm"]["reasoning"].get("decision_rationale", "No rationale")
                        print(f"  💭 LLM reasoning: {rationale}")
                    
                    if comparison["mechanical"].get("filtered"):
                        print(f"  🔧 Mechanical filter: {comparison['mechanical']['filtered']}")
                
                print()
                
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                logger.error(f"Error processing {date_str}: {e}", exc_info=True)
        
        # Display final comparison
        print(f"\n{'='*60}")
        print("FINAL RESULTS")
        print(f"{'='*60}\n")
        
        # Get performance comparison
        perf = tester.get_performance_comparison()
        
        print("📊 Performance Metrics:")
        print(f"  Mechanical Return: {perf['mechanical']['total_return_pct']:.2f}%")
        print(f"  LLM Return: {perf['llm']['total_return_pct']:.2f}%")
        print(f"  LLM Outperformance: {perf['comparison']['llm_outperformance']:.2f}%\n")
        
        print("📈 Risk Metrics:")
        print(f"  Mechanical Sharpe: {perf['mechanical']['sharpe_ratio']:.2f}")
        print(f"  LLM Sharpe: {perf['llm']['sharpe_ratio']:.2f}")
        print(f"  {'✅' if perf['comparison']['llm_better_sharpe'] else '❌'} LLM has better risk-adjusted returns\n")
        
        print("🤝 Agreement Statistics:")
        print(f"  Total Decisions: {tester.agreement_stats['total_decisions']}")
        print(f"  Agreement Rate: {tester.agreement_stats['agreement_rate']:.1%}")
        print(f"  Disagreements: {tester.agreement_stats['disagreements']}\n")
        
        # Analyze disagreements
        disagreement_analysis = tester.analyze_disagreements()
        if disagreement_analysis.get("total_disagreements", 0) > 0:
            print("🔍 Disagreement Analysis:")
            for pattern, count in disagreement_analysis.get("by_action", {}).items():
                print(f"  {pattern}: {count} times")
            
            if disagreement_analysis.get("common_patterns"):
                print("\n  Common patterns:")
                for pattern in disagreement_analysis["common_patterns"]:
                    print(f"  - {pattern}")
        
        # Save results
        output_dir = tester.save_results(f"{symbol}_{start_date}_{end_date}")
        print(f"\n💾 Results saved to: {output_dir}")
        
        print(f"\n{'='*60}")
        print("✅ Comparison complete!")
        print(f"{'='*60}\n")
    
    asyncio.run(async_main())