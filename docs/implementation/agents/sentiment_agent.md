# Sentiment Agent Documentation

## 1. Overview

The Sentiment Agent analyzes market data and news sentiment to provide insights about market behavior. It uses LLM-driven function calling to decide which data sources to query based on the user's question.

### Key Capabilities

- Fetches and analyzes news articles and their sentiment
- Retrieves market data for stocks and sectors
- Generates explanatory narratives about market behavior
- Integrates with the broader RH2MAS multi-agent system

## 2. Architecture

### Component Diagram

For detailed component diagrams, see the UML diagrams in:

- [docs/UML/SentimentAgent/sentimentAgentSystemDataFlow.svg](./UML/SentimentAgent/sentimentAgentSystemDataFlow.svg)
- [docs/UML/SentimentAgent/sentimentAgentSystemSequenceDiagram.svg](./UML/SentimentAgent/sentimentAgentSystemSequenceDiagram.svg)

### Data Flow

1. User query is received by the agent
2. Query is parsed to extract key information (ticker, sector, date range)
3. LLM decides which tools to call based on the query context
4. Data is retrieved from selected sources
5. Results are normalized and processed
6. LLM generates a narrative response synthesizing the data

### Tool Registration and Usage

The Sentiment Agent follows AutoGen 0.5.x patterns for tool registration and usage:

```python
# Tools are defined using FunctionTool in tools.py
sentiment_tools = get_tools_for_agent(SENTIMENT_AGENT)

# Agent is initialized with these tools
agent = SentimentAgent(tools=sentiment_tools)

# Agent uses process_with_tools to allow LLM to select tools
response = agent.process_with_tools(query, system_prompt)
```

## 3. Implementation Details

### AutoGen 0.5.x Integration

The Sentiment Agent uses AutoGen 0.5.x's function calling capabilities through:

- `FunctionTool` for tool definition (see `tools.py`)
- `model_client` for LLM integration
- AutoGen's messaging system for conversation management

### Dual Implementation Approaches

The system supports two different implementation approaches:

1. **AutoGen Framework Mode**
   - Uses `SentimentAgent` class (inherits from `BaseAgent` and AutoGen's `AssistantAgent`)
   - Follows AutoGen 0.5.x patterns for tool registration and usage
   - Tools are registered during agent initialization
   - LLM selects tools dynamically based on query

2. **Direct OpenAI API Mode**
   - Manually implements function calling using the OpenAI API directly
   - Defines tool schemas inline in the implementation
   - Provides a more direct control over the LLM interaction
   - Useful for testing and development

The CLI supports switching between these modes:

- Default: Direct OpenAI API Mode (for simplicity)
- Toggle with "direct" command: Switches to AutoGen Framework Mode

### LLM Function Calling Implementation

```python
# Example of the AutoGen implementation in SentimentAgent:
def generate_reply(self, messages, context=None):
    # [Processing logic...]
    return self.process_with_tools(last_message, system_prompt)

# Example of the direct implementation in CLI:
async def process_with_llm_function_calling(prompt, system_prompt):
    # [Direct OpenAI API implementation...]
```

## 4. Usage Guide

### CLI Interface

The sentiment_agent_cli_improved.py provides an interactive interface:

```bash
python sentiment_agent_cli_improved.py
```

### Switching Between Modes

Type "direct" in the CLI to toggle between:

- Function calling mode (default): Uses OpenAI API directly
- Direct agent mode: Uses SentimentAgent class with AutoGen

### When to Use Each Mode

- **Direct OpenAI API Mode**: For quick testing, simplified tool set
- **AutoGen Framework Mode**: For full access to all tools, proper framework usage

### Adding New Tools

To add a new tool to the Sentiment Agent:

1. Define the tool function in tools.py
2. Wrap it with FunctionTool
3. Add it to SENTIMENT_TOOLS list
4. Tag with agent_types = [SENTIMENT_AGENT]

Example:

```python
def my_new_tool(param1: str, param2: int) -> dict:
    """Tool documentation"""
    # Implementation
    return result

new_tool = FunctionTool(
    func=my_new_tool,
    name="my_new_tool",
    description="Description of what the tool does"
)
new_tool.agent_types = [SENTIMENT_AGENT]

# Add to SENTIMENT_TOOLS list
SENTIMENT_TOOLS.append(new_tool)
```

## 5. Testing

### Unit Testing

- Test individual components (QueryParser, tool functions)
- Mock API responses for deterministic testing

### Integration Testing

- Test complete agent workflow with mock LLM responses
- Verify tool selection logic

### Example Test Cases

- News sentiment analysis for specific ticker
- Market data retrieval and processing
- Error handling for missing data sources

## 6. Future Work

### Planned Improvements

- Enhanced natural language understanding
- Additional data sources integration
- Performance optimizations
- Integration with other agents

### Enhanced Query Understanding

- Implement a proper NLP pipeline for entity extraction
- Add more sophisticated date parsing for complex time ranges
- Support for comparison queries (e.g., "Compare tech vs energy sentiment")

### Additional Data Sources

- Integrate FRED economic indicators for macro context
- Add SEC filings for fundamental analysis
- Support bond yield and dollar index for cross-asset correlation
- Add options data to incorporate market expectations

### Performance Optimization

- Cache frequently accessed sector/ticker data
- Implement parallel data fetching for multiple sources
- Add request debouncing to manage API rate limits
- Cache recent API responses for common queries

### Response Quality

- Fine-tune the LLM system prompt for better narratives
- Add visual representations (charts, tables) of sentiment/price data
- Include customizable response detail levels
- Support for time series sentiment analysis

### Integration with Other Agents

- Standardize interfaces for Strategy and Risk agents
- Implement a structured output format for agent consumption
- Add metadata to responses for machine readability
- Support for targeted queries from other agents

## 7. Technical Details

### Key Improvements from Refactoring

1. **Modular Architecture**
   - Separated concerns into distinct modules:
     - SentimentAgent class (coordination and LLM integration)
     - QueryParser (natural language understanding)
     - DataProcessor (data formatting and preparation)
   - Moved shared utilities to a dedicated module

2. **External Configuration**
   - Moved system prompts to `agent_prompts.json`
   - Kept market sector data in `market_sectors.json`
   - Made it easier to update prompts and sector information

3. **LLM-Driven Design**
   - Eliminated hard-coded narrative templates
   - Let the LLM decide which tools to call based on the query
   - Used the LLM to generate natural language explanations
   - Provided supplementary context to guide the LLM

4. **Improved Query Understanding**
   - Implemented priority-based sector detection
   - Better support for complex natural language queries
   - Maintained fallback strategies for ambiguous queries

5. **Enhanced Processing Flow**
   - Pre-process user queries to extract helpful context
   - Process tool results for consistent data structures
   - Format data for optimal LLM consumption

### Technical Debt to Address

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
