# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
"""

from autogen import Agent
from autogen.config import AgentConfig
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAgent(Agent, ABC):
    """
    Abstract base class for AutoGen-based agents.
    Encapsulates common functionalities such as:
      - Configuration handling via AutoGen's AgentConfig
      - Memory system access for knowledge retrieval
      - Tool registration and usage
    """

    def __init__(self, name: str, config: dict, memory_system: Optional[Any] = None):
        """
        :param name: Unique name/identifier for this agent.
        :param config: A dictionary containing agent settings.
        :param memory_system: Optional memory interface for knowledge storage and retrieval.
        """
        agent_config = AgentConfig(
            **config)  # Convert config dict to AutoGen's AgentConfig
        super().__init__(name=name, config=agent_config)

        self.memory_system = memory_system
        self.tools = {}

        # Register memory retrieval as a callable tool
        if self.memory_system:
            self.register_function(
                self.retrieve_from_memory, "retrieve_memory")

    @abstractmethod
    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.

        :param messages: List of messages in the conversation.
        :param context: Optional context from AutoGen.
        :return: The agent's response.
        """
        pass

    def load_tool(self, tool_name: str, tool_instance: Any) -> None:
        """
        Registers a tool for agent use.
        """
        self.tools[tool_name] = tool_instance
        self.register_function(tool_instance, tool_name)

    # def query_market_data(self, symbol: str, start_date: str, end_date: str):
    #     if "market_data" not in self.tools:
    #         raise ValueError("MarketDataTool not loaded")
    #     return self.use_tool("market_data").fetch_options_data(symbol, start_date, end_date)

    # def preprocess_data(self, data: pd.DataFrame) -> dict:
    #     """
    #     Convert raw market data into a dictionary of signals
    #     or features for agent logic.
    #     """
    #     return data.to_dict("records")  # Example

    def use_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """
        Invokes a registered tool.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found.")
        return self.tools[tool_name](*args, **kwargs)

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
