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

### Robust Dispatcher Pattern

```python
def execute_tool_by_name(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool by name using the tool dispatcher dictionary."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    # Attempt different ways to invoke the tool
    if hasattr(tool, 'func'):
        try:
            return tool.func(**tool_args)
        except Exception as e:
            self.log(f"Error using tool.func: {e}")
    
    if callable(tool):
        try:
            return tool(**tool_args)
        except Exception as e:
            self.log(f"Error calling tool directly: {e}")
    
    if hasattr(tool, 'run'):
        try:
            return tool.run(tool_args)
        except Exception as e:
            self.log(f"Error using tool.run: {e}")
    
    # Fallback to explicit dispatch from a mapping
    if tool_name in TOOL_FUNCTION_MAP:
        return TOOL_FUNCTION_MAP[tool_name](**tool_args)
    
    raise ValueError(f"Could not determine how to execute tool: {tool_name}")
```

**Benefits:**
- Handles different AutoGen Core versions with varying interfaces
- Provides multiple fallback methods if one approach fails
- Centralizes tool lookup and execution logic
- Makes adding new tools easier (no code changes in BaseAgent)
- Improves maintainability, resilience, and cross-version compatibility

### Advanced Asynchronous Execution

```python
async def execute_tool_async(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool asynchronously."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    # Create a cancellation token for methods that require it
    from autogen_core._cancellation_token import CancellationToken
    cancellation_token = CancellationToken()
    
    # Define a helper to execute a function according to its async nature
    async def call_exec_fn(exec_fn: Callable, *args, **kwargs) -> Any:
        """Call a function based on whether it's a coroutine or not."""
        if asyncio.iscoroutinefunction(exec_fn):
            # If it's already async, just await it
            return await exec_fn(*args, **kwargs)
        else:
            # If it's synchronous, run it in a thread executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: exec_fn(*args, **kwargs))
    
    # Determine proper execution method
    if hasattr(tool, 'func'):
        exec_fn = tool.func
        try:
            return await call_exec_fn(exec_fn, **tool_args)
        except Exception as e:
            self.log(f"Error using tool.func: {e}")
    
    elif callable(tool):
        try:
            return await call_exec_fn(tool, **tool_args)
        except Exception as e:
            self.log(f"Error calling tool directly: {e}")
    
    elif hasattr(tool, 'run'):
        exec_fn = tool.run
        try:
            # Pass cancellation_token as required in AutoGen 0.5.1
            return await call_exec_fn(exec_fn, tool_args, cancellation_token)
        except Exception as e:
            self.log(f"Error using tool.run: {e}")
    
    elif tool_name in TOOL_FUNCTION_MAP:
        exec_fn = TOOL_FUNCTION_MAP[tool_name]
        try:
            return await call_exec_fn(exec_fn, **tool_args)
        except Exception as e:
            raise ValueError(f"Failed to execute tool: {e}")
    
    raise ValueError(f"Could not determine how to execute tool: {tool_name}")
```

**Advanced Features:**
- Intelligently handles both synchronous and asynchronous (coroutine) functions
- Uses `asyncio.iscoroutinefunction()` to detect if a function is a coroutine
- Awaits coroutine functions directly for optimal performance
- Runs synchronous functions in thread executor to prevent blocking
- Provides CancellationToken for tools requiring it (AutoGen 0.5.1 requirement)
- Logs detailed execution path for better debugging
- Falls back gracefully through multiple execution methods
- Compatible with both older and newer versions of AutoGen

**Important Notes:**
- CancellationToken is imported from `autogen_core._cancellation_token` (not tools)
- Coroutine functions must be awaited, not run in a thread executor
- Requires `import inspect` or `import asyncio` to detect coroutines
- The `run` method in AutoGen 0.5.1 requires a cancellation token as a second parameter

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