# OpenAIChatCompletionClient Reference

This document provides a reference for the `OpenAIChatCompletionClient` class from `autogen_ext.models.openai` as used in the RH2MAS project.

## OpenAIChatCompletionClient Class

The OpenAIChatCompletionClient is a client for OpenAI's chat completion API that handles function/tool calling in AutoGen 0.5.x.

```python
from autogen_ext.models.openai import OpenAIChatCompletionClient

client = OpenAIChatCompletionClient(
    model="gpt-4o-mini",
    api_key="your_api_key",
    temperature=0.2,
    max_tokens=4096,
    top_p=0.95,
    timeout=120,
    max_retries=3
)
```

### Constructor Parameters

- `model`: OpenAI model name (e.g., "gpt-4o-mini")
- `api_key`: OpenAI API key
- `temperature`: Controls randomness (lower is more deterministic)
- `max_tokens`: Maximum tokens in the response
- `top_p`: Controls diversity of responses
- `timeout`: Request timeout in seconds
- `max_retries`: Number of retry attempts for failed requests

## Key Methods

### create

```python
async def create(self, messages: List[Any], tools: List[Any] = None) -> Any:
    """
    Create a chat completion with optional tool calling.
    
    :param messages: List of message objects (SystemMessage, UserMessage, etc.)
    :param tools: List of tool objects (FunctionTool instances)
    :return: Response object with content attribute
    """
    # Implementation details...
```

The primary method to generate responses. It accepts a list of messages and optional tools.

## Usage in RH2MAS

### Initialization in BaseAgent

```python
# Create the LLM client instance for function calling
client_config = {
    "model": model_name,  # e.g., "gpt-4o-mini"
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

# Store model_client instance for direct access by subclasses
self.model_client = model_client_instance
```

### Usage for Tool Calling

```python
async def _run_tool_conversation(self, messages: List[Any]) -> Any:
    """
    Run a conversation with the LLM that may involve tool calling.
    """
    # Initialize conversation history for this interaction
    conversation = messages.copy()

    # Set up tools for the LLM to use
    tools_list = list(self._tools_dict.values())

    # First LLM call - might return tool calls
    response = await self.model_client.create(messages=conversation, tools=tools_list)

    # Check if the response contains tool calls
    if hasattr(response, 'content') and isinstance(response.content, list):
        # Process tool calls...
        # Add tool results to conversation...
        
        # Second LLM call with tool results
        final_response = await self.model_client.create(messages=conversation)
        return final_response

    # If no tool calls, just return the initial response
    return response
```

## Response Handling

Responses from `model_client.create()` have a `content` attribute that can be:

1. A string (for regular text responses)
2. A list of tool call objects (when the LLM decides to use tools)

```python
# Extracting response content
if hasattr(response, 'content'):
    if isinstance(response.content, str):
        return response.content
    else:
        # This could be tool calls or another format
        return str(response.content)
else:
    return str(response)
```

## Best Practices

1. **Client Configuration**:
   - Use lower temperature (0.2-0.3) for more deterministic function calling
   - Set appropriate max_tokens based on expected response length
   - Configure sensible timeout and retry settings

2. **Tool Integration**:
   - Pass tools as a list to the `create` method
   - Ensure tools have clear descriptions and parameter definitions
   - Handle both text responses and tool call responses

3. **Async Operations**:
   - Always use `await` with `model_client.create()`
   - Run in an async context or use `asyncio.run()`
   - Handle potential exceptions from async operations

4. **Response Processing**:
   - Check response.content for both string responses and tool calls
   - Process tool calls appropriately before making follow-up requests
   - Extract final content carefully from the response object