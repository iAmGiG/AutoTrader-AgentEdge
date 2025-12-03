"""
Tool execution utilities for AutoGen agents.

Handles tool calling, argument parsing, and result formatting.
"""

import asyncio
import json
from typing import Any, Callable, Dict

import pandas as pd
from autogen_core._cancellation_token import CancellationToken
from autogen_core.models import FunctionExecutionResult

from src.data_sources.tools import fetch_unified_market_data

# Fallback map for tool execution (build dynamically to handle conditional imports)
TOOL_FUNCTION_MAP = {
    "fetch_unified_market_data": fetch_unified_market_data,
    # Minimal architecture - only essential tools
}


def parse_tool_arguments(tool_args: Any, agent_name: str = "Agent") -> Dict[str, Any]:
    """
    Parse tool arguments into a dictionary format that can be passed to a tool.
    This handles various formats that might be returned by the LLM.

    :param tool_args: The tool arguments in whatever format the LLM provided.
    :param agent_name: Name of the agent for logging.
    :return: A dictionary of parsed arguments.
    """
    if isinstance(tool_args, dict):
        # Already a dictionary, just return it
        return tool_args
    elif isinstance(tool_args, str):
        # Try to parse as JSON
        try:
            parsed_args = json.loads(tool_args)
            if isinstance(parsed_args, dict):
                return parsed_args
            else:
                print(f"[{agent_name}] Warning: Parsed JSON is not a dictionary: {parsed_args}")
                return {}
        except json.JSONDecodeError:
            print(f"[{agent_name}] Warning: Failed to parse tool arguments as JSON")
            return {}
    else:
        # Unknown format
        print(f"[{agent_name}] Warning: Unknown tool arguments format: {type(tool_args)}")
        return {}


def format_tool_result(
    result: Any, tool_name: str, tool_id: str, agent_name: str = "Agent"
) -> FunctionExecutionResult:
    """
    Format a tool result for use in the conversation.

    :param result: The raw or processed result from a tool.
    :param tool_name: The name of the tool that was called.
    :param tool_id: The ID of the tool call.
    :param agent_name: Name of the agent for logging.
    :return: A FunctionExecutionResult object.
    """
    # Convert to JSON-serializable format if needed
    content_str = None

    if isinstance(result, pd.DataFrame):
        # Handle DataFrame conversion
        try:
            # Convert datetime columns to strings to avoid JSON serialization issues
            result_copy = result.copy()
            for col in result_copy.columns:
                if result_copy[col].dtype == "datetime64[ns]" or "datetime" in str(
                    result_copy[col].dtype
                ):
                    result_copy[col] = result_copy[col].astype(str)

            result_dict = result_copy.to_dict(orient="records")
            # Add context for empty DataFrames to help LLM provide better responses
            if len(result_dict) == 0:
                if "Error" in result.columns and not result.empty:
                    # If we have error information, include it
                    content_str = json.dumps(
                        {
                            "data": result_dict,
                            "message": f"No data returned. DataFrame columns: {list(result.columns)}",
                            "error_info": result.to_dict("records") if not result.empty else None,
                        }
                    )
                else:
                    content_str = json.dumps(
                        {
                            "data": result_dict,
                            "message": f"No data found. Expected columns: {list(result.columns)}",
                        }
                    )
            else:
                content_str = json.dumps(result_dict)
        except Exception as e:
            print(f"[{agent_name}] Error converting DataFrame to JSON: {e}")
            content_str = str(result)
    elif isinstance(result, (dict, list)):
        # Handle dict or list conversion
        try:
            content_str = json.dumps(result)
        except Exception as e:
            print(f"[{agent_name}] Error converting dict/list to JSON: {e}")
            content_str = str(result)
    else:
        # For strings and other types
        content_str = str(result)

    # Return in expected format
    return FunctionExecutionResult(
        content=content_str, call_id=tool_id, is_error=False, name=tool_name
    )


async def execute_tool_async(  # noqa: C901
    tool, tool_name: str, tool_args: Dict[str, Any], agent_name: str = "Agent"
) -> Any:
    """
    Execute a tool asynchronously using the most appropriate method based on the tool's interface.

    :param tool: The tool object to execute
    :param tool_name: The name of the tool
    :param tool_args: The arguments to pass to the tool
    :param agent_name: Name of the agent for logging
    :return: The result of the tool execution
    """
    cancellation_token = CancellationToken()

    # Helper for executing a function
    async def call_exec_fn(exec_fn: Callable, *args, **kwargs) -> Any:
        """Execute a function, handling both sync and async cases."""
        if asyncio.iscoroutinefunction(exec_fn):
            print(f"[{agent_name}] Executing async function {exec_fn.__name__}")
            return await exec_fn(*args, **kwargs)
        else:
            print(f"[{agent_name}] Executing sync function {exec_fn.__name__} in thread executor")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: exec_fn(*args, **kwargs))

    # Tool access control should be handled by proper tool configuration in tools.py
    # Sentiment agents should only have access to sentiment tools via their initialization

    # Strategy 1: Use function map if available (most reliable fallback)
    if tool_name in TOOL_FUNCTION_MAP:
        try:
            exec_fn = TOOL_FUNCTION_MAP[tool_name]
            print(f"[{agent_name}] Executing {tool_name} via function map")
            result = await call_exec_fn(exec_fn, **tool_args)
            return result
        except Exception as e:
            print(f"[{agent_name}] Error executing via function map: {e}")
            # Continue to next strategy

    # Strategy 2: Direct function call if available
    if hasattr(tool, "func") and callable(tool.func):
        try:
            print(f"[{agent_name}] Executing {tool_name} directly via func attribute")
            result = await call_exec_fn(tool.func, **tool_args)
            return result
        except Exception as e:
            print(f"[{agent_name}] Error executing via func attribute: {e}")
            # Continue to next strategy

    # Strategy 3: Call the tool directly if it's callable
    if callable(tool):
        try:
            print(f"[{agent_name}] Executing {tool_name} via direct call")
            result = await call_exec_fn(tool, **tool_args)
            return result
        except Exception as e:
            print(f"[{agent_name}] Error executing via direct call: {e}")
            # Continue to next strategy

    # Strategy 4: Use the standard run_json method (last resort)
    if hasattr(tool, "run_json"):
        try:
            print(f"[{agent_name}] Executing {tool_name} via run_json")
            return await tool.run_json(tool_args, cancellation_token)
        except Exception as e:
            print(f"[{agent_name}] Error executing via run_json: {e}")
            # Continue to next strategy

    # If we've tried all strategies and none worked
    raise ValueError(f"No viable execution method found for tool: {tool_name}")


def log_tool_call(tool_name: str, tool_args: Any) -> None:
    """
    Log information about a tool call.

    :param tool_name: The name of the tool being called.
    :param tool_args: The arguments for the tool call.
    """
    if isinstance(tool_args, dict):
        args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
    else:
        args_str = str(tool_args)
    print(f"- LLM is using tool: {tool_name}({args_str})")


def log_tool_result(tool_result: Any, agent_name: str = "Agent") -> None:
    """
    Log information about a tool execution result.

    :param tool_result: The result from executing a tool.
    :param agent_name: Name of the agent for logging.
    """
    if isinstance(tool_result, pd.DataFrame):
        print(f"[{agent_name}] Result is DataFrame with shape {tool_result.shape}")
        if not tool_result.empty:
            print(f"DataFrame head: {tool_result.head(3)}")
    else:
        print(f"[{agent_name}] Result is {type(tool_result)}")
