# base_agent.py
"""
Base class for the trading agents, on Microsoft Agent Framework (#606; it was AutoGen).

An agent's own work (voting, scanning, risk checks) is plain Python. For free-text
requests, process_with_tools() runs an Agent Framework Agent with the agent's tools:
the model may call tools for up to max_tool_rounds round trips, then must answer in
text. The OpenAI client is created on first use, so an agent that never calls the LLM
needs no API key.
"""

import asyncio
import os
import traceback
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Dict, List, Optional, Union

import openai
from agent_framework import Agent, FunctionInvocationConfiguration
from agent_framework.openai import OpenAIChatCompletionClient

from src.autogen_agents.tools import ALL_TOOLS

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

# Model round trips in which tools may be called before the model must answer in text
DEFAULT_MAX_TOOL_ROUNDS = 2


class BaseAgent(ABC):
    """
    Abstract base class for the trading agents.

    Provides the agent's name and tools, LLM conversations with tool calling
    (process_with_tools), an optional memory system and logging.
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
        :param tools: List of tools (Agent Framework FunctionTools) the agent can use.
        :param memory_system: Optional memory interface for knowledge storage and retrieval.
        :param llm_config: Optional dictionary containing LLM settings (temperature, etc).
        :param use_dual_models: If True, use the tool-calling model (OPENAI_TOOL_MODEL)
            instead of the default one. Default False - most agents use pure
            calculations without LLM calls.
        """
        self._name = name
        self.description = f"{name} agent"

        llm_params = DEFAULT_LLM_CONFIG.copy()
        if llm_config:
            llm_params.update(llm_config)
        self.llm_config = llm_params

        self.tools: List[Any] = [tool for tool in (ALL_TOOLS if tools is None else tools) if tool]
        self._tools_dict = {tool.name: tool for tool in self.tools}

        self.memory_system = memory_system
        self.use_dual_models = use_dual_models
        self.max_tool_rounds = DEFAULT_MAX_TOOL_ROUNDS
        self._model_client: Optional[OpenAIChatCompletionClient] = None

    @property
    def name(self) -> str:
        """The agent's name (read-only)."""
        return self._name

    @property
    def model_client(self) -> OpenAIChatCompletionClient:
        """The OpenAI chat client, created on first use (needs an API key then)."""
        if self._model_client is None:
            self._model_client = self._create_model_client()
        return self._model_client

    def _create_model_client(self) -> OpenAIChatCompletionClient:
        if not open_ai_key:
            raise ValueError(
                "OpenAI API key not found. Set the OPEN_AI_KEY environment variable or "
                "add OPEN_AI_KEY to config/config.json."
            )
        async_client = openai.AsyncOpenAI(
            api_key=open_ai_key,
            timeout=self.llm_config.get("timeout", 120),
            max_retries=self.llm_config.get("max_retries", 3),
        )
        return OpenAIChatCompletionClient(
            model=tool_model_name if self.use_dual_models else model_name,
            async_client=async_client,
            function_invocation_configuration=FunctionInvocationConfiguration(
                max_iterations=self.max_tool_rounds
            ),
        )

    def _chat_options(self) -> Dict[str, Any]:
        return {
            "temperature": self.llm_config.get("temperature", 0.2),
            "max_tokens": self.llm_config.get("max_tokens", 4096),
            "top_p": self.llm_config.get("top_p", 0.95),
        }

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
    # Public API Methods
    #############################

    def process_with_tools(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> Union[str, Awaitable[str]]:
        """
        Process a prompt with the LLM, supporting tool calling.

        Inside a running event loop this returns a coroutine to await; otherwise it
        runs the conversation and returns the text.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response or a coroutine to be awaited.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.process_with_tools_async(prompt, system_prompt))
        return self.process_with_tools_async(prompt, system_prompt)

    async def process_with_tools_async(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """
        Async version of process_with_tools - for use when already in an event loop.

        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response text, or an error message.
        """
        try:
            agent = Agent(
                client=self.model_client,
                instructions=system_prompt,
                name=self.name,
                tools=self.tools,
                default_options=self._chat_options(),
            )
            response = await agent.run(prompt)
            return response.text
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"

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
        Handle incoming messages. Must be implemented by all subclasses.

        :param messages: List of messages in the conversation.
        :param context: Optional context.
        :return: The agent's response.
        """
        pass
