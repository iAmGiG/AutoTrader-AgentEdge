# base_agent.py
"""
Base module defining an abstract agent class that all specialized agents inherit from.
"""


from autogen_agentchat.agents._assistant_agent import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from config.config_loader import ConfigLoader
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from src.tools.tools import ALL_TOOLS

# Instantiate ConfigLoader once at module-level
_loader = ConfigLoader()
model_name = _loader.get("open_model")     # e.g. "gpt-4o-mini"
open_ai_key = _loader.get("open_ai_key")

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
        model_client_instance = OpenAIChatCompletionClient(
            model=model_name,
            api_key=open_ai_key,
            temperature=llm_params.get("temperature", 0.2),
            max_tokens=llm_params.get("max_tokens", 4096),
            top_p=llm_params.get("top_p", 0.95),
        )
        
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
        
        # 7. Store the LLM configuration
        self.llm_config = llm_params

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
        Process a prompt with the LLM directly, without invoking the full AutoGen infrastructure.
        This is useful for generating narratives or processing structured data into text.
        
        :param prompt: The user prompt to process.
        :param system_prompt: Optional system prompt to provide context.
        :return: The LLM's response.
        """
        # This is a simplified version of what would happen in a real implementation
        # In a full implementation, we would use the model_client directly to call the LLM
        # For now, we'll return a placeholder message
        return f"LLM would process: {prompt[:30]}..."

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
