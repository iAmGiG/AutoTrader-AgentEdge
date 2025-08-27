# Troubleshooting Guide

## Common Import Errors

### `ImportError for autogen_ext`

- **Solution**: Ensure you're using the AutoGen conda environment
- **Command**: `conda activate AutoGen`

### `AttributeError for model_client`

- **Issue**: model_client not stored as class attribute in BaseAgent
- **Solution**: Ensure model_client is stored as class attribute in BaseAgent initialization

## Tool Execution Errors

### `'FunctionTool' object is not callable`

- **Issue**: Calling tool directly instead of its function
- **Solution**: Use `tool.func(**args)` instead of `tool(**args)`

### `'str' object has no attribute 'get'`

- **Issue**: Tool arguments need JSON parsing
- **Solution**: Parse arguments with `json.loads(tool_args)` before use

### `Input should be a valid string [type=string_type]`

- **Issue**: Result must be converted to string for LLM
- **Solution**: Convert results to string before returning FunctionExecutionResult

### Empty search_terms in SEC tool

- **Solution**: The `search_sec_filings` tool now handles empty search terms gracefully

## Data Type Errors

### `Object of type 'DataFrame' is not JSON serializable`

- **Solution**: Convert DataFrames to dict before serializing
- **Method**: `df.to_dict(orient='records')` then `json.dumps(result_dict)`

### `Object of type 'float64' is not JSON serializable`

- **Solution**: Convert numpy types to Python native types before serialization

## Cache System Issues

### Cache Fragmentation

- **Issue**: Multiple small cache files for same symbol/date range causing incomplete data
- **Symptoms**: Backtests showing date jumps (e.g., Jan → June), missing trading days
- **Solution**: Run cache consolidation scripts, ensure UnifiedCacheManager uses consolidated files
- **Prevention**: Use UnifiedCacheManager for all market data access

### Incomplete Daily Values in Results

- **Issue**: Results files only showing last 50 days instead of full year
- **Symptoms**: daily_values array truncated despite checkpoint having all days
- **Solution**: Fixed in simple_continuous_backtest.py - remove [-50:] slice
- **Verification**: Check len(results['daily_values']) equals trading days count

### Cache File Not Found

- **Issue**: UnifiedCacheManager not finding consolidated cache files
- **Symptoms**: "No cache found" despite files existing
- **Solution**: Update pattern matching to include both regular and _consolidated.json files
- **Code Fix**: See src/tools/cache/unified_cache.py lines 209-211

### Monthly Backtests Failing

- **Issue**: Cache validation rejecting valid monthly data (< 200 days)
- **Symptoms**: Month-specific backtests fail with "No market data available"
- **Solution**: Dynamic threshold based on requested date range (fixed in unified_cache.py)
- **Calculation**: min_threshold = max(expected_days * 0.5, 5)

## API and Data Issues

### Empty DataFrames

- **Check**: Dependencies are properly installed and API keys are configured
- **Location**: API keys should be in `config/config.json` (not in repo)

### Alpha Vantage API Limits

- **Limits**: 5 calls/minute, 500 calls/day
- **Solution**: Use caching extensively, consider FMP as alternative

### Module Import Issues

- **Solution**: Run test files from project root directory
- **Verification**: `import autogen_core; print(autogen_core.__file__)`

## Package and Environment Issues

### Package Conflicts

- **Solution**: Ensure using autogen-core 0.6.x from conda environment
- **Required packages**: autogen-core 0.6.4, autogen-agentchat 0.6.4

### Missing Dependencies

- **Solution**: All optional dependencies use lazy imports to handle missing packages gracefully
- **Install**: Use `pip install -e .` to install all dependencies

## Tool-Specific Issues

### Multi-Source Data Fallback

- **Primary**: Alpha Vantage (25 calls/day limit)
- **Secondary**: FMP (Financial Modeling Prep)
- **Tertiary**: NASDAQ Data Link

### Date Parsing Issues

- **Finnhub**: Fixed date handling in unified news tool for Finnhub responses
- **General**: Use `date_utils.py` for consistent date handling

## Performance Issues

### API Rate Limits

- **Solution**: Use intelligent backtest service with automatic rate limit management
- **Files**:
  - Service progress: `.cache/backtests/service_progress.json`
  - Service logs: `.cache/backtests/service.log`

### Cache Efficiency

- **News Cache**: 7-day expiry, filters by relevance score (≥ 0.5)
- **Market Data Cache**: 24-hour expiry, stores as JSON with metadata
- **Hit Rate**: Should achieve 70%+ cache efficiency
