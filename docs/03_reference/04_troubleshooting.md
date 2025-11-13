# Troubleshooting Guide

## AutoGen Framework Issues

### `ImportError for autogen_ext` or `autogen_agentchat`

- **Solution**: Ensure you're using the AutoGen conda environment
- **Command**: `conda activate AutoGen-TradingSystem`
- **Verify**: `python -c "import autogen_agentchat; print('AutoGen available')"`

### `AttributeError for model_client` in AutoGen Agents

- **Issue**: model_client not properly initialized in BaseAgent
- **Solution**: Check `src/autogen_agents/base_agent.py` initialization
- **Verify**: Ensure OpenAI client is properly configured for agents

## AutoGen Tool Integration Errors

### `'FunctionTool' object is not callable`

- **Issue**: Incorrect tool usage in AutoGen agents
- **Solution**: Use proper AutoGen tool registration in BaseAgent
- **Example**: Check `src/autogen_agents/base_agent.py` tool setup

### VoterAgent MACD/RSI Calculation Errors

- **Issue**: Missing trading_tools imports or data format issues
- **Solution**: Verify `src/trading_tools/indicators.py` imports work
- **Test**: `python -c "from src.trading_tools.indicators import calculate_macd, calculate_rsi; print('Indicators available')"`

### AutoGen Agent Communication Failures

- **Issue**: Agents not properly inheriting from BaseAgent
- **Solution**: Ensure all agents extend `src/autogen_agents/base_agent.py`
- **Check**: Agent initialization and tool registration

## Data Type Errors

### `Object of type 'DataFrame' is not JSON serializable`

- **Solution**: Convert DataFrames to dict before serializing
- **Method**: `df.to_dict(orient='records')` then `json.dumps(result_dict)`

### `Object of type 'float64' is not JSON serializable`

- **Solution**: Convert numpy types to Python native types before serialization

## Cache System Issues (Still Relevant)

### Cache Issues (SQLite-Based)

- **Issue**: Cache misses or incomplete data
- **Symptoms**: VoterAgent backtests showing date jumps, missing trading days
- **Solution**: Use TradingCacheManager (SQLite) for all AutoGen agent market data access
- **Prevention**: Ensure agents use `src/data_sources/tools.py` for data fetching
- **Check Cache**: Run `python scripts/cache_manager.py stats` to verify cache health

### VoterAgent Data Access Issues

- **Issue**: VoterAgent not finding market data for MACD/RSI calculations
- **Symptoms**: "No market data available" despite cache containing data
- **Solution**: Verify TradingCacheManager integration and cache hits
- **Debug**: Check `python scripts/cache_manager.py query SYMBOL --start DATE --end DATE`
- **Code**: Check `src/autogen_agents/voter_agent.py` data fetching logic

### Market Data Format Issues

- **Issue**: MACD/RSI calculations failing due to data format mismatches
- **Symptoms**: Pandas DataFrame issues, column name mismatches
- **Solution**: Ensure data normalization through `src/trading_tools/indicators.py`
- **Verification**: Test individual indicator functions before agent integration

## API and Data Issues

### Empty DataFrames

- **Check**: Dependencies are properly installed and API keys are configured
- **Location**: API keys should be in `config/config.json` (not in repo)

### Alpha Vantage API Limits

- **Limits**: 5 calls/minute, 500 calls/day
- **Solution**: Use caching extensively, consider FMP as alternative

### Module Import Issues

- **Solution**: Run AutoGen agent tests from project root directory
- **Verification**: `python -c "from src.autogen_agents.voter_agent import VoterAgent; print('VoterAgent import successful')"`
- **Environment**: Ensure `conda activate AutoGen-TradingSystem`

## Package and Environment Issues

### AutoGen Package Conflicts

- **Solution**: Ensure using autogen-agentchat and autogen-ext packages
- **Required packages**: autogen-agentchat 0.6.x, autogen-ext, openai
- **Install**: `pip install autogen-agentchat autogen-ext openai`

### Missing AutoGen Dependencies

- **Solution**: Install complete AutoGen stack
- **Install**: Use `pip install -e .` to install all dependencies
- **Verify**: `python -c "from autogen_agentchat.agents import AssistantAgent; print('AutoGen working')"`

## Tool-Specific Issues

### AutoGen Agent Market Data Sources

- **Primary**: Alpaca Markets (official SDK, real-time and historical)
- **Secondary**: Polygon.io API (historical data, used by VoterAgent for MACD/RSI)
- **Tertiary**: Alpha Vantage (fallback, 25 calls/day limit)
- **Cache**: TradingCacheManager (SQLite) reduces API calls by 90%+ with 8-10x query performance

### AutoGen Agent Date/Time Issues

- **VoterAgent**: Ensure proper date range formatting for market data requests
- **General**: Use consistent YYYY-MM-DD format across all agents
- **Timezone**: Market data cache handles timezone conversion automatically

## Performance Issues

### AutoGen Agent Performance

- **VoterAgent**: Optimized MACD+RSI calculations with SQLite caching
- **Cache Hit Rate**: Should achieve 90%+ with TradingCacheManager (8-10x faster than file-based)
- **Parallel Processing**: Multiple agents can run concurrently via TradingOrchestrator
- **Cache Maintenance**: Run `python scripts/cache_manager.py cleanup` weekly to remove expired data

### API Rate Limits (Current System)

- **Polygon API**: 5 calls/minute (primary data source for VoterAgent)
- **Alpaca API**: 200 requests/minute (for live trading integration)
- **Cache Strategy**: Intelligent caching reduces API usage by 90%+
- **Solution**: Use cache-first approach in all AutoGen agents

### AutoGen Agent Memory Usage

- **VoterAgent**: Lightweight, only loads necessary market data
- **BaseAgent**: Efficient tool registration and memory management
- **Monitoring**: Use `python -m memory_profiler` for agent performance testing
