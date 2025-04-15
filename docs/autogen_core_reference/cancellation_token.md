# CancellationToken Reference

This document provides information about the `CancellationToken` class in AutoGen Core 0.5.x, which is required for certain tool execution methods.

## Overview

The `CancellationToken` is a utility class used in AutoGen Core to allow for the cancellation of asynchronous operations. It is particularly important when working with the `run` method of `FunctionTool` objects, which requires a cancellation token as a parameter.

## Import Path

```python
from autogen_core._cancellation_token import CancellationToken
```

Note that the class is in an underscore-prefixed module, which typically indicates it's an internal implementation detail. However, it is required for proper tool execution in AutoGen 0.5.x.

## Basic Usage

```python
# Create a cancellation token
cancellation_token = CancellationToken()

# Use it with a tool's run method
result = tool.run(tool_args, cancellation_token)
```

## Class Definition

The `CancellationToken` class provides the following methods:

```python
class CancellationToken:
    """A token used to cancel pending async calls"""

    def __init__(self) -> None:
        """Initialize a new cancellation token."""
        
    def cancel(self) -> None:
        """Cancel pending async calls linked to this cancellation token."""
        
    def is_cancelled(self) -> bool:
        """Check if the CancellationToken has been used"""
        
    def add_callback(self, callback: Callable[[], None]) -> None:
        """Attach a callback that will be called when cancel is invoked"""
        
    def link_future(self, future: Future[Any]) -> Future[Any]:
        """Link a pending async call to a token to allow its cancellation"""
```

## Integration with Tool Execution

When executing tools that have a `run` method, you must pass a cancellation token:

```python
# Tool execution with proper cancellation token
if hasattr(tool, 'run'):
    try:
        # Pass cancellation_token as required by AutoGen 0.5.1
        return tool.run(tool_args, cancellation_token)
    except Exception as e:
        self.log(f"Error using tool.run with cancellation token: {e}")
```

## Common Errors

If you see errors like:

```
TypeError: run() missing 1 required positional argument: 'cancellation_token'
```

It means you're calling a tool's `run` method without providing the required cancellation token.

## Best Practices

1. **Always Import From The Correct Path**: Use the import path `autogen_core._cancellation_token` rather than trying to import from other modules.

2. **Create a New Token for Each Request**: Create a fresh cancellation token for each tool execution rather than reusing tokens.

3. **Handle Cancellation Gracefully**: If implementing cancellation logic, ensure your code handles it gracefully, releasing any resources that might otherwise be leaked.

4. **Robust Implementation**: Your tool dispatcher should include proper error handling around cancellation token usage:

```python
def execute_tool_by_name(self, tool_name, tool_args):
    tool = ALL_TOOLS_DICT.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' is not defined.")
        
    # Create a fresh cancellation token
    cancellation_token = CancellationToken()
    
    # Try tool.func first
    if hasattr(tool, 'func'):
        try:
            return tool.func(**tool_args)
        except Exception as e:
            self.log(f"Error using tool.func: {e}")
    
    # Try run with cancellation token
    if hasattr(tool, 'run'):
        try:
            return tool.run(tool_args, cancellation_token)
        except Exception as e:
            self.log(f"Error using tool.run with cancellation token: {e}")
            
    # Fallback to other methods...
```