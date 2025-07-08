"""MAS back-test utility with LLM reasoning capture.

This version captures and saves all LLM reasoning and analysis
for demonstrating the intelligent analysis performed by the agents.

Usage:
    python backtest_mas.py SYMBOL START END

Example:
    python backtest_mas.py NVDA 2023-01-01 2024-12-31
"""
from src.utils.output_manager import OutputManager
from src.utils.report_generator import ReportGenerator
from src.utils.date_utils import process_date_param
from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.agents.strategy_agent import StrategyAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.tools.cache import MarketDataCache
import traceback
import asyncio
from typing import List, Dict
import pandas as pd
import sys
import os
import json

# Add src to Python path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


def setup_output_directory(symbol: str, start_date: str, end_date: str) -> Dict[str, str]:
    """Create organized output directory structure and return paths.

    Args:
        symbol: Stock symbol
        start_date: Start date of backtest
        end_date: End date of backtest

    Returns:
        Dictionary of output paths
    """
    output_manager = OutputManager()
    run_dir = output_manager.create_run_directory(symbol, start_date, end_date)

    return {
        'run_dir': str(run_dir),
        'data_dir': str(run_dir / 'data'),
        'analysis_dir': str(run_dir / 'analysis'),
        'reports_dir': str(run_dir / 'reports'),
        'daily_reasoning_dir': str(run_dir / 'analysis' / 'daily_reasoning'),
        'agent_responses_dir': str(run_dir / 'analysis' / 'agent_responses'),
        'visualizations_dir': str(run_dir / 'visualizations')
    }


def save_llm_reasoning(daily_reasoning: List[Dict], output_path: str) -> None:
    """Save LLM reasoning with proper formatting and sample analysis.

    Args:
        daily_reasoning: List of daily reasoning dictionaries
        output_path: Path to save the reasoning file
    """
    import json
    from pathlib import Path

    # Extract sample analysis text from first few days
    sample_analyses = []
    for day_data in daily_reasoning[:3]:  # First 3 days as samples
        if 'agents' in day_data:
            sample = {
                'date': day_data.get('date', 'Unknown'),
                'sentiment_analysis': day_data['agents'].get('sentiment', {}).get('analysis', 'N/A'),
                'technical_analysis': day_data['agents'].get('technical', {}).get('analysis', 'N/A'),
                'coordinator_synthesis': day_data.get('coordinator_summary', {}).get('synthesis', 'N/A')
            }
            sample_analyses.append(sample)

    # Create formatted output
    formatted_output = {
        'total_days_analyzed': len(daily_reasoning),
        'sample_analyses': sample_analyses,
        'full_reasoning': daily_reasoning
    }

    # Save with proper JSON formatting
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(formatted_output, f, indent=2, default=str)

    print(f"✅ Saved LLM reasoning to: {output_file}")


def save_run_summary(symbol: str, metrics: Dict, trades: List[Dict],
                     best_insights: Dict, output_dir: str) -> None:
    """Generate and save markdown report for individual run.

    Args:
        symbol: Stock symbol
        metrics: Performance metrics dictionary
        trades: List of trade dictionaries
        best_insights: Best insights extracted from analysis
        output_dir: Directory to save the summary
    """
    from pathlib import Path
    from datetime import datetime

    output_path = Path(output_dir) / 'run_summary.md'

    # Build markdown report
    summary = f"""# Backtest Run Summary: {symbol}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Performance Metrics

| Metric | Value |
|--------|-------|
| Total Return | {metrics.get('total_return', 0):.2f}% |
| Sharpe Ratio | {metrics.get('sharpe_ratio', 0):.2f} |
| Max Drawdown | {metrics.get('max_drawdown', 0):.2f}% |
| Win Rate | {metrics.get('win_rate', 0):.2f}% |
| Number of Trades | {metrics.get('num_trades', 0)} |

## Example Trading Decisions

"""

    # Add first 3 trades as examples
    if trades:
        summary += "### Sample Trades\n\n"
        for i, trade in enumerate(trades[:3]):
            summary += f"""**Trade {i+1}**: {trade['action']} on {trade['date']}
- Price: ${trade['price']:.2f}
- Quantity: {trade['qty']} shares
- Sentiment Score: {trade.get('sentiment', 'N/A')}
- MACD Value: {trade.get('macd_today', 'N/A')}
- Reasoning: {trade.get('reasoning', 'No reasoning captured')[:200]}...

"""

    # Add best insights
    if best_insights:
        summary += "## Key Insights\n\n"

        if best_insights.get('sentiment_analysis'):
            summary += "### Top Sentiment Findings\n"
            for insight in best_insights['sentiment_analysis'][:2]:
                summary += f"- **{insight['date']}**: {insight.get('insight', {}).get('summary', 'N/A')}\n"

        if best_insights.get('technical_patterns'):
            summary += "\n### Notable Technical Patterns\n"
            for pattern in best_insights['technical_patterns'][:2]:
                summary += f"- **{pattern['date']}**: {pattern['pattern']} (Significance: {pattern['significance']})\n"

    # Save the summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary)

    print(f"✅ Saved run summary to: {output_path}")


async def get_signals_with_reasoning(coord: CoordinatorAgent, date: str, symbol: str,
                                     output_manager: OutputManager) -> Dict:
    """Get signals from coordinator and capture all LLM reasoning."""
    # Use the new method that returns both signals and raw responses
    signals, raw_responses = await coord.get_signals_with_reasoning(date, symbol)

    if signals.get('ok', False):
        # Save sentiment reasoning with actual LLM response
        if 'sentiment' in raw_responses:
            sentiment_data = raw_responses['sentiment']
            output_manager.save_llm_reasoning(date, 'sentiment', {
                'score': sentiment_data.get('parsed_data', {}).get('score'),
                'raw_response': sentiment_data.get('raw_response', ''),
                'analysis': sentiment_data.get('analysis', 'No detailed analysis captured'),
                'tools_called': sentiment_data.get('tools_called', []),
                'data_sources': ['alpha_vantage_news', 'newsapi', 'finnhub'],
                'confidence': sentiment_data.get('parsed_data', {}).get('confidence', 0),
                'key_themes': sentiment_data.get('parsed_data', {}).get('key_themes', [])
            })

        # Save technical reasoning with actual LLM response
        if 'technical' in raw_responses:
            tech_data = raw_responses['technical']
            output_manager.save_llm_reasoning(date, 'technical', {
                'indicators': tech_data.get('parsed_data', {}),
                'raw_response': tech_data.get('raw_response', ''),
                'analysis': tech_data.get('analysis', 'No detailed analysis captured'),
                'tools_called': tech_data.get('tools_called', []),
                'data_sources': ['alpha_vantage', 'yahoo_finance'],
                'pattern': tech_data.get('parsed_data', {}).get('pattern', ''),
                'signal_strength': tech_data.get('parsed_data', {}).get('signal_strength', 0)
            })

        # Save coordinator analysis with enhanced details
        output_manager.save_coordinator_analysis(date, {
            'aggregated_signals': signals,
            'raw_responses': raw_responses,
            'synthesis': f"Sentiment: {signals.get('sentiment', {}).get('score', 'N/A')}, " +
            f"MACD Today: {signals.get('technical', {}).get('macd_today', 'N/A')}",
            'timestamp': raw_responses.get('timestamp', ''),
            'symbol': symbol
        })

    return signals


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    start = process_date_param(sys.argv[2]) if len(
        sys.argv) > 2 else "2025-05-01"
    end = process_date_param(sys.argv[3]) if len(
        sys.argv) > 3 else "2025-05-06"

    # Initialize output manager
    output_manager = OutputManager()
    run_dir = output_manager.create_run_directory(symbol, start, end)
    print(f"\n📁 Created organized output directory: {run_dir}")

    # Initialize cache
    cache = MarketDataCache()

    # Try to get data from cache first
    print(f"\nChecking cache for {symbol} from {start} to {end}")
    prices = cache.get(symbol, start, end, "alpha_vantage")

    if prices is None or prices.empty:
        # Use MarketDataTool with Yahoo as the preferred source (no rate limits)
        tool = MarketDataTool(config={"data_source": "yahoo"})
        result = tool.fetch_market_data(
            symbol=symbol,
            start_date=start,
            end_date=end
        )

        if result is None or result.empty:
            print(f"Failed to fetch data for {symbol}")
            output_manager.finalize_run("failed")
            return

        prices = result
        # Cache the data
        cache.set(symbol, start, end, "alpha_vantage", prices)
        print(f"Cached {len(prices)} days of data")
    else:
        print(f"Found {len(prices)} days in cache")

    # Ensure we have a Close column
    if 'Close' not in prices.columns and 'close' in prices.columns:
        prices['Close'] = prices['close']
    elif 'Close' not in prices.columns:
        print("Error: No 'Close' price column found in data")
        output_manager.finalize_run("failed")
        return

    # Ensure index is datetime
    if not isinstance(prices.index, pd.DatetimeIndex):
        if 'date' in prices.columns:
            prices.set_index('date', inplace=True)
        elif 'Date' in prices.columns:
            prices.set_index('Date', inplace=True)

    # Handle timezone-aware datetime conversion
    try:
        prices.index = pd.to_datetime(prices.index, utc=True)
    except:
        prices.index = pd.to_datetime(prices.index)

    # Sort by date
    prices = prices.sort_index()

    print(f"\nBacktesting {symbol} from {start} to {end}")
    print(f"Data points: {len(prices)}")
    print(
        f"Price range: ${prices['Close'].min():.2f} - ${prices['Close'].max():.2f}")

    # Initialize agents
    coord = CoordinatorAgent()
    strat = StrategyAgent()

    # Track portfolio state
    equity = 100_000.0  # Starting cash
    shares = 0
    trades: List[Dict] = []
    equity_curve: List[Dict] = []

    # Track processing statistics
    total_days = len(prices)
    successful_days = 0
    failed_days = 0
    skipped_days = 0

    # Process each day
    for i, (ts, row) in enumerate(prices.iterrows()):
        price = row['Close']
        date_str = ts.date().isoformat()

        # Progress indicator
        print(f"\n--- Processing {i+1}/{total_days} days: {date_str} ---")
        print(f"Price: ${price:.2f}")

        try:
            # Get signals with reasoning capture
            sigs = asyncio.run(get_signals_with_reasoning(
                coord, date_str, symbol, output_manager))

            # Validate signals
            sentiment_data = sigs.get('sentiment', {})
            technical_data = sigs.get('technical', {})

            if not sigs.get('ok', False):
                print(
                    f"⚠️  Skipping {date_str}: Error in signals - {sigs.get('error', 'Unknown error')}")
                skipped_days += 1
                continue

            if not sentiment_data or sentiment_data.get('score') is None:
                print(f"⚠️  Skipping {date_str}: Missing sentiment data")
                skipped_days += 1
                continue

            if not technical_data or technical_data.get('macd_today') is None:
                print(f"⚠️  Skipping {date_str}: Missing technical data")
                skipped_days += 1
                continue

            print(
                f"Signals received: sentiment={sentiment_data}, technical={technical_data}")

            # Make trading decision
            decision = strat.decide_trade(
                sigs, price=float(price), trade_date=date_str)
            print(f"Decision: {decision}")

            # Save trading decision with reasoning
            output_manager.save_trading_decision(date_str, {
                'action': decision.get('action', 'HOLD'),
                'reasoning': decision.get('reasoning', ''),
                'conditions_met': decision.get('conditions_met', {}),
                'price': float(price),
                'signals': sigs
            })

            qty = decision.get("qty", 100)

            # Execute trades
            if decision.get("action") == "BUY" and equity >= price * qty:
                equity -= price * qty
                shares += qty
                trades.append({
                    "date": date_str,
                    "action": "BUY",
                    "price": float(price),
                    "qty": qty,
                    "sentiment": sentiment_data.get('score', 0),
                    "macd_today": technical_data.get('macd_today', 0),
                    "reasoning": decision.get('reasoning', '')
                })
                print(f"✅ Executed BUY: {qty} shares @ ${price:.2f}")

            elif decision.get("action") == "SELL" and shares > 0:
                sell_value = price * shares
                equity += sell_value
                trades.append({
                    "date": date_str,
                    "action": "SELL",
                    "price": float(price),
                    "qty": shares,
                    "sentiment": sentiment_data.get('score', 0),
                    "macd_today": technical_data.get('macd_today', 0),
                    "reasoning": decision.get('reasoning', '')
                })
                print(
                    f"✅ Executed SELL: {shares} shares @ ${price:.2f} = ${sell_value:.2f}")
                shares = 0

            # Update equity curve
            current_value = equity + shares * price
            equity_curve.append({
                "date": date_str,
                "equity": current_value,
                "shares": shares,
                "price": float(price)
            })

            # Update strategy agent's equity curve
            strat.update_equity_curve(date_str, current_value, float(price))

            successful_days += 1

        except Exception as e:
            print(f"   Error processing {date_str}: {str(e)}")
            print(f"   Exception type: {type(e).__name__}")
            traceback.print_exc()
            failed_days += 1

            # Still update equity curve
            current_value = equity + shares * price
            equity_curve.append({
                "date": date_str,
                "equity": current_value,
                "shares": shares,
                "price": float(price),
                "error": True
            })

            # Update strategy agent's equity curve even on error
            strat.update_equity_curve(date_str, current_value, float(price))
            continue

    # Calculate final statistics
    final_value = equity + shares * prices.iloc[-1]['Close']
    initial_value = 100_000.0
    total_return = (final_value - initial_value) / initial_value * 100

    print("\n" + "="*60)
    print(f"BACKTEST SUMMARY: {symbol}")
    print(f"Period: {start} to {end}")
    print("="*60)

    print(f"\nProcessing Statistics:")
    print(f"  Total days: {total_days}")
    print(
        f"  Successful: {successful_days} ({successful_days/total_days*100:.1f}%)")
    print(f"  Failed: {failed_days} ({failed_days/total_days*100:.1f}%)")
    print(f"  Skipped: {skipped_days} ({skipped_days/total_days*100:.1f}%)")

    print(f"\nPerformance:")
    print(f"  Initial equity: ${initial_value:,.2f}")
    print(f"  Final equity: ${final_value:,.2f}")
    print(f"  Total return: {total_return:+.2f}%")
    print(f"  Final shares held: {shares}")

    # Save data files to organized structure
    data_dir = run_dir / "data"

    if trades:
        print(f"\nTrade Summary:")
        print(f"  Total trades: {len(trades)}")
        trades_df = pd.DataFrame(trades)
        buys = trades_df[trades_df['action'] == 'BUY']
        sells = trades_df[trades_df['action'] == 'SELL']
        print(f"  Buys: {len(buys)}")
        print(f"  Sells: {len(sells)}")

        print("\nDetailed Trades:")
        print(trades_df.to_string(index=False))

        # Save trades
        trades_df.to_csv(data_dir / "trades.csv", index=False)
        print(f"\n✅ Trades saved to: {data_dir / 'trades.csv'}")
    else:
        print("\n No trades executed")

    # Save equity curve
    if equity_curve:
        equity_df = pd.DataFrame(equity_curve)
        equity_df.to_csv(data_dir / "equity.csv", index=False)
        print(f"✅ Equity curve saved to: {data_dir / 'equity.csv'}")

    # Calculate and save metrics
    metrics = strat.calculate_metrics(initial_capital=initial_value)
    strat.print_metrics_summary(metrics)

    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(data_dir / "metrics.csv", index=False)
    print(f"\n✅ Metrics saved to: {data_dir / 'metrics.csv'}")

    # Generate executive summary
    print("\n📊 Generating executive summary...")
    summary = output_manager.generate_executive_summary(metrics)
    print(
        f"✅ Executive summary saved to: {run_dir / 'reports' / 'executive_summary.md'}")

    # Extract best insights
    print("\n🔍 Extracting best insights...")
    best_insights = output_manager.extract_best_insights()
    print(
        f"✅ Best insights saved to: {run_dir / 'analysis' / 'best_insights.json'}")

    # Generate run summary using the new helper function
    print("\n📝 Generating run summary...")
    save_run_summary(symbol, metrics, trades, best_insights,
                     str(run_dir / 'reports'))

    # Generate enhanced executive summary using ReportGenerator
    print("\n🎯 Generating enhanced executive summary...")
    report_gen = ReportGenerator()
    enhanced_summary = report_gen.generate_executive_summary(run_dir, metrics)
    enhanced_summary_path = run_dir / 'reports' / 'executive_summary_enhanced.md'
    enhanced_summary_path.write_text(enhanced_summary)
    print(f"✅ Enhanced executive summary saved to: {enhanced_summary_path}")

    # Extract best LLM examples
    print("\n🏆 Extracting best LLM analysis examples...")
    llm_examples = report_gen.extract_llm_examples(run_dir, num_examples=5)
    examples_path = run_dir / 'analysis' / 'best_llm_examples.json'
    with open(examples_path, 'w') as f:
        json.dump(llm_examples, f, indent=2, default=str)
    print(f"✅ Best LLM examples saved to: {examples_path}")

    # Print summary of examples found
    for category, examples in llm_examples.items():
        if examples:
            print(
                f"  - {category}: {len(examples)} high-quality examples extracted")

    # Finalize run
    output_manager.finalize_run("completed")

    print(f"\n🎯 Complete organized output saved to: {run_dir}")
    print("\nOrganized structure includes:")
    print("  📁 data/          - Trade, equity, and metrics CSV files")
    print("  📁 analysis/      - Daily LLM reasoning and agent responses")
    print("  📁 reports/       - Executive summary and detailed analysis")
    print("  📄 metadata.json  - Run metadata and configuration")


if __name__ == "__main__":
    main()
