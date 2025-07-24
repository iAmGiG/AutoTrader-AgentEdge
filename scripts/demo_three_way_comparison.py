#!/usr/bin/env python3
"""Demonstrate three-way strategy comparison: Buy & Hold vs Mechanical vs LLM.

This script proves the progression of performance improvements.
"""

import sys
import logging
from datetime import datetime
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.coordinator_agent import CoordinatorAgent
from src.utils.parallel_strategy_tester import ParallelStrategyTester
from src.tools.data_sources.market.market_data_tool import MarketDataTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Run three-way strategy comparison."""
    
    # Parameters
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "2025-01-10"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "2025-01-20"
    
    print(f"\n{'='*70}")
    print(f"Three-Way Strategy Comparison: Buy & Hold vs Mechanical vs LLM")
    print(f"{'='*70}")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Goal: Prove LLM > Mechanical > Buy & Hold")
    print(f"{'='*70}\n")
    
    # Initialize components
    coordinator = CoordinatorAgent()
    tester = ParallelStrategyTester(initial_capital=10000)
    
    # Get market data
    print("📊 Fetching market data...")
    market_tool = MarketDataTool()
    prices = market_tool.fetch_market_data(symbol, start_date, end_date)
    
    if prices.empty:
        print("❌ Error: No market data available")
        return
    
    print(f"✅ Found {len(prices)} trading days\n")
    
    # Process each trading day
    print("🔄 Running strategies in parallel...\n")
    
    for idx, (date, row) in enumerate(prices.iterrows()):
        date_str = date.strftime("%Y-%m-%d")
        price = float(row['Close'])
        
        print(f"📅 Day {idx+1}/{len(prices)}: {date_str} - Price: ${price:.2f}")
        
        try:
            # Get signals from agents
            signals = await coordinator.get_signals(date_str, symbol)
            
            if not signals.get("ok"):
                print(f"  ⚠️  Error getting signals: {signals.get('error', 'Unknown')}")
                continue
            
            # Run three-way comparison
            comparison = tester.run_three_way_comparison(signals, price, date_str)
            
            # Display decisions
            bh_action = comparison["buy_hold"]["action"]
            mech_action = comparison["mechanical"]["action"]
            llm_action = comparison["llm"]["action"]
            
            print(f"  💰 Buy & Hold: {bh_action}")
            print(f"  🔧 Mechanical: {mech_action}")
            print(f"  🤖 LLM: {llm_action} (confidence: {comparison['llm'].get('confidence', 'N/A')})")
            
            # Highlight differences
            if mech_action != bh_action or llm_action != bh_action:
                print(f"  📍 Active strategies diverge from Buy & Hold")
            
            if mech_action != llm_action:
                print(f"  ⚡ LLM disagrees with Mechanical")
                if isinstance(comparison["llm"]["reasoning"], dict):
                    rationale = comparison["llm"]["reasoning"].get("decision_rationale", "")
                    if rationale:
                        print(f"  💭 LLM reasoning: {rationale[:100]}...")
            
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            logger.error(f"Error processing {date_str}: {e}", exc_info=True)
    
    # Get final comparison
    print(f"\n{'='*70}")
    print("📊 FINAL RESULTS - Strategy Performance Comparison")
    print(f"{'='*70}\n")
    
    perf = tester.get_three_way_comparison()
    
    # Display performance table
    print("Strategy     | Return   | Sharpe | Max DD  | Trades | Final Value")
    print("-------------|----------|--------|---------|--------|------------")
    
    # Buy & Hold
    bh = perf["buy_hold"]
    print(f"Buy & Hold   | {bh['total_return_pct']:>7.2f}% | {bh['sharpe_ratio']:>6.2f} | "
          f"{bh['max_drawdown']:>6.2%} | {bh['num_trades']:>6} | ${bh['final_equity']:>10,.2f}")
    
    # Mechanical
    mech = perf["mechanical"]
    print(f"Mechanical   | {mech['total_return_pct']:>7.2f}% | {mech['sharpe_ratio']:>6.2f} | "
          f"{mech['max_drawdown']:>6.2%} | {mech['num_trades']:>6} | ${mech['final_equity']:>10,.2f}")
    
    # LLM
    llm = perf["llm"]
    print(f"LLM Strategy | {llm['total_return_pct']:>7.2f}% | {llm['sharpe_ratio']:>6.2f} | "
          f"{llm['max_drawdown']:>6.2%} | {llm['num_trades']:>6} | ${llm['final_equity']:>10,.2f}")
    
    print(f"\n{'='*70}")
    print("📈 PERFORMANCE PROGRESSION")
    print(f"{'='*70}\n")
    
    # Show progression
    comp = perf["comparisons"]
    
    print("1️⃣ Mechanical vs Buy & Hold:")
    print(f"   Outperformance: {comp['mechanical_vs_bh']['outperformance']:+.2f}%")
    print(f"   Better Sharpe: {'✅' if comp['mechanical_vs_bh']['better_sharpe'] else '❌'}")
    print(f"   Lower Drawdown: {'✅' if comp['mechanical_vs_bh']['lower_drawdown'] else '❌'}")
    
    print("\n2️⃣ LLM vs Buy & Hold:")
    print(f"   Outperformance: {comp['llm_vs_bh']['outperformance']:+.2f}%")
    print(f"   Better Sharpe: {'✅' if comp['llm_vs_bh']['better_sharpe'] else '❌'}")
    print(f"   Lower Drawdown: {'✅' if comp['llm_vs_bh']['lower_drawdown'] else '❌'}")
    
    print("\n3️⃣ LLM vs Mechanical:")
    print(f"   Outperformance: {comp['llm_vs_mechanical']['outperformance']:+.2f}%")
    print(f"   Better Sharpe: {'✅' if comp['llm_vs_mechanical']['better_sharpe'] else '❌'}")
    print(f"   Lower Drawdown: {'✅' if comp['llm_vs_mechanical']['lower_drawdown'] else '❌'}")
    
    # Summary
    print(f"\n{'='*70}")
    print("🎯 CONCLUSION")
    print(f"{'='*70}\n")
    
    # Check if we proved the progression
    mech_beats_bh = comp['mechanical_vs_bh']['outperformance'] > 0
    llm_beats_bh = comp['llm_vs_bh']['outperformance'] > 0  
    llm_beats_mech = comp['llm_vs_mechanical']['outperformance'] > 0
    
    if mech_beats_bh and llm_beats_bh and llm_beats_mech:
        print("✅ SUCCESS! Proved: LLM > Mechanical > Buy & Hold")
        print("   Expert rules add value, and AI adds even more value!")
    else:
        print("⚠️  Results mixed:")
        print(f"   Mechanical > Buy & Hold: {'✅' if mech_beats_bh else '❌'}")
        print(f"   LLM > Buy & Hold: {'✅' if llm_beats_bh else '❌'}")
        print(f"   LLM > Mechanical: {'✅' if llm_beats_mech else '❌'}")
    
    # Save results
    output_dir = tester.save_results(f"three_way_{symbol}_{start_date}_{end_date}")
    print(f"\n💾 Detailed results saved to: {output_dir}")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())