# Sentiment Agent - Future Work

## Current Implementation

The enhanced Sentiment Agent now includes:

1. **External Configuration Storage**
   - Market sectors, tickers, and ETFs stored in JSON
   - Easily extensible to add new sectors, keywords, or instruments
   - Separation of code and data for better maintainability

2. **Advanced Natural Language Understanding**
   - Topic extraction from complex queries
   - Sector recognition using keyword matching
   - Default handling for date ranges (5-day default)
   - Support for queries without explicit tickers or sectors

3. **Combined Data Analysis**
   - Integration of news sentiment and price movements
   - ETF data inclusion for broader sector context
   - Leveraged ETF support for institutional trend signals

4. **Improved Market Behavior Explanations**
   - Cause-and-effect narratives in plain language
   - Detection of alignment/misalignment between sentiment and price
   - Disclaimers about data limitations and interpretation certainty
   - Reduced Austrian economics terminology for broader accessibility

## Future Improvements

1. **Enhanced Query Understanding**
   - Implement a proper NLP pipeline for entity extraction
   - Add more sophisticated date parsing for complex time ranges
   - Support for comparison queries (e.g., "Compare tech vs energy sentiment")

2. **Additional Data Sources**
   - Integrate FRED economic indicators for macro context
   - Add SEC filings for fundamental analysis
   - Support bond yield and dollar index for cross-asset correlation
   - Add options data to incorporate market expectations

3. **Performance Optimization**
   - Cache frequently accessed sector/ticker data
   - Implement parallel data fetching for multiple sources
   - Add request debouncing to manage API rate limits
   - Cache recent API responses for common queries

4. **Response Quality**
   - Fine-tune the LLM system prompt for better narratives
   - Add visual representations (charts, tables) of sentiment/price data
   - Include customizable response detail levels
   - Support for time series sentiment analysis

5. **Integration with Other Agents**
   - Standardize interfaces for Strategy and Risk agents
   - Implement a structured output format for agent consumption
   - Add metadata to responses for machine readability
   - Support for targeted queries from other agents

## Technical Debt to Address

1. **Code Structure**
   - Review circular import issues in data tools
   - Separate data fetching from processing logic
   - Implement proper error handling and rate limit management
   - Add comprehensive unit tests for each component

2. **Configuration Management**
   - Move API keys to secure storage
   - Implement versioning for sector configurations
   - Add validation for configuration files
   - Support for hot-reloading of configurations

3. **Documentation**
   - Document the query language capabilities
   - Add examples of different query types
   - Create developer documentation for extending the agent
   - Document integration points with other agents