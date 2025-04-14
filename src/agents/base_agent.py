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
            # Import the proper message types from autogen_core
            from autogen_core.models import SystemMessage, UserMessage
            import asyncio
            
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
            import traceback
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
            # Import the proper message types from autogen_core
            from autogen_core.models import SystemMessage, UserMessage, AssistantMessage, FunctionExecutionResult, FunctionExecutionResultMessage
            import asyncio
            
            # Build the messages array with the correct message types
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            
            # Add the user prompt with the correct message type
            messages.append(UserMessage(content=prompt, source="user"))
            
            # Define async function to handle LLM interaction with tool calling
            async def async_call_llm_with_tools():
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
                    
                    # Add the assistant's response with tool calls to the conversation
                    conversation.append(AssistantMessage(content=tool_calls, source="assistant"))
                    
                    # Process each tool call
                    tool_results = []
                    for tool_call in tool_calls:
                        tool_name = tool_call.name
                        tool_args = tool_call.arguments
                        tool_id = tool_call.id
                        
                        # Print better diagnostic info about the tool call
                        if isinstance(tool_args, dict):
                            args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                        else:
                            args_str = str(tool_args)
                        print(f"- LLM is using tool: {tool_name}({args_str})")
                        
                        # Execute the tool
                        try:
                            # Get the actual tool from the tools dict
                            tool = self._tools_dict.get(tool_name)
                            if not tool:
                                raise ValueError(f"Tool not found: {tool_name}")
                                
                            # Parse the tool arguments in a clean way
                            parsed_args = self._parse_tool_arguments(tool_args)
                            
                            # Execute the tool with proper error handling
                            try:
                                # Convert parsed_args to a dictionary and pass to the tool
                                if isinstance(parsed_args, dict):
                                    # Call the tool with the parsed arguments
                                    tool_result = tool.func(**parsed_args)
                                else:
                                    self.log(f"Error: parsed_args is not a dictionary: {type(parsed_args)}")
                                    tool_result = f"Error: Could not parse tool arguments properly"
                            except Exception as e:
                                self.log(f"Error executing tool {tool_name}: {str(e)}")
                                tool_result = f"Error executing {tool_name}: {str(e)}"
                            
                            # Let the subclass process the result if needed
                            processed_result = self.process_tool_result(tool_name, tool_result, parsed_args)
                            
                            # Convert processed result to JSON serializable format if needed
                            if hasattr(processed_result, 'to_dict'):
                                # For pandas DataFrames or objects with to_dict method
                                processed_result = processed_result.to_dict(orient='records')
                            
                            # Add the result to our list
                            tool_results.append(
                                FunctionExecutionResult(
                                    content=processed_result,
                                    call_id=tool_id,
                                    is_error=False,
                                    name=tool_name
                                )
                            )
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
                    
                    # Add the tool results to the conversation
                    if tool_results:
                        conversation.append(FunctionExecutionResultMessage(content=tool_results))
                    
                    # Call the LLM again with the tool results
                    print("- Calling LLM to generate final response with tool results...")
                    final_response = await self.model_client.create(messages=conversation)
                    return final_response
                
                # If no tool calls, just return the initial response
                return response
            
            # Run the async function and get the response
            response = asyncio.run(async_call_llm_with_tools())
            
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
            import traceback
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            return f"Error processing with LLM: {str(e)}"
            
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
                    self.log(f"Warning: Parsed JSON is not a dictionary: {parsed_args}")
                    return {}
            except json.JSONDecodeError as e:
                self.log(f"Warning: Failed to parse tool arguments as JSON: {e}")
                return {}
        else:
            # Unknown format
            self.log(f"Warning: Unknown tool arguments format: {type(tool_args)}")
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
