# How is News Data Currently Stored and Processed?

- Current State:
  - The NewsHeadlineTool fetches data from the API and returns it as a list of dictionaries (each dictionary representing one article). For testing and basic processing, this raw structure is sufficient.

- For LLM Prompts:
  - Since LLMs generally expect text, you may not need a DataFrame at all for text-based prompts. You can simply extract and concatenate the headlines, descriptions, or full article texts into a single string or a list of strings to pass into the LLM.

**considering** to use data frames regardless.

## Merging Numeric Market Data with Text-Based News

**Current Approach:**

- Numeric Market Data: The MarketDataTool currently returns data as a Pandas DataFrame (which is well-suited for time-series analysis and numeric computations).
- Text News Data: The NewsHeadlineTool returns a list of dictionaries (raw text), which works well for generating prompts for an LLM.

## Unifying Data from Multiple Tools Before Sending to the LLM

- Current Status:
- No concrete logic has been implemented yet for merging outputs from the NewsHeadlineTool and MarketDataTool. The integration layer (likely within your DecisionEngine or a new aggregator module) hasn't been defined.

- Future Considerations:
- Aggregation Strategy:
- Develop an integration module that collects outputs from each tool (e.g., sentiment signals, numeric indicators) and fuses them into a comprehensive context.
  - Summarizing each data stream: Generate meta-tokens or summaries (e.g., "HIGH_VOLATILITY" from market data, "NEGATIVE_SENTIMENT" from news).
  - Aligning by Timestamp: If data is time-stamped, align news and market data for the same period.
  - Concatenating Information: Create a combined text prompt that includes both numeric insights (converted to natural language if needed) and raw text or summarized headlines.
- Example Process Flow:

    1. Fetch Data: Each agent retrieves its data (news articles, market prices).
    2. Preprocess Data: Each tool or agent processes its data to extract key metrics (e.g., sentiment score, market trends).
    3. Aggregate Results: An aggregator (or DecisionEngine) collects these results and formats them into a unified prompt (or data structure) for the LLM to generate recommendations.
- Design Consideration:
  - Focus on making this integration layer modular so that you can later refine how the outputs are merged without having to rework the core tools or agents.

### why use a DataFrame strucutre

1. integration and future devlopemtn:
    - consitencye: the data frame can privide a consisten way ot store bot hte numberi market data nad text-ased news data. so mergin, processing, and align datasets by common keys becomes a feature.
    - meta-token generation: genraign meta-tokens, sentiment scores, or other summary metrics directly within the dtaframe becomes a feature. aiding the decision engine in aggregating the diverse signals.
    - extensiblity: as we add to the system, pulling in new data streams and xomplex processing, the nature will already be strealined with the tool's ouptu bineg the data strucutre.
2. enhanced tooling and analysis:
    - data manipulation: pandas gives the power of data manipulation and aggregation functions, simplying the process of cleaing and summarizing data before passing it to the LLM engine.
    - alignment of data streams: with dataframes, we can align time-series data from market sources with timestapped news articles, this way agents are processing synchronized inputs.

### LLM considerations

1. LLM Prompt Complexity:
    - Increased Token Count: Using a structured DataFrame may lead to more complex prompt formatting when converting the data into text. This could potentially increase LLM usage costs.
    - Balance Needed: While there might be a trade-off in prompt size, the benefits in modularity and data integration can outweigh the cost—at least until a more optimized method is made.
2. Cost vs. Development Efficiency:
    - Short-Term vs. Long-Term Gains: Although a more compact text prompt might save on token usage costs, the development efficiency and the ability to quickly integrate multiple data streams are key. In the long run, a uniform structure allows you to iterate faster and scale your system more effectively.
    - Future Optimizations: Once your pipeline is in place, you could explore strategies to compress or summarize the DataFrame data further before generating LLM prompts, potentially mitigating the cost concerns.
