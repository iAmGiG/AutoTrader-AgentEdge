# AutoGen Core Best Practices

This document outlines best practices for working with AutoGen Core 0.5.x in the RH2MAS project, based on observed patterns and optimizations.

## Tool Implementation

### Function Definition

```python
def fetch_data(symbol: str = "AAPL", count: int = 5) -> pd.DataFrame:
    """
    Fetch data for the given symbol.
    
    Args:
        symbol: The stock symbol to fetch data for
        count: Number of records to retrieve
        
    Returns:
        DataFrame containing the requested data
    """
    # Implementation...
    return df
```

**Best Practices:**
- Use clear, descriptive function names
- Add type annotations for all parameters and return values
- Provide detailed docstrings (used by LLM to understand the tool)
- Include default values for optional parameters
- Return standardized data structures (DataFrames when possible)

### Tool Registration

```python
from autogen_core.tools import FunctionTool

data_tool = FunctionTool(
    func=fetch_data,
    name="fetch_data",
    description="Fetches financial data for a given stock symbol, returning a DataFrame."
)

# Register all tools in a central location
ALL_TOOLS = [data_tool, news_tool, ...]
ALL_TOOLS_DICT = {tool.name: tool for tool in ALL_TOOLS}
```

**Best Practices:**
- Wrap each function with `FunctionTool`
- Use consistent naming conventions
- Provide detailed descriptions for each tool
- Create a dictionary for efficient lookup by name
- Centralize tool registration in one location (`tools.py`)

## Tool Dispatching

### Efficient Dispatcher Pattern

```python
def execute_tool_by_name(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool by name using the tool dispatcher dictionary."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    return tool.func(**tool_args)
```

**Benefits:**
- Eliminates lengthy if-else chains
- Centralizes tool lookup logic
- Makes adding new tools easier (no code changes in BaseAgent)
- Improves maintainability and testability

### Asynchronous Execution

```python
async def execute_tool_async(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool asynchronously."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: tool.func(**tool_args))
    return result
```

**Benefits:**
- Allows non-blocking execution
- Enables potential parallel tool execution
- Maintains responsiveness during long-running operations
- Fits with AutoGen's async architecture

## Data Handling

### DataFrame Processing

```python
# Convert DataFrame to JSON-serializable format
if isinstance(result, pd.DataFrame):
    # Convert DataFrame to dict
    result_dict = result.to_dict(orient='records')
    # Convert to JSON string
    content_str = json.dumps(result_dict)
    return content_str
```

**Best Practices:**
- Always convert DataFrames to dictionaries before serialization
- Use `orient='records'` for most readable format for LLMs
- Handle empty DataFrames gracefully
- Add debugging information about DataFrame shape and content

### Error Handling

```python
try:
    # Tool execution code
    result = tool.func(**args)
    return result
except Exception as e:
    error_message = f"Error executing {tool_name}: {str(e)}"
    traceback.print_exc()  # For debug logs
    return FunctionExecutionResult(
        content=error_message,
        call_id=tool_id,
        is_error=True,
        name=tool_name
    )
```

**Best Practices:**
- Use try/except blocks around tool execution
- Return specific error messages
- Set `is_error=True` in FunctionExecutionResult
- Log detailed stack traces for debugging
- Provide guidance for the LLM on how to handle the error

## LLM Interaction

### Message Construction

```python
def _build_message_sequence(self, prompt: str, system_prompt: Optional[str] = None) -> List[Any]:
    """Build a sequence of messages for the conversation with the LLM."""
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(UserMessage(content=prompt, source="user"))
    return messages
```

**Best Practices:**
- Create helper methods for common message patterns
- Include optional system prompts for context
- Maintain consistent message structure
- Use appropriate message types from `autogen_core.models`

### Conversation Management

```python
# Initialize conversation
conversation = messages.copy()

# First LLM call
response = await self.model_client.create(messages=conversation, tools=tools_list)

# Add assistant response to conversation
conversation.append(AssistantMessage(content=response.content, source="assistant"))

# Add tool results to conversation
conversation.append(FunctionExecutionResultMessage(content=tool_results))

# Final LLM call
final_response = await self.model_client.create(messages=conversation)
```

**Best Practices:**
- Maintain the full conversation history
- Add each message to the conversation in the correct order
- Include tool calls and results in the conversation
- Pass the complete conversation history to follow-up LLM calls