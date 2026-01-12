"""
Bedrock chat client wrapper that adds response_format support at the chat client level.

This wrapper intercepts the chat client's get_streaming_response method where
tool definitions are actually sent to the LLM, providing better control over
structured output without interfering with tool calling.
"""
import json
import re
from copy import deepcopy
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from agent_framework import ChatMessage, TextContent, Role
from agent_framework._types import ChatOptions, ChatResponseUpdate
from aletheia.utils.logging import log_debug, log_error


class BedrockChatClientResponseWrapper:
    """Wrapper for chat response objects that matches the expected interface."""
    
    def __init__(self, text: str, **kwargs):
        """Initialize response wrapper.
        
        Args:
            text: The response text
            **kwargs: Additional attributes to set on the wrapper
        """
        self.text = text
        # Set any additional attributes from the original response
        for key, value in kwargs.items():
            setattr(self, key, value)


class BedrockChatClientWrapper:
    """Wrapper that adds response_format support to Bedrock chat clients."""
    
    def __init__(self, chat_client):
        """Initialize the wrapper with a chat client instance.
        
        Args:
            chat_client: The Bedrock chat client instance to wrap
        """
        self.chat_client = chat_client
        self._original_get_streaming_response = chat_client._inner_get_streaming_response
        
        # Replace the _inner_get_streaming_response method with our wrapper
        chat_client._inner_get_streaming_response = self._wrapped_get_streaming_response
    
    async def _wrapped_get_streaming_response(
        self, 
        *,
        messages: List[ChatMessage],
        chat_options: ChatOptions,
        **kwargs
    ) -> AsyncGenerator[ChatResponseUpdate, None]:
        """Wrapped get_streaming_response method that handles response_format for Bedrock.
        
        Args:
            messages: List of chat messages (includes system messages with tools)
            chat_options: Chat options including response_format
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        log_debug(f"BedrockChatClientWrapper called with {len(messages)} messages")
        log_debug(f"Chat options - response_format: {chat_options.response_format}")
        log_debug(f"Chat options - tools: {len(chat_options.tools) if chat_options.tools else 0}")
        log_debug(f"Chat options - max_tokens: {chat_options.max_tokens}")
        log_debug(f"Chat options - tool_choice: {chat_options.tool_choice}")
        
        # Log tool information at debug level
        if chat_options.tools:
            log_debug(f"Available tools: {[getattr(tool, 'name', str(tool)) for tool in chat_options.tools]}")
        
        # Temporarily patch the _build_converse_request method to log what's being sent
        original_build_request = self.chat_client._build_converse_request
        
        def debug_build_request(*args, **kwargs):
            request = original_build_request(*args, **kwargs)
            log_debug(f"Bedrock request - Model: {request.get('modelId')}")
            log_debug(f"Bedrock request - Messages: {len(request.get('messages', []))}")
            log_debug(f"Bedrock request - Tools: {len(request.get('toolConfig', {}).get('tools', []))}")
            log_debug(f"Bedrock request - Tool choice: {request.get('toolConfig', {}).get('toolChoice', 'None')}")
            return request
        
        # Apply the patch
        self.chat_client._build_converse_request = debug_build_request
        
        # Override max_tokens for Bedrock to avoid the 1024 token default limit
        modified_chat_options = chat_options
        if chat_options.max_tokens is None or chat_options.max_tokens < 32768:
            # Create a new ChatOptions with updated max_tokens
            modified_chat_options = ChatOptions(
                model_id=chat_options.model_id,
                allow_multiple_tool_calls=chat_options.allow_multiple_tool_calls,
                conversation_id=chat_options.conversation_id,
                frequency_penalty=chat_options.frequency_penalty,
                instructions=chat_options.instructions,
                logit_bias=chat_options.logit_bias,
                max_tokens=32768,  # Set to 32K tokens
                metadata=chat_options.metadata,
                presence_penalty=chat_options.presence_penalty,
                response_format=chat_options.response_format,
                seed=chat_options.seed,
                stop=chat_options.stop,
                store=chat_options.store,
                temperature=chat_options.temperature,
                tool_choice=chat_options.tool_choice,
                tools=chat_options.tools,
                top_p=chat_options.top_p,
                user=chat_options.user,
                additional_properties=chat_options.additional_properties,
            )
            log_debug(f"Updated max_tokens to {modified_chat_options.max_tokens}")
        
        if chat_options.response_format is None:
            # No response format specified, use original method
            log_debug("No response_format specified, using original method")
            chunk_count = 0
            async for chunk in self._original_get_streaming_response(messages=messages, chat_options=modified_chat_options, **kwargs):
                chunk_count += 1
                yield chunk
            log_debug(f"Yielded {chunk_count} chunks from original method")
            # Restore original method
            self.chat_client._build_converse_request = original_build_request
            return
        
        log_debug("Adding JSON schema instructions for structured output")
        
        # Create modified messages with JSON schema instructions
        # Use deepcopy to avoid modifying the original messages
        modified_messages = []
        for msg in messages:
            # Create a new message to avoid modifying the original
            new_contents = []
            if hasattr(msg, 'contents') and msg.contents:
                for content in msg.contents:
                    # Check if this is a tool-related content that we shouldn't modify
                    content_type = type(content).__name__
                    if 'Tool' in content_type or 'Function' in content_type:
                        # Don't modify tool-related content
                        new_contents.append(content)
                    elif hasattr(content, 'text'):
                        # Create new TextContent to avoid modifying original
                        new_contents.append(TextContent(text=content.text))
                    else:
                        new_contents.append(content)
            
            # Create new message with copied contents
            new_msg = ChatMessage(
                role=msg.role,
                contents=new_contents,
                author_name=getattr(msg, 'author_name', None),
                message_id=getattr(msg, 'message_id', None),
                additional_properties=getattr(msg, 'additional_properties', {}),
                raw_representation=getattr(msg, 'raw_representation', None)
            )
            modified_messages.append(new_msg)
        response_format = chat_options.response_format
        
        # Get the JSON schema from the response_format model
        schema = response_format.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        # Add JSON schema instructions to the system message or create one
        json_instructions = f"""

CRITICAL: You must format your response as valid JSON that matches this exact schema:

```json
{schema_str}
```

IMPORTANT INSTRUCTIONS:
- Your response must be valid JSON only
- Do NOT include any text before or after the JSON
- Do NOT use <thinking> tags or any XML-style tags
- Do NOT include explanations or reasoning outside the JSON
- Follow the schema exactly
- Use proper JSON formatting with quotes around strings
- Start your response directly with the opening curly brace {{
- If you need to call tools, do so first, then format the final response as JSON
"""
        
        # Find system message or create one - be careful not to modify tool messages
        system_message_found = False
        for msg in modified_messages:
            if msg.role == Role.SYSTEM:
                # Add to existing system message
                for content in msg.contents:
                    if hasattr(content, 'text'):
                        content.text += json_instructions
                        system_message_found = True
                        break
                break
        
        if not system_message_found:
            # Create new system message at the beginning
            system_msg = ChatMessage(
                role=Role.SYSTEM,
                contents=[TextContent(text=json_instructions)]
            )
            modified_messages.insert(0, system_msg)
        
        log_debug(f"Modified messages for JSON schema - total messages: {len(modified_messages)}")
        
        # Log message roles to debug the conversation flow
        for i, msg in enumerate(modified_messages):
            log_debug(f"Message {i}: role={msg.role}, contents_count={len(msg.contents) if hasattr(msg, 'contents') else 0}")
            # Check for tool-related content
            if hasattr(msg, 'contents'):
                for j, content in enumerate(msg.contents):
                    content_type = type(content).__name__
                    if 'Tool' in content_type or 'Function' in content_type:
                        log_debug(f"Message {i} Content {j}: {content_type} - potential tool content")
        
        # Remove response_format from chat_options to avoid conflicts
        modified_chat_options_no_format = ChatOptions(
            model_id=modified_chat_options.model_id,
            allow_multiple_tool_calls=modified_chat_options.allow_multiple_tool_calls,
            conversation_id=modified_chat_options.conversation_id,
            frequency_penalty=modified_chat_options.frequency_penalty,
            instructions=modified_chat_options.instructions,
            logit_bias=modified_chat_options.logit_bias,
            max_tokens=modified_chat_options.max_tokens,
            metadata=modified_chat_options.metadata,
            presence_penalty=modified_chat_options.presence_penalty,
            response_format=None,  # Remove to avoid conflicts
            seed=modified_chat_options.seed,
            stop=modified_chat_options.stop,
            store=modified_chat_options.store,
            temperature=modified_chat_options.temperature,
            tool_choice=modified_chat_options.tool_choice,
            tools=modified_chat_options.tools,
            top_p=modified_chat_options.top_p,
            user=modified_chat_options.user,
            additional_properties=modified_chat_options.additional_properties,
        )
        
        # Collect all response text for parsing
        accumulated_text = ""
        all_chunks = []
        
        log_debug("Starting to collect response chunks...")
        chunk_count = 0
        async for chunk in self._original_get_streaming_response(messages=modified_messages, chat_options=modified_chat_options_no_format, **kwargs):
            chunk_count += 1
            all_chunks.append(chunk)
            
            # Extract text from chunk
            chunk_text = ""
            if hasattr(chunk, 'contents') and chunk.contents:
                for content in chunk.contents:
                    if hasattr(content, 'text') and content.text:
                        chunk_text += content.text
            elif hasattr(chunk, 'text') and chunk.text:
                chunk_text = chunk.text
            
            if chunk_text:
                accumulated_text += chunk_text
        
        log_debug(f"Collected {len(accumulated_text)} characters from {len(all_chunks)} chunks")
        
        # Try to parse the accumulated text as JSON
        try:
            # Clean up the text - remove Nova thinking tags and markdown
            json_text = accumulated_text.strip()
            
            # Remove Nova model thinking tags
            if '<thinking>' in json_text and '</thinking>' in json_text:
                thinking_end = json_text.find('</thinking>')
                if thinking_end != -1:
                    json_text = json_text[thinking_end + 12:].strip()
                    log_debug("Removed <thinking> tags from Nova model response")
            
            # Remove markdown code blocks
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            if json_text.endswith('```'):
                json_text = json_text[:-3]
            json_text = json_text.strip()
            
            # Handle DeepSeek models that might miss the opening brace
            if json_text.startswith('"') and not json_text.startswith('{'):
                json_text = '{' + json_text
                log_debug("Added missing opening brace for DeepSeek model")
            
            # Handle missing closing brace (if response was truncated)
            if json_text.startswith('{') and not json_text.rstrip().endswith('}'):
                open_braces = json_text.count('{')
                close_braces = json_text.count('}')
                if open_braces > close_braces:
                    json_text = json_text.rstrip() + '}'
                    log_debug("Added missing closing brace")
            
            log_debug(f"Attempting to parse JSON response ({len(json_text)} characters)")
            
            # Parse and validate against the schema
            parsed_data = json.loads(json_text)
            validated_response = response_format(**parsed_data)
            
            log_debug("Successfully parsed and validated JSON response")
            
            # Create a single response chunk with the validated data
            response_text = validated_response.model_dump_json(indent=2)
            
            # Create a ChatResponseUpdate that matches the original format
            if all_chunks:
                # Use the last chunk as a template
                last_chunk = all_chunks[-1]
                yield ChatResponseUpdate(
                    contents=[TextContent(text=response_text)],
                    role=last_chunk.role,
                    author_name=getattr(last_chunk, 'author_name', None),
                    response_id=getattr(last_chunk, 'response_id', None),
                    message_id=getattr(last_chunk, 'message_id', None),
                    created_at=getattr(last_chunk, 'created_at', None),
                    additional_properties=getattr(last_chunk, 'additional_properties', {}),
                    raw_representation=getattr(last_chunk, 'raw_representation', None),
                )
            else:
                # Fallback if no chunks were collected
                yield ChatResponseUpdate(
                    contents=[TextContent(text=response_text)],
                    role=Role.ASSISTANT,
                )
            
        except (json.JSONDecodeError, ValidationError) as e:
            log_error(f"Failed to parse JSON response: {e}")
            log_debug(f"Raw response text (first 500 chars): {accumulated_text[:500]}...")
            
            # Fallback: yield original chunks
            log_debug("Falling back to original response chunks")
            for chunk in all_chunks:
                yield chunk
        
        # Always restore the original method
        finally:
            self.chat_client._build_converse_request = original_build_request


def wrap_bedrock_chat_client(chat_client, provider: str) -> None:
    """Wrap a chat client with Bedrock response format support if needed.
    
    Args:
        chat_client: The chat client instance to potentially wrap
        provider: The LLM provider name ("bedrock", "azure", "openai")
    """
    if provider == "bedrock":
        log_debug("Wrapping chat client with Bedrock response format support")
        BedrockChatClientWrapper(chat_client)
    else:
        log_debug(f"Provider {provider} already supports response_format, no chat client wrapping needed")