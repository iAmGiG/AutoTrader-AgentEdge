#!/usr/bin/env python3
"""Demo script to showcase enhanced reporting capabilities.

This demonstrates the advisor-ready reporting features without
running a full backtest.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.report_generator import ReportGenerator
from src.utils.output_manager import OutputManager
from pathlib import Path
import json
from datetime import datetime, timedelta


def create_demo_backtest_data():
    """Create realistic demo data for showcasing reports."""
    
    # Setup output directory
    output_manager = OutputManager()
    run_dir = output_manager.create_run_directory("DEMO", "2024-01-01", "2024-03-31")
    
    # Create sample daily reasoning data with high-quality analysis
    daily_data = []
    
    # Day 1 - Strong bullish signals
    daily_data.append({
        "date": "2024-01-15",
        "agents": {
            "sentiment": {
                "analysis": "Exceptional positive sentiment detected across multiple news sources. "
                           "The company's Q4 earnings report exceeded analyst expectations by 25%, "
                           "with revenue growth of 18% YoY. CEO guidance for next quarter suggests "
                           "continued momentum. Institutional investors are increasing positions, "
                           "with notable purchases from major hedge funds. Social media sentiment "
                           "analysis shows 85% positive mentions, highest level in 12 months. "
                           "The product launch announcement has generated significant buzz in tech "
                           "communities. Market reaction has been overwhelmingly positive.",
                "score": 0.92,
                "confidence": 0.95,
                "tools_called": ["fetch_all_news", "analyze_sentiment", "social_media_scan"],
                "key_themes": ["earnings beat", "institutional buying", "product innovation"]
            },
            "technical": {
                "analysis": "Strong bullish technical setup confirmed across multiple timeframes. "
                           "MACD histogram showing acceleration with bullish crossover confirmed "
                           "3 days ago. Price broke above 50-day MA with volume 2.5x average, "
                           "indicating institutional accumulation. RSI at 68 shows strength without "
                           "being overbought. Fibonacci retracement shows support at $145 (38.2%) "
                           "with next resistance at $165 (61.8% extension). Volume profile indicates "
                           "strong buying interest at current levels. Bollinger Bands expanding, "
                           "suggesting increased volatility and potential for continued upward movement.",
                "macd_today": 3.25,
                "macd_yest": 2.80,
                "pattern": "Bullish Flag Breakout",
                "signal_strength": 0.88,
                "tools_called": ["fetch_market_data", "calculate_indicators"]
            }
        },
        "coordinator_summary": {
            "synthesis": "Unanimous bullish signals from all agents. Sentiment shows exceptional "
                        "positive momentum backed by fundamental catalysts. Technical indicators "
                        "confirm uptrend with strong volume support. Risk metrics acceptable with "
                        "stop-loss at $145. Recommended action: STRONG BUY with high conviction.",
            "aggregated_signals": {"sentiment": 0.92, "technical": 0.88, "risk": 0.15}
        },
        "trading_decision": {
            "action": "BUY",
            "reasoning": "Confluence of positive factors creates high-probability setup. "
                        "Earnings momentum, institutional support, and technical breakout "
                        "align perfectly. Risk/reward ratio favorable at 1:3.",
            "confidence": 0.90,
            "conditions_met": {
                "sentiment_positive": True,
                "macd_bullish": True,
                "volume_confirmation": True,
                "risk_acceptable": True
            }
        }
    })
    
    # Day 2 - Consolidation
    daily_data.append({
        "date": "2024-01-16",
        "agents": {
            "sentiment": {
                "analysis": "Sentiment remains positive but showing signs of consolidation. "
                           "No new major catalysts today, market digesting yesterday's moves. "
                           "Analyst upgrades from 3 major banks with average PT of $170. "
                           "Some profit-taking observed in pre-market but buying interest "
                           "remains strong at dips. Options flow shows continued bullish "
                           "positioning with unusual call volume at $160 strike.",
                "score": 0.65,
                "confidence": 0.80,
                "tools_called": ["fetch_all_news", "options_flow_analysis"]
            },
            "technical": {
                "analysis": "Healthy consolidation pattern forming after yesterday's breakout. "
                           "Price holding above breakout level with decreasing volume, typical "
                           "of a bull flag formation. MACD still positive but flattening. "
                           "Support building at $152 level. Market structure remains intact.",
                "macd_today": 3.15,
                "macd_yest": 3.25,
                "pattern": "Bull Flag Consolidation",
                "signal_strength": 0.70
            }
        },
        "coordinator_summary": {
            "synthesis": "Normal consolidation after strong move. All indicators suggest "
                        "continuation pattern rather than reversal. Hold current positions.",
            "aggregated_signals": {"sentiment": 0.65, "technical": 0.70, "risk": 0.20}
        }
    })
    
    # Day 3 - Warning signs
    daily_data.append({
        "date": "2024-02-01",
        "agents": {
            "sentiment": {
                "analysis": "Sentiment shifting negative on regulatory concerns. SEC announced "
                           "investigation into company's accounting practices. While management "
                           "claims confidence in their methods, market showing risk-off behavior. "
                           "Short interest increasing significantly. Social sentiment turned "
                           "negative with concerns about potential fines. Institutional flow "
                           "data shows some distribution beginning.",
                "score": -0.45,
                "confidence": 0.85,
                "tools_called": ["fetch_all_news", "regulatory_filings", "short_interest_data"]
            },
            "technical": {
                "analysis": "Technical breakdown in progress. Price gapped down below 50-day MA "
                           "on heavy volume. MACD crossed below signal line indicating trend "
                           "reversal. Support at $145 being tested. RSI dropped from 68 to 42 "
                           "in two sessions showing momentum shift. Volume patterns suggest "
                           "institutional selling. Next support at $140 (200-day MA).",
                "macd_today": -0.85,
                "macd_yest": 0.20,
                "pattern": "Bearish Reversal",
                "signal_strength": 0.82
            }
        },
        "coordinator_summary": {
            "synthesis": "Risk-off signal triggered. Regulatory concerns creating uncertainty. "
                        "Technical breakdown confirms sentiment shift. Recommend closing longs "
                        "and considering protective strategies.",
            "aggregated_signals": {"sentiment": -0.45, "technical": -0.82, "risk": 0.75}
        },
        "trading_decision": {
            "action": "SELL",
            "reasoning": "Regulatory risk introduces unquantifiable downside. Technical "
                        "breakdown confirms distribution. Protecting capital takes priority "
                        "over potential gains. Can re-enter when situation clarifies.",
            "confidence": 0.88,
            "conditions_met": {
                "sentiment_negative": True,
                "macd_bearish": True,
                "risk_elevated": True
            }
        }
    })
    
    # Save daily reasoning files
    for day_data in daily_data:
        date = day_data['date']
        daily_file = run_dir / 'analysis' / 'daily_reasoning' / f'{date}.json'
        output_manager.save_json(daily_file, day_data)
    
    # Create sample metrics
    metrics = {
        'total_return': 18.5,
        'sharpe_ratio': 2.1,
        'max_drawdown': -7.3,
        'win_rate': 68.0,
        'num_trades': 15,
        'avg_win_loss_ratio': 2.3
    }
    
    # Create sample trades
    trades = [
        {
            'date': '2024-01-15',
            'action': 'BUY',
            'price': 150.25,
            'qty': 100,
            'sentiment': 0.92,
            'macd_today': 3.25,
            'reasoning': 'Strong confluence of bullish signals. Earnings beat and technical breakout.'
        },
        {
            'date': '2024-02-01', 
            'action': 'SELL',
            'price': 158.75,
            'qty': 100,
            'sentiment': -0.45,
            'macd_today': -0.85,
            'reasoning': 'Regulatory concerns and technical breakdown. Risk management priority.'
        }
    ]
    
    # Save sample data files
    import pandas as pd
    pd.DataFrame(trades).to_csv(run_dir / 'data' / 'trades.csv', index=False)
    pd.DataFrame([metrics]).to_csv(run_dir / 'data' / 'metrics.csv', index=False)
    
    # Update metadata to show completed
    metadata_file = run_dir / 'metadata.json'
    metadata = output_manager.load_json(metadata_file)
    metadata['status'] = 'completed'
    output_manager.save_json(metadata_file, metadata)
    
    return run_dir, metrics


def main():
    print("🎯 Enhanced Reporting Demo")
    print("="*50)
    
    # Create demo data
    print("\n1️⃣ Creating demo backtest data...")
    run_dir, metrics = create_demo_backtest_data()
    print(f"✅ Demo data created in: {run_dir}")
    
    # Initialize report generator
    report_gen = ReportGenerator()
    
    # Generate enhanced executive summary
    print("\n2️⃣ Generating enhanced executive summary...")
    exec_summary = report_gen.generate_executive_summary(run_dir, metrics)
    exec_path = run_dir / 'reports' / 'executive_summary_demo.md'
    exec_path.write_text(exec_summary)
    print(f"✅ Executive summary saved to: {exec_path}")
    
    # Extract best LLM examples
    print("\n3️⃣ Extracting best LLM analysis examples...")
    llm_examples = report_gen.extract_llm_examples(run_dir, num_examples=5)
    
    print("\nExtracted examples by category:")
    for category, examples in llm_examples.items():
        if examples:
            print(f"  - {category}: {len(examples)} examples")
            # Show first example snippet
            if examples and 'analysis' in examples[0]:
                snippet = examples[0]['analysis'][:100] + "..."
                print(f"    Example: {snippet}")
    
    # Save examples
    examples_path = run_dir / 'analysis' / 'demo_llm_examples.json'
    with open(examples_path, 'w') as f:
        json.dump(llm_examples, f, indent=2, default=str)
    print(f"\n✅ LLM examples saved to: {examples_path}")
    
    # Generate consolidated report for single run
    print("\n4️⃣ Generating consolidated report...")
    report_path = run_dir / 'reports' / 'consolidated_demo.md'
    report_gen.create_consolidated_report([run_dir], report_path)
    
    print(f"\n✅ Demo complete! Check the following files:")
    print(f"  📄 {exec_path}")
    print(f"  📄 {examples_path}")
    print(f"  📄 {report_path}")
    
    # Print a sample of the executive summary
    print("\n" + "="*50)
    print("SAMPLE OF EXECUTIVE SUMMARY:")
    print("="*50)
    lines = exec_summary.split('\n')[:30]
    print('\n'.join(lines))
    print("\n... (truncated)")


if __name__ == "__main__":
    main()