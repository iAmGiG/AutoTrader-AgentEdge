# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
"""

# Import the proper message types from autogen_core
from autogen_core.models import SystemMessage, UserMessage, AssistantMessage, FunctionExecutionResult, FunctionExecutionResultMessage
from autogen_agentchat.agents._assistant_agent import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
# Import tool dictionary for dynamic tool access
from src.tools.tools import ALL_TOOLS, ALL_TOOLS_DICT
from src.tools.tools import (
    fetch_market_data, fetch_news, fetch_yahoo_data,
    fetch_alpha_vantage_data, fetch_alpha_vantage_news
)
from config.config_loader import ConfigLoader
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict, Callable
# Import CancellationToken from autogen_core
from autogen_core._cancellation_token import CancellationToken
import asyncio
import inspect
import traceback
import pandas as pd

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()
model_name = _loader.get("open_model")     # e.g. "gpt-4o-mini"
open_ai_key = _loader.get("open_ai_key")

# Fallback map for tool execution when other methods fail
TOOL_FUNCTION_MAP = {
    "fetch_market_data": fetch_market_data,
    "fetch_news": fetch_news,
    "fetch_yahoo_data": fetch_yahoo_data,
    "fetch_alpha_vantage_data": fetch_alpha_vantage_data,
    "fetch_alpha_vantage_news": fetch_alpha_vantage_news
}

# Default LLM parameters for improved function calling
DEFAULT_LLM_CONFIG = {
    "temperature": 0.2,  # Lower temperature for more deterministic function calling
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.95,       # Focus on more likely tokens
}


class BaseAgent(AssistantAgent, ABC):
    """
    Abstract base class for AutoGen-based agents.
    Encapsulates common functionalities such as:
      - Configuration handling via AutoGen's AgentConfig
      - Memory system access for knowledge retrieval
      - Tool registration and usage
    """

    def __init__(self, name: str, tools=None, memory_system: Optional[Any] = None, llm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent with tools, memory system, and LLM configuration.

        :param name: Unique name/identifier for this agent.
        :param tools: List of tools the agent can use.
        :param memory_system: Optional memory interface for knowledge storage and retrieval.
        :param llm_config: Optional dictionary containing LLM settings (temperature, etc).
        """
        # 1. Merge default LLM config with any provided config
        llm_params = DEFAULT_LLM_CONFIG.copy()
        if llm_config:
            llm_params.update(llm_config)

        # 2. Create the LLM client instance for function calling
        # Use the updated configuration style for OpenAIChatCompletionClient in AutoGen 0.5.1
        client_config = {
            "model": model_name,
            "api_key": open_ai_key,
            # LLM parameters
            "temperature": llm_params.get("temperature", 0.2),
            "max_tokens": llm_params.get("max_tokens", 4096),
            "top_p": llm_params.get("top_p", 0.95),
            # API settings
            "timeout": llm_params.get("timeout", 120),
            "max_retries": llm_params.get("max_retries", 3),
        }

        model_client_instance = OpenAIChatCompletionClient(**client_config)

        # 3. Set up tools
        tools = tools or ALL_TOOLS
        if tools is None:
            tools = []

        # 4. Call the parent constructor
        super().__init__(
            name=name,
            model_client=model_client_instance,
            tools=tools,  # Tools are passed directly to AssistantAgent
            description=f"{name} agent",
            reflect_on_tool_use=True,     # Let the agent reflect on tool calls
            tool_call_summary_format="{result}",
        )

        # 5. Store tools in a local dict for manual calls
        self._tools_dict = {tool.name: tool for tool in tools}

        # 6. Set up memory system
        self.memory_system = memory_system

        # 7. Store the LLM configuration and model client
        self.llm_config = llm_params

        # 8. Store model_client instance for direct access by subclasses
        self.model_client = model_client_instance

    def use_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Manually invoke a tool by name with the given keyword arguments.

        :param tool_name: Name of the tool to invoke.
        :param kwargs: Keyword arguments to pass to the tool.
        :return: Result of the tool invocation.
        """
        tool = self._tools_dict.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found {tool_name}")
        return tool(**kwargs)

    def process_with_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Base implementation to process a prompt with the LLM directly.
        This provides a minimal implementation without any specialized processing.
        Agents should override this method to add agent-specific processing.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response.
        """
        try:
            # Build the messages array with the correct message types
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))

            # Add the user prompt with the correct message type
            messages.append(UserMessage(content=prompt, source="user"))

            # Define async function to call the LLM
            async def async_call_llm():
                # Call the LLM directly using the model_client
                response = await self.model_client.create(messages=messages)
                return response

            # Run the async function and get the response
            response = asyncio.run(async_call_llm())

            # Extract the response content - in AutoGen 0.5.x, the response structure is different
            if response:
                # Check if the response has a content attribute (new AutoGen API)
                if hasattr(response, 'content'):
                    if isinstance(response.content, str):
                        return response.content
                    else:
                        # This could be another format, convert to string
                        return str(response.content)
                # Fall back to other possible response formats
                else:
                    return str(response)
            else:
                return "No response generated by the LLM."

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"

    def process_with_tools(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Process a prompt with the LLM, supporting tool calling but with minimal processing.
        This method provides the core tool calling functionality that specific agents can build upon.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response.
        """
        try:
            messages = self._build_message_sequence(prompt, system_prompt)
            response = asyncio.run(self._run_tool_conversation(messages))
            return self._extract_content(response)
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"

    def _build_message_sequence(self, prompt: str, system_prompt: Optional[str] = None) -> List[Any]:
        """
        Build a sequence of messages for the conversation with the LLM.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: A list of message objects.
        """
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(UserMessage(content=prompt, source="user"))
        return messages

    async def _run_tool_conversation(self, messages: List[Any]) -> Any:
        """
        Run a conversation with the LLM that may involve tool calling.

        :param messages: The initial messages for the conversation.
        :return: The LLM's response.
        """
        # Initialize conversation history for this interaction
        conversation = messages.copy()

        # Set up tools for the LLM to use
        tools_list = list(self._tools_dict.values())

        # First LLM call - might return tool calls
        print("- Calling LLM to analyze the query...")
        response = await self.model_client.create(messages=conversation, tools=tools_list)

        # Check if the response contains tool calls
        if hasattr(response, 'content') and isinstance(response.content, list):
            # We have tool calls to process
            tool_calls = response.content
            conversation.append(AssistantMessage(content=tool_calls, source="assistant"))
            
            # Process all tool calls and get results
            tool_results = await self._process_tool_calls(tool_calls)
            
            # Add the tool results to the conversation
            if tool_results:
                conversation.append(FunctionExecutionResultMessage(content=tool_results))

            # Call the LLM again with the tool results
            print("- Calling LLM to generate final response with tool results...")
            final_response = await self.model_client.create(messages=conversation)
            return final_response

        # If no tool calls, just return the initial response
        return response

    async def _process_tool_calls(self, tool_calls: List[Any]) -> List[FunctionExecutionResult]:
        """
        Process a list of tool calls and return their results.

        :param tool_calls: A list of tool call objects from the LLM.
        :return: A list of function execution results.
        """
        tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_args = tool_call.arguments
            tool_id = tool_call.id

            # Print diagnostic info about the tool call
            self._log_tool_call(tool_name, tool_args)
            
            try:
                # Execute the tool and get the result
                tool_result = await self._execute_tool(tool_name, tool_args)
                
                # Format the result for the LLM
                formatted_result = self._format_tool_result(tool_result, tool_name, tool_id)
                tool_results.append(formatted_result)
            except Exception as e:
                # Handle tool execution errors
                error_message = f"Error executing {tool_name}: {str(e)}"
                print(error_message)
                tool_results.append(
                    FunctionExecutionResult(
                        content=error_message,
                        call_id=tool_id,
                        is_error=True,
                        name=tool_name
                    )
                )
                
        return tool_results

    def _log_tool_call(self, tool_name: str, tool_args: Any) -> None:
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

    async def _execute_tool(self, tool_name: str, tool_args: Any) -> Any:
        """
        Execute a tool with the given arguments.

        :param tool_name: The name of the tool to execute.
        :param tool_args: The arguments for the tool.
        :return: The result of the tool execution.
        """
        # Get the actual tool from the tools dict
        tool = self._tools_dict.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Parse the tool arguments in a clean way
        parsed_args = self._parse_tool_arguments(tool_args)

        try:
            # Call the appropriate function directly based on tool name
            tool_result = await self._call_specific_tool(tool_name, parsed_args)
            self.log(f"Successfully executed {tool_name}")
            
            # Log information about the result
            self._log_tool_result(tool_result)
            
            # Let the subclass process the result if needed
            processed_result = self.process_tool_result(tool_name, tool_result, parsed_args)
            return processed_result
            
        except Exception as e:
            traceback.print_exc()
            self.log(f"Error executing tool {tool_name}: {str(e)}")
            return f"Error executing {tool_name}: {str(e)}"

    def execute_tool_by_name(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a tool by name using the tool dispatcher dictionary.
        
        This method checks the tool's interface to decide whether to call its
        'func', directly call the tool (if callable), or use its 'run' method.
        If a function is a coroutine, it will run it through the async method.
        
        :param tool_name: The name of the tool to execute.
        :param tool_args: The arguments to pass to the tool.
        :return: The result of the tool execution.
        """
        tool = ALL_TOOLS_DICT.get(tool_name)
        if not tool:
            self.log(f"Tool '{tool_name}' not found.")
            raise ValueError(f"Tool '{tool_name}' is not defined.")
        
        self.log(f"Executing tool: {tool_name} with arguments: {tool_args}")

        # Create a cancellation token for methods that require it
        cancellation_token = CancellationToken()
        
        # Helper function to handle potentially coroutine functions
        def exec_fn_sync(fn: Callable, *args, **kwargs) -> Any:
            """Execute a function, running it through asyncio if it's a coroutine function."""
            if asyncio.iscoroutinefunction(fn):
                self.log(f"Function {fn.__name__} is a coroutine, running via asyncio")
                # We need to run the coroutine function through asyncio
                return asyncio.run(fn(*args, **kwargs))
            else:
                return fn(*args, **kwargs)

        # Attempt different ways to invoke the tool
        if hasattr(tool, 'func'):
            try:
                return exec_fn_sync(tool.func, **tool_args)
            except Exception as e:
                self.log(f"Error using tool.func: {e}")
                traceback.print_exc()
        
        if callable(tool):
            try:
                return exec_fn_sync(tool, **tool_args)
            except Exception as e:
                self.log(f"Error calling tool directly: {e}")
                traceback.print_exc()
        
        if hasattr(tool, 'run'):
            try:
                # Pass cancellation_token as required by AutoGen 0.5.1
                return exec_fn_sync(tool.run, tool_args, cancellation_token)
            except Exception as e:
                self.log(f"Error using tool.run with cancellation token: {e}")
                traceback.print_exc()
        
        # Fallback to explicit dispatch from the mapping
        if tool_name in TOOL_FUNCTION_MAP:
            try:
                return exec_fn_sync(TOOL_FUNCTION_MAP[tool_name], **tool_args)
            except Exception as e:
                self.log(f"Error using fallback function: {e}")
                traceback.print_exc()
                
                # As a last resort, try to execute the tool asynchronously
                try:
                    self.log(f"Attempting to execute {tool_name} asynchronously as a last resort")
                    return asyncio.run(self.execute_tool_async(tool_name, tool_args))
                except Exception as e2:
                    self.log(f"Async execution also failed: {e2}")
                    raise ValueError(f"Failed to execute tool {tool_name} with all available methods: {e}, {e2}")
        
        raise ValueError(f"Could not determine how to execute tool: {tool_name}")
    
    async def execute_tool_async(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Execute a tool asynchronously using the dispatcher dictionary.
        
        This method checks the tool's interface to decide whether to call its
        'func', directly call the tool (if callable), or use its 'run' method.
        If a tool returns a coroutine (is async), we await it; otherwise, we run it
        in an executor.
        
        :param tool_name: The name of the tool to execute.
        :param tool_args: The arguments to pass to the tool.
        :return: The result of the tool execution.
        """
        tool = ALL_TOOLS_DICT.get(tool_name)
        if not tool:
            self.log(f"Tool '{tool_name}' not found.")
            raise ValueError(f"Tool '{tool_name}' is not defined.")
        
        self.log(f"Executing tool asynchronously: {tool_name} with arguments: {tool_args}")
        
        # Create a cancellation token for methods that require it
        cancellation_token = CancellationToken()
        
        # Define a helper to execute a given function according to its async nature
        async def call_exec_fn(exec_fn: Callable, *args, **kwargs) -> Any:
            """Helper function to call the execution function based on whether it's a coroutine or not."""
            if asyncio.iscoroutinefunction(exec_fn):
                self.log(f"Executing async function {exec_fn.__name__}")
                return await exec_fn(*args, **kwargs)
            else:
                self.log(f"Executing sync function {exec_fn.__name__} in thread executor")
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: exec_fn(*args, **kwargs))
        
        # Determine the proper method to execute the tool
        if hasattr(tool, 'func'):
            exec_fn = tool.func
            try:
                result = await call_exec_fn(exec_fn, **tool_args)
                self.log(f"Tool '{tool_name}' execution completed via tool.func.")
                return result
            except Exception as e:
                self.log(f"Error using tool.func for {tool_name}: {e}")
                traceback.print_exc()
        
        elif callable(tool):
            try:
                result = await call_exec_fn(tool, **tool_args)
                self.log(f"Tool '{tool_name}' execution completed via direct call.")
                return result
            except Exception as e:
                self.log(f"Error calling tool directly for {tool_name}: {e}")
                traceback.print_exc()
        
        elif hasattr(tool, 'run'):
            exec_fn = tool.run
            try:
                # Pass cancellation_token to run
                result = await call_exec_fn(exec_fn, tool_args, cancellation_token)
                self.log(f"Tool '{tool_name}' execution completed via tool.run.")
                return result
            except Exception as e:
                self.log(f"Error using tool.run for {tool_name}: {e}")
                traceback.print_exc()
        
        elif tool_name in TOOL_FUNCTION_MAP:
            exec_fn = TOOL_FUNCTION_MAP[tool_name]
            try:
                result = await call_exec_fn(exec_fn, **tool_args)
                self.log(f"Tool '{tool_name}' execution completed via function map.")
                return result
            except Exception as e:
                self.log(f"Error using fallback function for {tool_name}: {e}")
                traceback.print_exc()
                raise ValueError(f"Failed to execute tool {tool_name} asynchronously: {e}")
        
        else:
            raise ValueError(f"Could not determine how to execute tool: {tool_name}")

    async def _call_specific_tool(self, tool_name: str, parsed_args: Dict[str, Any]) -> Any:
        """
        Call a specific tool by name with parsed arguments.
        Uses the improved async tool execution with proper coroutine handling.

        :param tool_name: The name of the tool to call.
        :param parsed_args: The parsed arguments for the tool.
        :return: The result of the tool call.
        """
        try:
            # Use the advanced async dispatcher to execute the tool
            # This will properly handle both synchronous and asynchronous functions
            self.log(f"Calling tool {tool_name} with arguments: {parsed_args}")
            result = await self.execute_tool_async(tool_name, parsed_args)
            self.log(f"Completed execution of {tool_name}")
            return result
        except Exception as e:
            self.log(f"Error executing tool {tool_name}: {str(e)}")
            traceback.print_exc()
            return f"Error executing {tool_name}: {str(e)}"

    def _log_tool_result(self, tool_result: Any) -> None:
        """
        Log information about a tool execution result.

        :param tool_result: The result from executing a tool.
        """
        if isinstance(tool_result, pd.DataFrame):
            self.log(f"Result is DataFrame with shape {tool_result.shape}")
            # Temporary debug info
            if not tool_result.empty:
                print(f"DataFrame head: {tool_result.head(3)}")
        else:
            self.log(f"Result is {type(tool_result)}")

    def _format_tool_result(self, result: Any, tool_name: str, tool_id: str) -> FunctionExecutionResult:
        """
        Format a tool result for use in the conversation.

        :param result: The raw or processed result from a tool.
        :param tool_name: The name of the tool that was called.
        :param tool_id: The ID of the tool call.
        :return: A FunctionExecutionResult object.
        """
        # Convert processed result to JSON serializable format if needed
        if hasattr(result, 'to_dict'):
            # For pandas DataFrames or objects with to_dict method
            result = result.to_dict(orient='records')

        # Convert the processed result to a string if it's not already
        if isinstance(result, (dict, pd.DataFrame, list)):
            try:
                import json

                # Convert DataFrame to dict if needed
                if isinstance(result, pd.DataFrame):
                    result_dict = result.to_dict(orient='records')
                else:
                    result_dict = result

                # Convert to JSON string
                content_str = json.dumps(result_dict)

                # Return the result as a string
                return FunctionExecutionResult(
                    content=content_str,
                    call_id=tool_id,
                    is_error=False,
                    name=tool_name
                )
            except Exception as e:
                self.log(f"Error serializing result to JSON: {str(e)}")
                return FunctionExecutionResult(
                    content=str(result),
                    call_id=tool_id,
                    is_error=False,
                    name=tool_name
                )
        else:
            # If it's already a string or another simple type, just convert to string
            return FunctionExecutionResult(
                content=str(result),
                call_id=tool_id,
                is_error=False,
                name=tool_name
            )

    def _extract_content(self, response: Any) -> str:
        """
        Extract the content from a response object.

        :param response: The response from the LLM.
        :return: The content as a string.
        """
        if response:
            # Check if the response has a content attribute (new AutoGen API)
            if hasattr(response, 'content'):
                if isinstance(response.content, str):
                    return response.content
                else:
                    # This could be another format, convert to string
                    return str(response.content)
            # Fall back to other possible response formats
            else:
                return str(response)
        else:
            return "No response generated by the LLM."

    def _parse_tool_arguments(self, tool_args: Any) -> Dict[str, Any]:
        """
        Parse tool arguments into a dictionary format that can be passed to a tool.
        This handles various formats that might be returned by the LLM.

        :param tool_args: The tool arguments in whatever format the LLM provided.
        :return: A dictionary of parsed arguments.
        """
        if isinstance(tool_args, dict):
            # Already a dictionary, just return it
            return tool_args
        elif isinstance(tool_args, str):
            # Try to parse as JSON
            import json
            try:
                parsed_args = json.loads(tool_args)
                if isinstance(parsed_args, dict):
                    return parsed_args
                else:
                    self.log(
                        f"Warning: Parsed JSON is not a dictionary: {parsed_args}")
                    return {}
            except json.JSONDecodeError as e:
                self.log(
                    f"Warning: Failed to parse tool arguments as JSON: {e}")
                return {}
        else:
            # Unknown format
            self.log(
                f"Warning: Unknown tool arguments format: {type(tool_args)}")
            return {}

    def process_tool_result(self, tool_name: str, result: Any, tool_args: Any) -> Any:
        """
        Process tool results before passing them back to the LLM.
        This is a hook for subclasses to override and add custom processing.

        :param tool_name: The name of the tool that was called.
        :param result: The raw result from the tool.
        :param tool_args: The arguments that were passed to the tool.
        :return: The processed result.
        """
        # Base implementation just returns the result without processing
        return result

    @abstractmethod
    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.

        :param messages: List of messages in the conversation.
        :param context: Optional context from AutoGen.
        :return: The agent's response.
        """
        pass

    def store_in_memory(self, key: str, data: Any) -> None:
        """
        Stores data in the memory system under the specified key.
        """
        if self.memory_system:
            self.memory_system.store_data(key, data)

    def retrieve_from_memory(self, key: str) -> Any:
        """
        Retrieves data from memory.
        """
        if self.memory_system:
            return self.memory_system.retrieve_data(key)
        return None

    def store_data_in_context(self, key: str, data: Any):
        if self.memory_system:
            self.memory_system.store_data(key, data, layer="context")

    def retrieve_data_from_context(self, key: str):
        if self.memory_system:
            return self.memory_system.retrieve_data(key, layer="context")
        return None

    def set_logger(self, logger: Any) -> None:
        """
        Optionally attaches a logger to this agent for debugging and audit trails.

        :param logger: A logging instance (e.g., Python's built-in logging).
        """
        self.logger = logger

    def log(self, message: str) -> None:
        """
        Logs a message if a logger has been set.

        :param message: The log message.
        """
        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"[{self.name}] {message}")
        else:
            # For quick debugging, fallback to print
            print(f"[{self.name}] {message}")
