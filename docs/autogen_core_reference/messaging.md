# AutoGen Core Messaging Reference

This document provides a reference for the messaging-related classes from `autogen_core.models` used in the RH2MAS project.

## Core Message Types

### SystemMessage

```python
from autogen_core.models import SystemMessage

system_message = SystemMessage(content="You are a financial analyst...")
```

Used for providing system-level instructions to the LLM. This is typically used for setting up context, defining the assistant's role, or providing background information.

### UserMessage

```python
from autogen_core.models import UserMessage

user_message = UserMessage(content="Analyze the recent market trends", source="user")
```

Represents a message from the user. The `source` parameter typically identifies the origin of the message.

### AssistantMessage

```python
from autogen_core.models import AssistantMessage

assistant_message = AssistantMessage(content="Based on my analysis...", source="assistant")
```

Represents a message from the assistant. Can contain text responses or, in the case of tool calls, a list of tool call objects.

## Tool-Related Message Types

### FunctionExecutionResult

```python
from autogen_core.models import FunctionExecutionResult

result = FunctionExecutionResult(
    content="Result data in string format",
    call_id="unique_id_from_tool_call",
    is_error=False,
    name="tool_name"
)
```

Represents the result of executing a tool. Parameters:
- `content`: The result data as a string
- `call_id`: ID matching the original tool call
- `is_error`: Boolean indicating if an error occurred
- `name`: Name of the tool that was called

### FunctionExecutionResultMessage

```python
from autogen_core.models import FunctionExecutionResultMessage

result_message = FunctionExecutionResultMessage(content=[result1, result2])
```

A container for one or more tool execution results. Used to add tool results to the conversation history.

## Usage Patterns in RH2MAS

### Creating a Conversation

```python
def _build_message_sequence(self, prompt: str, system_prompt: Optional[str] = None) -> List[Any]:
    """
    Build a sequence of messages for the conversation with the LLM.
    """
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(UserMessage(content=prompt, source="user"))
    return messages
```

### Processing Tool Calls

```python
# Add the assistant's response with tool calls to the conversation
conversation.append(AssistantMessage(content=tool_calls, source="assistant"))

# Process tool calls and get results...

# Add the tool results to the conversation
if tool_results:
    conversation.append(FunctionExecutionResultMessage(content=tool_results))
```

### Creating Tool Results

```python
tool_results.append(
    FunctionExecutionResult(
        content=json.dumps(result_dict),
        call_id=tool_id,
        is_error=False,
        name=tool_name
    )
)
```

## Best Practices

1. **Message Sequence**:
   - Always start with a SystemMessage for context (when applicable)
   - Follow with UserMessage to represent the query
   - Add AssistantMessage with tool calls when tools are invoked
   - Add FunctionExecutionResultMessage with results after tool execution

2. **Result Formatting**:
   - Tool results must be converted to strings before being added to FunctionExecutionResult
   - Complex data types should be JSON-serialized
   - DataFrames should be converted to dictionaries first: `df.to_dict(orient='records')`

3. **Error Handling**:
   - Always set `is_error=True` in FunctionExecutionResult when an error occurs
   - Provide clear error messages in the content
   - Log detailed information for debugging

4. **Conversation Management**:
   - Maintain conversation history correctly by appending messages in order
   - Include all relevant messages when calling the LLM