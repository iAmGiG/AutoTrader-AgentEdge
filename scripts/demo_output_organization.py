#!/usr/bin/env python3
"""Demo script showing output organization helper functions.

This demonstrates how to use the output organization functions
independently for testing and development.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backtest_mas import setup_output_directory, save_llm_reasoning, save_run_summary
from datetime import datetime


def demo_output_organization():
    """Demonstrate the output organization functions."""
    
    # 1. Setup output directory structure
    print("1. Setting up output directory structure...")
    paths = setup_output_directory("DEMO", "2024-01-01", "2024-01-31")
    
    print("\nCreated directories:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    
    # 2. Demo LLM reasoning data
    print("\n2. Creating sample LLM reasoning data...")
    sample_reasoning = [
        {
            'date': '2024-01-01',
            'agents': {
                'sentiment': {
                    'analysis': 'Strong positive sentiment detected. News coverage shows ' +
                                'excitement about Q4 earnings beat and new product announcements. ' +
                                'Market reaction has been overwhelmingly positive with high ' +
                                'trading volumes indicating institutional interest.',
                    'score': 0.85,
                    'confidence': 0.9
                },
                'technical': {
                    'analysis': 'MACD showing bullish crossover with strong momentum. ' +
                                'Price has broken above 50-day MA with volume confirmation. ' +
                                'RSI at 65 indicates strength without being overbought. ' +
                                'Support established at $150 level.',
                    'macd_today': 2.5,
                    'macd_yest': 1.8
                }
            },
            'coordinator_summary': {
                'synthesis': 'Both sentiment and technical indicators align bullishly. ' +
                            'Recommended action: BUY signal with high confidence.'
            }
        },
        {
            'date': '2024-01-02',
            'agents': {
                'sentiment': {
                    'analysis': 'Neutral sentiment with mixed signals. Some profit-taking ' +
                                'observed but no negative news. Analysts maintaining buy ratings.',
                    'score': 0.1,
                    'confidence': 0.7
                },
                'technical': {
                    'analysis': 'Consolidation pattern forming. MACD still positive but ' +
                                'flattening. Volume decreasing suggests pause in trend.',
                    'macd_today': 2.3,
                    'macd_yest': 2.5
                }
            }
        }
    ]
    
    # Save LLM reasoning
    reasoning_path = os.path.join(paths['analysis_dir'], 'all_reasoning.json')
    save_llm_reasoning(sample_reasoning, reasoning_path)
    
    # 3. Demo metrics and trades
    print("\n3. Creating sample metrics and trades...")
    sample_metrics = {
        'total_return': 15.5,
        'sharpe_ratio': 1.8,
        'max_drawdown': -8.2,
        'win_rate': 65.0,
        'num_trades': 12
    }
    
    sample_trades = [
        {
            'date': '2024-01-01',
            'action': 'BUY',
            'price': 152.50,
            'qty': 100,
            'sentiment': 0.85,
            'macd_today': 2.5,
            'reasoning': 'Strong bullish signals from both sentiment and technical analysis. ' +
                        'Positive earnings surprise and MACD crossover indicate upward momentum.'
        },
        {
            'date': '2024-01-15',
            'action': 'SELL',
            'price': 165.75,
            'qty': 100,
            'sentiment': -0.3,
            'macd_today': -0.5,
            'reasoning': 'Sentiment turned negative on regulatory concerns. MACD crossed ' +
                        'below signal line indicating trend reversal. Taking profits.'
        }
    ]
    
    sample_best_insights = {
        'sentiment_analysis': [
            {
                'date': '2024-01-01',
                'insight': {
                    'summary': 'Q4 earnings beat expectations by 20%, driving positive sentiment'
                }
            }
        ],
        'technical_patterns': [
            {
                'date': '2024-01-01',
                'pattern': 'Bullish MACD Crossover',
                'significance': 'high'
            }
        ]
    }
    
    # Save run summary
    save_run_summary('DEMO', sample_metrics, sample_trades, 
                    sample_best_insights, paths['reports_dir'])
    
    print("\n✅ Demo completed! Check the output directory for generated files.")
    print(f"\nOutput location: {paths['run_dir']}")


if __name__ == "__main__":
    demo_output_organization()