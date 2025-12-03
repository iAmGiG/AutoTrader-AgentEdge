# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
This implementation is designed for AutoGen 0.6.x and provides common functionality
for all agents in the system.
"""

# Import standard Python libraries
import asyncio
import os
import traceback
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Dict, List, Optional, Union

from autogen_agentchat.agents._assistant_agent import AssistantAgent

# Import the proper AutoGen core components
from autogen_core.models import (
    AssistantMessage,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
)
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Import tool dictionary and extracted utilities
from src.autogen_agents.message_processor import build_message_sequence, extract_content
from src.autogen_agents.tool_executor import (
    execute_tool_async,
    format_tool_result,
    log_tool_call,
    log_tool_result,
    parse_tool_arguments,
)
from src.data_sources.tools import ALL_TOOLS

# Import utils and config
from src.utils.config_loader import ConfigLoader

# Load configuration file for fallback values
config_loader = ConfigLoader()

# Read configuration from environment variables or fallback to config
model_name = os.getenv("OPEN_MODEL", config_loader.get("OPEN_MODEL"))
open_ai_key = os.getenv("OPEN_AI_KEY", config_loader.get("OPEN_AI_KEY"))

# Dual model configuration for cost optimization
# Tool calling: Use gpt-4o-mini (fast, cheap, efficient for structured outputs)
# Prompt/Reasoning: Use o4-mini (enhanced reasoning for trading decisions)
tool_model_name = os.getenv("OPENAI_TOOL_MODEL", config_loader.get("OPENAI_TOOL_MODEL", model_name))
prompt_model_name = os.getenv(
    "OPENAI_PROMPT_MODEL", config_loader.get("OPENAI_PROMPT_MODEL", model_name)
)

# Default LLM parameters
DEFAULT_LLM_CONFIG = {
    "temperature": 0.2,  # Lower temperature for more deterministic function calling
    "max_tokens": 4096,  # Ensure enough tokens for complex responses
    "top_p": 0.95,  # Focus on more likely tokens
}


class BaseAgent(AssistantAgent, ABC):
    """
    Abstract base class for AutoGen-based agents.
    Encapsulates common functionalities such as:
      - Configuration handling via AutoGen's AgentConfig
      - Memory system access for knowledge retrieval
      - Tool registration and usage
    """

    def __init__(
        self,
        name: str,
        tools=None,
        memory_system: Optional[Any] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        use_dual_models: bool = False,
    ):
        """
        Initialize the agent with tools, memory system, and LLM configuration.

        :param name: Unique name/identifier for this agent.
        :param tools: List of tools the agent can use.
        :param memory_system: Optional memory interface for knowledge storage and retrieval.
        :param llm_config: Optional dictionary containing LLM settings (temperature, etc).
        :param use_dual_models: If True, uses separate models for tool calling (4o-mini) and reasoning (o3-mini).
                                Default False - most agents use pure calculations without LLM calls.
        """
        # 1. Merge default LLM config with any provided config
        llm_params = DEFAULT_LLM_CONFIG.copy()
        if llm_config:
            llm_params.update(llm_config)

        # 2. Create the LLM client instance for function calling
        if not open_ai_key:
            raise ValueError(
                "OpenAI API key not found. Set the OPEN_AI_KEY environment variable or update your Codex config."
            )

        # Select model based on dual model configuration
        selected_model = tool_model_name if use_dual_models else model_name

        client_config = {
            "model": selected_model,
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
        if tools is None:
            tools = ALL_TOOLS

        # 4. Call the parent constructor
        super().__init__(
            name=name,
            model_client=model_client_instance,
            tools=tools,
            description=f"{name} agent",
            reflect_on_tool_use=True,
            tool_call_summary_format="{result}",
        )

        # 5. Store tools in a local dict for direct access
        self._tools_dict = {tool.name: tool for tool in tools}

        # 6. Set up memory system
        self.memory_system = memory_system

        # 7. Store the LLM configuration and model client
        self.llm_config = llm_params
        self.model_client = model_client_instance

        # 8. Create optional reasoning model client (o3-mini for enhanced reasoning)
        self.use_dual_models = use_dual_models
        if use_dual_models:
            reasoning_config = client_config.copy()
            reasoning_config["model"] = prompt_model_name
            self.reasoning_model_client = OpenAIChatCompletionClient(**reasoning_config)
        else:
            self.reasoning_model_client = None

    def log(self, message: str) -> None:
        """
        Logs a message using the agent's logger or falls back to print.

        :param message: The log message.
        """
        if hasattr(self, "logger") and self.logger:
            self.logger.info(f"[{self.name}] {message}")
        else:
            # For quick debugging, fallback to print
            print(f"[{self.name}] {message}")

    #############################
    # Message Building and Processing
    #############################

    def _build_message_sequence(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> List[Any]:
        """Build a sequence of messages for the conversation with the LLM."""
        return build_message_sequence(prompt, system_prompt)

    def _extract_content(self, response: Any) -> str:
        """Extract the content from a response object."""
        return extract_content(response)

    def _parse_tool_arguments(self, tool_args: Any) -> Dict[str, Any]:
        """Parse tool arguments into a dictionary format."""
        return parse_tool_arguments(tool_args, self.name)

    #############################
    # Tool Execution
    #############################

    async def _execute_tool(self, tool_name: str, tool_args: Any) -> Any:
        """
        Core method to execute a tool with the given arguments.

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
            # Call the tool and get result
            tool_result = await self._execute_tool_async(tool, tool_name, parsed_args)

            # Log and process result
            self._log_tool_result(tool_result)
            processed_result = self.process_tool_result(tool_name, tool_result, parsed_args)
            return processed_result
        except Exception as e:
            traceback.print_exc()
            self.log(f"Error executing tool {tool_name}: {str(e)}")
            return f"Error executing {tool_name}: {str(e)}"

    async def _execute_tool_async(self, tool, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Execute a tool asynchronously using the extracted tool executor."""
        return await execute_tool_async(tool, tool_name, tool_args, self.name)

    def _log_tool_call(self, tool_name: str, tool_args: Any) -> None:
        """Log information about a tool call."""
        log_tool_call(tool_name, tool_args)

    def _log_tool_result(self, tool_result: Any) -> None:
        """Log information about a tool execution result."""
        log_tool_result(tool_result, self.name)

    def _format_tool_result(
        self, result: Any, tool_name: str, tool_id: str
    ) -> FunctionExecutionResult:
        """Format a tool result for use in the conversation."""
        return format_tool_result(result, tool_name, tool_id, self.name)

    #############################
    # Core Conversation Methods
    #############################

    async def _run_tool_conversation(self, messages: List[Any]) -> Any:
        """
        Run a conversation that may involve tool calls, but bail out after
        `self.max_tool_rounds` (default 2).  The final turn is a plain-text
        summary request with *no* tools supplied, so the model cannot call
        another function.
        """
        max_rounds = getattr(self, "max_tool_rounds", 2)
        rounds = 0
        conversation = list(messages)
        tools_list = list(self._tools_dict.values())

        while True:
            rounds += 1
            self.log(f"Calling LLM (tool round {rounds})...")
            response = await self.model_client.create(
                messages=conversation,
                tools=tools_list,
            )

            # ── If the model wants to call tools ──────────────────────
            if hasattr(response, "content") and isinstance(response.content, list):
                if rounds >= max_rounds:
                    self.log(
                        f"{self.name}: reached max_tool_rounds={max_rounds}; "
                        "stopping further tool calls."
                    )
                    break

                # record the tool call then execute it
                tool_calls = response.content
                conversation.append(AssistantMessage(content=tool_calls, source="assistant"))
                tool_results = await self._process_tool_calls(tool_calls)
                conversation.append(FunctionExecutionResultMessage(content=tool_results))
                continue  # go to next round

            # ── No tool call → return assistant answer ─────────────
            return response

        # ── Ask for a text-only summary (no tools param!) ─────────────
        summary = await self.model_client.create(
            messages=conversation
            + [
                AssistantMessage(
                    content=(
                        "Summarize these findings in a final answer. " "Do NOT call any more tools."
                    ),
                    source="assistant",
                )
            ]
        )
        return summary

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

            # Log the tool call
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
                        content=error_message, call_id=tool_id, is_error=True, name=tool_name
                    )
                )

        return tool_results

    #############################
    # Public API Methods
    #############################

    def process_with_tools(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Union[str, Awaitable[str]]:
        """
        Process a prompt with the LLM, supporting tool calling.
        This method provides the core tool calling functionality that specific agents can build upon.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response or a coroutine to be awaited.
        """
        try:
            messages = self._build_message_sequence(prompt, system_prompt)
            try:
                asyncio.get_running_loop()
                in_loop = True
            except RuntimeError:
                in_loop = False

            if in_loop:
                return self.process_with_tools_async(prompt, system_prompt)
            else:
                response = asyncio.run(self._run_tool_conversation(messages))
                return self._extract_content(response)
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"

    async def process_with_tools_async(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """
        Async version of process_with_tools - for use when already in an event loop.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response.
        """
        try:
            messages = self._build_message_sequence(prompt, system_prompt)
            response = await self._run_tool_conversation(messages)
            return self._extract_content(response)
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"

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

    #############################
    # Memory Management Methods
    #############################

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
        """
        Stores data in the context layer of memory.
        """
        if self.memory_system:
            self.memory_system.store_data(key, data, layer="context")

    def retrieve_data_from_context(self, key: str):
        """
        Retrieves data from the context layer of memory.
        """
        if self.memory_system:
            return self.memory_system.retrieve_data(key, layer="context")
        return None

    def set_logger(self, logger: Any) -> None:
        """
        Attaches a logger to this agent for debugging and audit trails.

        :param logger: A logging instance (e.g., Python's built-in logging).
        """
        self.logger = logger

    @abstractmethod
    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.
        Must be implemented by all subclasses.

        :param messages: List of messages in the conversation.
        :param context: Optional context from AutoGen.
        :return: The agent's response.
        """
        pass
