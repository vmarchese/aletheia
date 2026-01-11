"""
Bedrock client wrapper that adds response_format support.

This wrapper adds structured output support to Bedrock clients by:
1. Intercepting run_stream calls with response_format parameter
2. Adding JSON schema instructions to the system prompt
3. Parsing and validating the response against the expected schema
"""
import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from agent_framework import ChatMessage, TextContent, Role
from aletheia.utils.logging import log_debug, log_error


class BedrockResponseWrapper:
    """Wrapper for response objects that matches the expected interface."""
    
    def __init__(self, text: str, contents: Optional[List] = None):
        """Initialize response wrapper.
        
        Args:
            text: The response text
            contents: Optional contents list (for usage tracking)
        """
        self.text = text
        self.contents = contents or []


class BedrockResponseFormatWrapper:
    """Wrapper that adds response_format support to Bedrock ChatAgent instances."""
    
    def __init__(self, chat_agent):
        """Initialize the wrapper with a ChatAgent instance.
        
        Args:
            chat_agent: The ChatAgent instance to wrap
        """
        self.chat_agent = chat_agent
        self._original_run_stream = chat_agent.run_stream
        
        # Replace the run_stream method with our wrapper
        chat_agent.run_stream = self._wrapped_run_stream
    
    async def _wrapped_run_stream(
        self, 
        messages: List[ChatMessage], 
        thread=None, 
        response_format: Optional[Type[BaseModel]] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """Wrapped run_stream method that handles response_format for Bedrock.
        
        Args:
            messages: List of chat messages
            thread: Optional thread context
            response_format: Optional Pydantic model for structured output
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        # Override max_tokens for Bedrock to avoid the 1024 token default limit
        # Claude models support up to 64K output tokens
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = 32768  # Set to 32K tokens (half of max to be safe)
            log_debug(f"BedrockWrapper: Setting max_tokens to {kwargs['max_tokens']}")
        
        if response_format is None:
            # No response format specified, use original method with updated max_tokens
            log_debug(f"BedrockWrapper: No response_format specified, using original method")
            async for chunk in self._original_run_stream(messages, thread=thread, **kwargs):
                yield chunk
            return
        
        log_debug("BedrockWrapper: Adding JSON schema instructions for AgentResponse")
        
        # Create modified messages with JSON schema instructions
        modified_messages = messages.copy()
        
        # Get the JSON schema from the response_format model
        schema = response_format.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        # Add JSON schema instructions to the last user message
        json_instructions = f"""

Please format your response as valid JSON that matches this exact schema:

```json
{schema_str}
```

Important:
- Your response must be valid JSON only
- Do not include any text before or after the JSON
- Follow the schema exactly
- Use proper JSON formatting with quotes around strings
"""
        
        if modified_messages and modified_messages[-1].role == Role.USER:
            # Find the text content in the last message
            for content in modified_messages[-1].contents:
                if hasattr(content, 'text'):
                    content.text += json_instructions
                    break
        
        # Collect all response text for parsing
        accumulated_text = ""
        all_chunks = []
        
        log_debug("BedrockWrapper: Starting to collect response chunks...")
        async for chunk in self._original_run_stream(modified_messages, thread=thread, **kwargs):
            all_chunks.append(chunk)
            if hasattr(chunk, 'text') and chunk.text:
                accumulated_text += chunk.text
        
        log_debug(f"BedrockWrapper: Collected {len(accumulated_text)} characters from {len(all_chunks)} chunks")
        
        # Try to parse the accumulated text as JSON
        try:
            # Clean up the text - remove any markdown code blocks
            json_text = accumulated_text.strip()
            if json_text.startswith('```json'):
                json_text = json_text[7:]  # Remove ```json
            if json_text.endswith('```'):
                json_text = json_text[:-3]  # Remove ```
            json_text = json_text.strip()
            
            # Parse and validate against the schema
            parsed_data = json.loads(json_text)
            validated_response = response_format(**parsed_data)
            
            log_debug("BedrockWrapper: Successfully parsed and validated JSON response")
            
            # Create a single response chunk with the validated data
            response_text = validated_response.model_dump_json(indent=2)
            wrapped_chunk = BedrockResponseWrapper(
                text=response_text,
                contents=getattr(all_chunks[-1], 'contents', []) if all_chunks else []
            )
            yield wrapped_chunk
            
        except (json.JSONDecodeError, ValidationError) as e:
            log_error(f"BedrockWrapper: Failed to parse JSON response: {e}")
            log_debug(f"BedrockWrapper: Raw response text: {accumulated_text[:500]}...")
            
            # Fallback: yield original chunks
            log_debug("BedrockWrapper: Falling back to original response chunks")
            for chunk in all_chunks:
                if hasattr(chunk, 'text'):
                    wrapped_chunk = BedrockResponseWrapper(
                        text=chunk.text,
                        contents=getattr(chunk, 'contents', [])
                    )
                    yield wrapped_chunk
                else:
                    yield chunk


def wrap_bedrock_agent(chat_agent, provider: str) -> None:
    """Wrap a ChatAgent with Bedrock response format support if needed.
    
    Args:
        chat_agent: The ChatAgent instance to potentially wrap
        provider: The LLM provider name ("bedrock", "azure", "openai")
    """
    if provider == "bedrock":
        log_debug("Wrapping ChatAgent with Bedrock response format support")
        BedrockResponseFormatWrapper(chat_agent)
    else:
        log_debug(f"Provider {provider} already supports response_format, no wrapping needed")