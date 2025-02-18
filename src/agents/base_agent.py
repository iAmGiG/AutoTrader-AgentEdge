# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAgent(ABC):
    """
    An abstract base class for all agents in the system.
    Encapsulates common functionalities like:
      - Configuration handling
      - Memory system access
      - Custom tool usage
      - Basic message handling
    """

    def __init__(self,
                 name: str,
                 config: dict,
                 memory_system: Optional[Any] = None):
        """
        :param name: Unique name/identifier for this agent.
        :param config: A dictionary-like object containing agent or system configuration.
        :param memory_system: A memory interface/class instance used for storing/retrieving data.
        """
        self.name = name
        self.config = config
        self.memory_system = memory_system
        self.logger = None  # Optionally, attach a logging mechanism here
        self.tools = {}  # Custom tools or APIs can be stored here when initialized

    @abstractmethod
    def handle_message(self, message: str) -> str:
        """
        Processes an incoming message and returns a response.
        Specialized agents must implement their own logic for handling messages.

        :param message: Incoming message (command, query, etc.).
        :return: A string response or output from this agent.
        """
        pass

    def load_tool(self, tool_name: str, tool_instance: Any) -> None:
        """
        Adds a custom tool or API handle to this agent's toolset.

        :param tool_name: The name or key for the tool.
        :param tool_instance: The object/instance providing the tool functionality.
        """
        self.tools[tool_name] = tool_instance

    def use_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """
        Invokes a previously loaded tool with provided arguments.

        :param tool_name: The name of the tool to invoke.
        :param args: Positional arguments for the tool call.
        :param kwargs: Keyword arguments for the tool call.
        :return: The result or output from the tool.
        """
        if tool_name not in self.tools:
            raise ValueError(
                f"Tool '{tool_name}' not found. Please load it first.")
        return self.tools[tool_name](*args, **kwargs)

    def store_in_memory(self, key: str, data: Any) -> None:
        """
        Stores data in the memory system under the specified key.

        :param key: Unique identifier for the memory entry.
        :param data: The data to store.
        """
        if self.memory_system:
            self.memory_system.store_data(key, data)

    def retrieve_from_memory(self, key: str) -> Any:
        """
        Retrieves data from the memory system using the specified key.

        :param key: The key identifying the stored data.
        :return: The retrieved data or None if no entry is found.
        """
        if self.memory_system:
            return self.memory_system.retrieve_data(key)
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
