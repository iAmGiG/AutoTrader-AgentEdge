# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
"""


from autogen_agentchat.agents._assistant_agent import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from config.config_loader import ConfigLoader
from abc import ABC, abstractmethod
from typing import Any, Optional
from src.tools.tools import ALL_TOOLS

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()
model_name = _loader.get("open_model")     # e.g. "gpt-4o-mini"
open_ai_key = _loader.get("open_ai_key")


class BaseAgent(AssistantAgent, ABC):
    """
    Abstract base class for AutoGen-based agents.
    Encapsulates common functionalities such as:
      - Configuration handling via AutoGen's AgentConfig
      - Memory system access for knowledge retrieval
      - Tool registration and usage
    """

    def __init__(self, name: str, tools=None, memory_system: Optional[Any] = None):
        """
        :param name: Unique name/identifier for this agent.
        :param config: A dictionary containing agent settings (model keys, tool config, etc.).
        :param memory_system: Optional memory interface for knowledge storage and retrieval.
        """
        # 1. Create the actual client instance required by AssistantAgent
        # Here we create the actual client instance required by AssistantAgent
        model_client_instance = OpenAIChatCompletionClient(
            model=model_name,  # <-- The library specifically needs this 'model' param
            api_key=open_ai_key,
            # Add other optional parameters if desired:
            # organization="...",
            # temperature=0.7,
            # max_tokens=2048,
            # etc.
        )
        tools = tools or ALL_TOOLS
        # 2. If no tools are provided, default to an empty list
        if tools is None:
            tools = []

        # 3. Call the parent constructor
        super().__init__(
            name=name,
            model_client=model_client_instance,
            tools=tools,  # <--- Tools are passed directly to AssistantAgent
            description=f"{name} agent",  # or read from config if needed
            reflect_on_tool_use=True,     # e.g. let the agent reflect on tool calls
            tool_call_summary_format="{result}",
        )
        # Store the tools in a local dict for manual calls as needed
        self._tools_dict = {tool.name: tool for tool in tools}
        # 4. Memory system
        self.memory_system = memory_system

    def use_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Here we manually invoke a tool by name with the given keyword arguments
        If we need to pass position args, we then add them to the kw args or revise the method signature
        """
        tool = self._tools_dict.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found {tool_name}")
        # if we have a tool, then it is call able, then give it the kw args
        return tool(**kwargs)

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
        if self.logger:
            self.logger.info(f"[{self.name}] {message}")
        else:
            # For quick debugging, fallback to print or pass
            print(f"[{self.name}] {message}")
