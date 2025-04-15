# FunctionTool Reference

This document provides a reference for the `FunctionTool` class from `autogen_core.tools` and related classes, based on the use patterns observed in the RH2MAS codebase.

## FunctionTool Class

```python
from autogen_core.tools import FunctionTool

# Basic usage
function_tool = FunctionTool(
    func=my_function,
    name="my_function_name",
    description="Description of what this function does."
)
```

### Constructor Parameters

- `func`: The Python function to wrap as a tool
- `name`: A unique name for the tool (used when dispatching)
- `description`: Detailed description of what the tool does (shown to the LLM)

### Key Methods and Attributes

- `func`: Direct access to the underlying function
- `name`: The tool's name
- `description`: The tool's description

### Usage in RH2MAS

#### Tool Definition

```python
def fetch_news(keyword: str = "market", count: int = 5) -> pd.DataFrame:
    """
    Fetch news articles (as a DataFrame) from NewsHeadlineTool.
    """
    tool = NewsHeadlineTool(source="newsapi")
    df = tool.fetch_data(keyword=keyword, count=count)
    return df

news_tool = FunctionTool(
    func=fetch_news,
    name="fetch_news",
    description="Fetch news articles for a given keyword, returning a Pandas DataFrame."
)
```

#### Tool Execution

To call a tool directly:

```python
# Synchronous execution
result = tool.func(**args)

# Asynchronous execution (recommended pattern)
async def execute_tool_async(tool_name, tool_args):
    tool = tool_registry.get(tool_name)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: tool.func(**tool_args))
    return result
```

## Common Tool Patterns in RH2MAS

### Tool Registration

```python
# Central registry of tools
ALL_TOOLS = [
    news_tool,
    market_data_tool,
    # ...other tools
]

# Dictionary for efficient lookup
ALL_TOOLS_DICT = {tool.name: tool for tool in ALL_TOOLS}
```

### Tool Dispatcher in BaseAgent

```python
def execute_tool_by_name(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool by name using the tool dispatcher dictionary."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    return tool.func(**tool_args)

async def execute_tool_async(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """Execute a tool asynchronously."""
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: tool.func(**tool_args))
    return result
```

## Best Practices

1. **Tool Definition**:
   - Always include proper type hints in tool functions
   - Provide detailed docstrings for better LLM understanding
   - Use default parameters for optional arguments

2. **Tool Results**:
   - Return pandas DataFrames for data-oriented tools
   - Convert DataFrames to JSON-serializable format before passing to LLM
   - Use `df.to_dict(orient='records')` for DataFrame conversion

3. **Error Handling**:
   - Add proper exception handling in tool implementations
   - Return informative error messages
   - Log detailed debug information

4. **Tool Organization**:
   - Centralize tool definitions in `tools.py`
   - Maintain a lookup dictionary (`ALL_TOOLS_DICT`) for efficient dispatching
   - Keep individual tool implementations separate and modular