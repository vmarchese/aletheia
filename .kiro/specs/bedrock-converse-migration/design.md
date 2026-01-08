# Design Document: Bedrock Converse API Migration

## Overview

This design document outlines the migration of Aletheia's Bedrock integration from the legacy `invoke_model` API to the modern `converse` API. The Converse API provides a standardized interface for interacting with foundation models on Amazon Bedrock, offering improved consistency, better streaming support, and enhanced functionality.

The migration will replace the current JSON-based request/response format with the Converse API's structured message format while maintaining backward compatibility with the existing `BaseChatClient` interface.

## Architecture

### Current Architecture
```
BedrockChatClient
├── _inner_get_response() → invoke_model()
├── _inner_get_streaming_response() → simulate streaming
├── _convert_messages_to_bedrock() → JSON format
└── _create_chat_response() → parse JSON response
```

### New Architecture
```
BedrockChatClient
├── _inner_get_response() → converse()
├── _inner_get_streaming_response() → converse_stream()
├── _convert_messages_to_converse() → Converse message format
├── _create_chat_response() → parse Converse response
└── _process_stream_events() → handle streaming events
```

### Key Changes
1. **API Method**: Replace `invoke_model()` with `converse()`
2. **Streaming**: Replace simulated streaming with native `converse_stream()`
3. **Message Format**: Convert from JSON body to structured message arrays
4. **Response Processing**: Handle Converse API response structure
5. **Error Handling**: Update for Converse API specific errors

## Components and Interfaces

### BedrockChatClient Class

The main client class will be updated to use the Converse API while maintaining the same public interface:

```python
class BedrockChatClient(BaseChatClient):
    def __init__(self, model_id: str, region: str = "us-east-1"):
        # Initialize boto3 bedrock-runtime client
        
    async def _inner_get_response(self, *, messages, chat_options, **kwargs) -> ChatResponse:
        # Convert messages to Converse format
        # Call bedrock_client.converse()
        # Convert response to ChatResponse
        
    async def _inner_get_streaming_response(self, *, messages, chat_options, **kwargs) -> AsyncIterable[ChatResponseUpdate]:
        # Convert messages to Converse format  
        # Call bedrock_client.converse_stream()
        # Process event stream and yield updates
```

### Message Conversion Component

```python
class ConverseMessageConverter:
    def convert_to_converse_format(self, messages: Sequence[ChatMessage]) -> Dict[str, Any]:
        # Convert ChatMessage objects to Converse API format
        # Separate system messages from conversation messages
        # Return: {"system": [...], "messages": [...]}
        
    def extract_system_messages(self, messages: Sequence[ChatMessage]) -> List[Dict[str, str]]:
        # Extract and format system messages
        
    def convert_conversation_messages(self, messages: Sequence[ChatMessage]) -> List[Dict[str, Any]]:
        # Convert user/assistant messages to Converse format
```

### Response Processing Component

```python
class ConverseResponseProcessor:
    def create_chat_response(self, converse_response: Dict[str, Any], model_id: str) -> ChatResponse:
        # Convert Converse API response to ChatResponse format
        # Extract message content, usage details, and metadata
        
    def process_streaming_event(self, event: Dict[str, Any]) -> Optional[ChatResponseUpdate]:
        # Process individual streaming events
        # Handle contentBlockStart, contentBlockDelta, messageStop events
```

### Tool Use Support Components

```python
class ConverseToolConverter:
    def convert_tools_to_converse_format(self, tools: Sequence[ToolProtocol]) -> List[Dict[str, Any]]:
        # Convert ToolProtocol objects to Bedrock tool definitions
        # Return list of tool definitions for Converse API
        
    def convert_tool_choice_to_converse_format(self, tool_choice: Any) -> Dict[str, Any]:
        # Convert tool choice parameter to Converse API format
        # Support "auto", "any", "none", or specific tool selection

class ConverseToolResponseProcessor:
    def extract_tool_calls_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Extract tool calls from Converse API response
        # Handle tool_use content blocks
        
    def create_tool_result_message(self, tool_call_id: str, result: str) -> Dict[str, Any]:
        # Create tool result message for subsequent conversation
        # Format tool results for Converse API
```

## Data Models

### Converse API Request Format
```python
{
    "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
    "messages": [
        {
            "role": "user",
            "content": [
                {"text": "Hello, how are you?"}
            ]
        }
    ],
    "system": [
        {"text": "You are a helpful assistant."}
    ],
    "inferenceConfig": {
        "temperature": 0.5,
        "maxTokens": 4000
    },
    "additionalModelRequestFields": {
        "top_k": 200
    },
    "toolConfig": {
        "tools": [
            {
                "toolSpec": {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state"
                                }
                            },
                            "required": ["location"]
                        }
                    }
                }
            }
        ],
        "toolChoice": {
            "auto": {}
        }
    }
}
```

### Tool Use Request Format
```python
{
    "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
    "messages": [
        {
            "role": "user",
            "content": [
                {"text": "What's the weather in Seattle?"}
            ]
        }
    ],
    "toolConfig": {
        "tools": [
            {
                "toolSpec": {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"}
                            },
                            "required": ["location"]
                        }
                    }
                }
            }
        ],
        "toolChoice": {"auto": {}}
    }
}
}
```

### Converse API Response Format
```python
{
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {"text": "Hello! I'm doing well, thank you for asking."}
            ]
        }
    },
    "stopReason": "end_turn",
    "usage": {
        "inputTokens": 10,
        "outputTokens": 12,
        "totalTokens": 22
    },
    "metrics": {
        "latencyMs": 1234
    }
}
```

### Tool Use Response Format
```python
{
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tooluse_123",
                        "name": "get_weather",
                        "input": {
                            "location": "Seattle"
                        }
                    }
                }
            ]
        }
    },
    "stopReason": "tool_use",
    "usage": {
        "inputTokens": 15,
        "outputTokens": 8,
        "totalTokens": 23
    }
}
```

### Tool Result Message Format
```python
{
    "role": "user",
    "content": [
        {
            "toolResult": {
                "toolUseId": "tooluse_123",
                "content": [
                    {"text": "The weather in Seattle is 72°F and sunny."}
                ]
            }
        }
    ]
}
```

### Streaming Event Format
```python
# Content block start
{
    "contentBlockStart": {
        "start": {
            "text": ""
        },
        "contentBlockIndex": 0
    }
}

# Content block delta
{
    "contentBlockDelta": {
        "delta": {
            "text": "Hello"
        },
        "contentBlockIndex": 0
    }
}

# Message stop
{
    "messageStop": {
        "stopReason": "end_turn"
    }
}

# Metadata
{
    "metadata": {
        "usage": {
            "inputTokens": 10,
            "outputTokens": 12,
            "totalTokens": 22
        },
        "metrics": {
            "latencyMs": 1234
        }
    }
}
```

## Implementation Details

### Message Format Conversion

The current implementation converts messages to a JSON body with `anthropic_version` and model-specific formatting. The new implementation will use the standardized Converse message format:

**Current Format:**
```python
body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": max_tokens,
    "messages": [{"role": "user", "content": "text"}],
    "system": "system prompt"
}
```

**New Format:**
```python
request = {
    "modelId": model_id,
    "messages": [
        {
            "role": "user", 
            "content": [{"text": "text"}]
        }
    ],
    "system": [{"text": "system prompt"}],
    "inferenceConfig": {
        "maxTokens": max_tokens,
        "temperature": 0.5
    }
}
```

### Streaming Implementation

The current implementation simulates streaming by yielding the complete response. The new implementation will use native streaming:

```python
async def _inner_get_streaming_response(self, *, messages, chat_options, **kwargs):
    converse_messages = self._convert_messages_to_converse(messages)
    
    response = self.bedrock_client.converse_stream(
        modelId=self.model_id,
        messages=converse_messages["messages"],
        system=converse_messages["system"],
        inferenceConfig=self._build_inference_config(chat_options)
    )
    
    current_text = ""
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta_text = event["contentBlockDelta"]["delta"]["text"]
            current_text += delta_text
            
            yield ChatResponseUpdate(
                role=Role.ASSISTANT,
                contents=[TextContent(text=delta_text)],
                model_id=self.model_id,
                # ... other fields
            )
```

### Error Handling

Update error handling to work with Converse API specific exceptions:

```python
try:
    response = self.bedrock_client.converse(...)
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'ValidationException':
        # Handle validation errors (invalid model ID, etc.)
    elif error_code == 'AccessDeniedException':
        # Handle permission errors
    elif error_code == 'ThrottlingException':
        # Handle rate limiting
    else:
        # Handle other errors
    
    raise ServiceResponseException(
        f"Bedrock Converse API failed: {e.response['Error']['Message']}",
        inner_exception=e
    )
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: API Method Selection
*For any* request type (streaming or non-streaming), the system should call the appropriate Converse API method (`converse` for regular requests, `converse_stream` for streaming requests) instead of the legacy `invoke_model` method.
**Validates: Requirements 1.1, 3.1**

### Property 2: Message Format Conversion
*For any* sequence of ChatMessage objects, the conversion to Converse format should produce a valid structure with properly formatted messages array and system array, where user/assistant messages have the correct role and content structure, and system messages are extracted to the system parameter.
**Validates: Requirements 1.2, 2.1, 2.2, 2.3, 2.4, 2.5**

### Property 3: Parameter Structure Compliance
*For any* chat options and model configuration, the system should format inference parameters in the `inferenceConfig` structure and model-specific parameters in the `additionalModelRequestFields` structure according to Converse API specifications.
**Validates: Requirements 1.4, 1.5**

### Property 4: Streaming Event Processing
*For any* streaming response event sequence, the system should handle the event stream format correctly, yielding ChatResponseUpdate objects incrementally for content deltas and providing final usage statistics when the stream completes.
**Validates: Requirements 3.2, 3.3, 3.4**

### Property 5: Response Format Conversion
*For any* valid Converse API response, the system should correctly extract the output message, convert content blocks to TextContent objects, map usage information to UsageDetails format, map stopReason to FinishReason values, and generate appropriate response metadata.
**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

### Property 6: Error Handling Completeness
*For any* Converse API error (ClientError), the system should catch the exception, provide descriptive error messages for validation errors, indicate permission issues clearly for access denied errors, and handle throttling appropriately for rate limit errors.
**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

### Property 7: Backward Compatibility Preservation
*For any* existing client usage pattern, the public interface should remain unchanged, responses should maintain the same ChatResponse structure, the same environment variables should be accepted, the same model identifiers should be supported, and region handling should work identically.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 8: Thread Safety and Performance
*For any* concurrent client usage, the system should maintain thread safety, reuse the boto3 client instance across calls, and handle multiple simultaneous requests without data corruption or race conditions.
**Validates: Requirements 7.1, 7.5**

### Property 9: Tool Use Support
*For any* set of tools provided to the chat client, the system should convert them to valid Bedrock tool definitions, handle tool_use content blocks in responses, process tool results in subsequent messages, and support tool choice parameters correctly.
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

## Error Handling

The migration will update error handling to work with Converse API specific exceptions while maintaining the same error interface for the rest of the application:

### Exception Mapping
- `ValidationException` → Invalid model ID or malformed request
- `AccessDeniedException` → Insufficient permissions for model access
- `ThrottlingException` → Rate limiting exceeded
- `ServiceQuotaExceededException` → Service limits exceeded
- `InternalServerException` → AWS service internal errors

### Error Response Format
All errors will be wrapped in `ServiceResponseException` with descriptive messages that include the original AWS error details while maintaining compatibility with existing error handling code.

## Testing Strategy

### Unit Testing
- **Message Conversion Tests**: Verify ChatMessage to Converse format conversion
- **Response Processing Tests**: Verify Converse response to ChatResponse conversion  
- **Error Handling Tests**: Test all error scenarios with mock ClientError exceptions
- **Configuration Tests**: Verify environment variable processing and client initialization
- **Interface Compatibility Tests**: Ensure public interface remains unchanged

### Property-Based Testing
The testing strategy will use **Hypothesis** for property-based testing in Python. Each correctness property will be implemented as a property-based test with minimum 100 iterations.

**Property Test Configuration:**
- Library: Hypothesis (Python property-based testing framework)
- Iterations: Minimum 100 per property test
- Test Tags: **Feature: bedrock-converse-migration, Property {number}: {property_text}**

**Dual Testing Approach:**
- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs
- Both approaches are complementary and necessary for comprehensive coverage

### Integration Testing
- **Mock Bedrock Service**: Test with mocked boto3 client responses
- **End-to-End Flows**: Verify complete request/response cycles
- **Streaming Tests**: Test streaming functionality with mock event streams
- **Performance Tests**: Verify no significant performance regression

### Compatibility Testing
- **Regression Tests**: Ensure existing functionality continues to work
- **Interface Tests**: Verify public API compatibility
- **Configuration Tests**: Test with existing environment variable configurations

Now I need to use the prework tool to analyze the acceptance criteria before writing the correctness properties:

<function_calls>
<invoke name="prework">
<parameter name="featureName">bedrock-converse-migration