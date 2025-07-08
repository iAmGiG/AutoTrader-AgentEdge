# Sentiment Agent Refactoring Plan

## Current Issues

1. **Hard-coded Narratives**: The agent currently uses fixed templates for market behavior explanations, limiting flexibility and making the code complex.

2. **Incorrect Tool Usage Flow**: The agent pre-determines which tools to call rather than letting the LLM decide based on the query.

3. **Large Monolithic Class**: The SentimentAgent class has grown too large, handling too many responsibilities.

4. **Embedded System Prompt**: The system prompt is hard-coded in the agent, making it difficult to update.

5. **Limited LLM Integration**: The current implementation doesn't fully utilize the LLM's capabilities for generating narratives.

## Refactoring Goals

1. **True LLM-Driven Tools**: Let the LLM decide which tools to call based on the query.

2. **Dynamic Narrative Generation**: Let the LLM generate the narrative based on the data, not pre-defined templates.

3. **Modular Architecture**: Break down the SentimentAgent into smaller, focused components.

4. **Externalized Configuration**: Move system prompts to external JSON configuration files.

5. **Enhanced Testing**: Create proper tests that simulate the complete LLM-driven flow.

## Implementation Plan

### 1. External Configuration

Create two new configuration files:

- `config/agent_prompts.json`: Store system prompts for all agents
- `config/agent_templates.json`: Store any reusable message templates

Example `agent_prompts.json`:

```json
{
  "sentiment_agent": {
    "system_prompt": "You are the Sentiment Agent, a specialized assistant designed to...",
    "tool_description": "This agent uses the following tools: fetch_news, fetch_market_data...",
    "default_response": "I can help with analyzing market sentiment and generating explanations..."
  },
  "other_agents": {
    ...
  }
}
```

### 2. Simplified Agent Structure

Refactor the SentimentAgent to focus on:

- Loading configuration
- Registering tools with AutoGen
- Routing messages to and from the LLM

```python
class SentimentAgent(BaseAgent):
    def __init__(self, name="SentimentAgent", memory_system=None):
        # Load configurations
        self.config = self._load_agent_config("sentiment_agent")
        self.market_sectors = self._load_market_sectors()
        
        # Register tools with AutoGen
        tools = self._register_tools()
        
        # Initialize base agent with system prompt from config
        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=SENTIMENT_LLM_CONFIG,
            system_message=self.config["system_prompt"]
        )
    
    def _load_agent_config(self, agent_key):
        """Load agent configuration from external files"""
        # Implementation...
    
    def _register_tools(self):
        """Register all available tools for this agent"""
        # Implementation...
    
    def generate_reply(self, messages, context=None):
        """Main entry point for AutoGen message processing"""
        # Let AutoGen and the LLM handle tool selection and execution
        # Return the LLM's response directly
```

### 3. Data Processing Utilities

Move data processing logic to utility classes:

```python
class SentimentDataProcessor:
    """Process news and market data for sentiment analysis"""
    
    @staticmethod
    def preprocess_news(news_data):
        """Process news data and extract sentiment"""
        # Implementation...
    
    @staticmethod
    def preprocess_market_data(market_data):
        """Process market data and extract trends"""
        # Implementation...

class QueryParser:
    """Parse user queries to extract topics, sectors, and dates"""
    
    @staticmethod
    def extract_query_details(message, market_sectors):
        """Extract details from a user query"""
        # Implementation...
```

### 4. True LLM-Driven Tool Calling

Instead of pre-determining which tools to call, pass the query to the LLM and let it decide:

```python
def generate_reply(self, messages, context=None):
    if not messages:
        return self.config["default_response"]
    
    last_message = messages[-1]
    
    # The model will now decide which tools to use based on the query
    # This is handled by AutoGen's function calling capabilities
    return super().generate_reply(messages, context)
```

### 5. Narrative Generation

Remove all hard-coded narrative templates and let the LLM generate narratives based on data:

```python
def format_data_for_llm(self, data):
    """Format data to be passed to the LLM for narrative generation"""
    # Prepare a structured format with all available data
    formatted_data = {
        "news_sentiment": {
            "average_score": data.get("sentiment_score"),
            "sample_headlines": data.get("headlines", [])[:3],
            "article_count": data.get("article_count", 0)
        },
        "market_data": {
            "ticker": data.get("ticker"),
            "price_change": data.get("price_change"),
            "latest_price": data.get("latest_price"),
            "volume": data.get("volume")
        },
        "sector_context": {
            "sector": data.get("sector"),
            "etfs": data.get("etfs", []),
            "blue_chips": data.get("blue_chips", [])
        }
    }
    
    # The formatted data will be passed to the LLM
    # The LLM will generate a complete narrative based on this data
    return formatted_data
```

## Testing Approach

Create two types of tests:

1. **Unit Tests**: Test individual components (QueryParser, SentimentDataProcessor, etc.)

2. **Integration Tests**: Test the complete LLM-driven flow with mock LLM responses

For integration tests, use a mock LLM that simulates the function calling behavior:

```python
class MockLLM:
    def generate_reply(self, messages, available_tools):
        # Simulate LLM deciding which tools to call based on the message
        # Return a simulated response
```

## Implementation Timeline

1. Create external configuration files
2. Implement utility classes for data processing
3. Refactor SentimentAgent to use LLM-driven tools
4. Implement testing framework
5. Validate with real-world queries

## Benefits

1. **More Flexible**: LLM-generated narratives will be more adaptable and context-aware
2. **Easier Maintenance**: Smaller, focused components are easier to understand and update
3. **Better Scalability**: New tools and data sources can be added without changing core agent logic
4. **Improved Testing**: Modular components enable better test coverage
5. **Enhanced User Experience**: More natural, contextual responses for complex queries
