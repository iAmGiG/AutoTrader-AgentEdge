# Advanced Metrics System

The Advanced Metrics System provides comprehensive analysis capabilities for backtest results through two main components:

1. **MetricsAnalyzer**: Analyzes existing JSON backtest results
2. **MetricsCapture**: Real-time metrics collection during backtesting (for future tests)

## Quick Start

### Analyze Existing Results

```bash
# Run comprehensive analysis on all V0-V4 results
python scripts/generate_results_summary.py --advanced

# Or use the analyzer directly
python src/analysis/metrics_analyzer.py
```

### Generated Reports

The analysis generates three types of outputs:

1. **Comprehensive JSON Report** (`reports/backtest_analysis_2024.json`)
   - Individual ticker/strategy analysis
   - Sentiment effectiveness by bucket
   - Trade quality metrics
   - Risk-adjusted performance
   - Market regime analysis

2. **Strategy Comparison CSV** (`reports/strategy_comparison_2024.csv`)
   - Comparative metrics across all strategies
   - Ready for spreadsheet analysis and visualization

3. **Continuation States** (`reports/continuation_states_2025/`)
   - Final portfolio states for each ticker/strategy after 2024
   - Ready to continue backtesting into 2025

## MetricsAnalyzer Features

### Sentiment Effectiveness Analysis
Groups trades by sentiment ranges and analyzes performance:
- **Very Bearish**: 0.0-0.3 sentiment
- **Bearish**: 0.3-0.5 sentiment  
- **Neutral**: 0.5-0.7 sentiment
- **Bullish**: 0.7-1.0 sentiment

For each bucket, calculates:
- Total trades, win rate, average return
- Best and worst individual trades
- Total bucket contribution

### Trade Quality Metrics
- **Holding Periods**: Average, min, max days per trade
- **Profit Factor**: Total wins / Total losses
- **Win/Loss Analysis**: Largest winner/loser, avg winner/loser ratio
- **Streak Analysis**: Consecutive wins and losses

### Risk-Adjusted Performance
- **Maximum Drawdown**: Peak-to-trough portfolio decline
- **Drawdown Duration**: Longest underwater period
- **Calmar Ratio**: Annualized return / Max drawdown
- **Recovery Factor**: Total return / Max drawdown
- **Sharpe Ratio**: Risk-adjusted returns (using 2% risk-free rate)

### Market Regime Analysis
Detects bull/bear markets using 50-day vs 200-day moving averages:
- Strategy performance during bull markets
- Strategy performance during bear markets  
- Win rate differences by regime

### Strategy Comparison
Ranks V0-V4 strategies across multiple metrics:
- Total return, Sharpe ratio, Calmar ratio
- Identifies best strategy per ticker
- Generates summary statistics

## MetricsCapture Features (Future Integration)

For integration with future backtests, MetricsCapture provides real-time tracking:

### Enhanced Trade Tracking
- Entry/exit sentiment comparison
- MACD histogram values for trend strength
- VWAP distance at trade entry
- 5-day and 20-day volatility at entry

### Real-Time Risk Monitoring
- Current drawdown from peak
- Days since portfolio high
- Running high water mark
- Rolling 30-day Sharpe ratio

### Market Regime Detection  
- Live bull/bear regime identification
- Performance tracking by regime
- Regime transition detection

### Position Analysis
- Position concentration monitoring
- Sentiment-based position sizing effectiveness
- Rolling return calculations (30d, 90d, YTD)

## Integration with Existing Framework

### Using MetricsAnalyzer

```python
from src.analysis.metrics_analyzer import MetricsAnalyzer

# Initialize analyzer
analyzer = MetricsAnalyzer()

# Analyze all results
analysis = analyzer.analyze_all_results()

# Save reports
analyzer.save_analysis_report(analysis)
analyzer.save_comparison_csv(analysis) 
analyzer.save_checkpoints(analysis)

# Access specific insights
best_strategies = analysis['best_strategy_per_ticker']
strategy_rankings = analysis['strategy_rankings']
```

### Future Integration with MetricsCapture

```python
from src.analysis.metrics_capture import MetricsCapture

# Initialize for a backtest
metrics = MetricsCapture(symbol='AAPL', initial_cash=100000)

# During backtesting loop
metrics.update_daily_data(
    date='2024-01-02',
    portfolio_value=portfolio_value,
    cash=cash,
    position=position,
    stock_price=stock_price,
    sentiment=sentiment,
    volume=volume  # optional
)

# When executing trades
metrics.record_trade(
    date='2024-01-02',
    action='BUY',
    price=185.0,
    shares=500,
    sentiment=0.7,
    macd_signal='1',
    portfolio_value=portfolio_value
)

# Export enhanced results
enhanced_results = metrics.export_enhanced_results()
```

## Key Insights from Current Analysis

Based on the V0-V4 analysis:

### Strategy Performance Rankings
1. **V0 (Baseline)**: 36.39% average return - Pure MACD often competitive
2. **V4 (LLM)**: 31.66% average return - Strong performance with intelligent sentiment
3. **V1 (News)**: 20.31% average return - VADER sentiment from news
4. **V3 (Combined)**: 18.24% average return - Heuristic combination
5. **V2 (VXX Fear)**: 15.38% average return - Volatility-based sentiment

### Best Strategy by Ticker (Sharpe Ratio)
- **NVDA**: V4 (Sharpe: 2.319) - LLM excels with high-volatility tech
- **META**: V2 (Sharpe: 1.931) - VXX fear signals effective
- **TSLA**: V3 (Sharpe: 1.823) - Combined approach works well
- **GOOGL**: V1 (Sharpe: 1.169) - News sentiment effective
- **AMZN**: V0 (Sharpe: 1.084) - Baseline strong for large-cap
- **SPY**: V0 (Sharpe: 0.681) - Pure MACD good for broad market
- **AAPL**: V2 (Sharpe: 0.513) - VXX signals help with mega-cap
- **MSFT**: V4 (Sharpe: 0.363) - LLM provides slight edge

### Sentiment Effectiveness Patterns
- **Bullish Sentiment** (0.7-1.0): Higher win rates but fewer trades
- **Neutral Sentiment** (0.5-0.7): Balanced performance, most consistent
- **Bearish Sentiment** (0.3-0.5): Lower win rates but can capture downside protection
- **Very Bearish** (0.0-0.3): Limited samples, mixed results

## File Structure

```
src/analysis/
├── metrics_analyzer.py     # Analyze existing results
├── metrics_capture.py      # Real-time metrics (future)
└── __init__.py

scripts/
└── generate_results_summary.py       # Enhanced with --advanced flag

reports/
├── backtest_analysis_2024.json      # Comprehensive analysis
├── strategy_comparison_2024.csv     # Comparative metrics
└── V0-V4_Framework_Results.md       # Summary report

reports/continuation_states_2025/
├── AAPL_V0_2024_01_01_to_2024_12_31_continuation_state.json
├── AAPL_V1_2024_01_01_to_2024_12_31_continuation_state.json
└── ...                             # All 40 combinations
```

## Next Steps

1. **Current**: Use MetricsAnalyzer to analyze existing V0-V4 results
2. **Future**: Integrate MetricsCapture into backtesting framework for real-time metrics
3. **Enhancement**: Add visualization capabilities for generated reports
4. **Expansion**: Extend analysis to additional timeframes and assets

The system provides a foundation for comprehensive quantitative analysis of trading strategies with particular focus on sentiment effectiveness and risk-adjusted performance measurement.