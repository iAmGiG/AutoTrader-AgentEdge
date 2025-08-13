# RH2MAS Terminology & Acronyms

## Agent Acronyms

- **TA** = Technical Agent (analyzes price patterns, volume, technical indicators)
- **SA** = Sentiment Agent (analyzes news sentiment and market psychology)
- **RA** = Risk Agent (evaluates portfolio risk and position sizing)
- **Strategy Agent** = Makes final trading decisions based on inputs from other agents
- **MAS** = Multi-Agent System (the overall system architecture)

## Stock & Market Terms

- **MAG7** = Magnificent Seven stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
- **MACD Histogram** = Difference between MACD line and signal line
- **Signal Strength** = Normalized score (0-1) indicating entry quality
- **Market Heat** = Composite score of market conditions (VXX, SPY momentum, sector rotation)

## System Architecture Terms

- **FunctionTool** = AutoGen wrapper for external functions/APIs
- **BaseAgent** = Parent class for all trading agents
- **DataObfuscator** = Tool for validating LLM decisions without training data leakage
- **ParallelStrategyTester** = Framework for comparing Buy & Hold vs Mechanical vs LLM strategies

## File Extensions & Formats

- **`.cache/backtests/`** = Directory for backtest results and cached data
- **`.cache/market_data/`** = Cached market data from various APIs
- **`_yy_mm_dd.md`** = Standard naming convention for reports (e.g., `validation_25_07_29.md`)
