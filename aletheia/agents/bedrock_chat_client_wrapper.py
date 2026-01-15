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

from agent_framework import ChatMessage, TextContent, Role, FunctionCallContent, FunctionResultContent
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
        options: ChatOptions,
        **kwargs
    ) -> AsyncGenerator[ChatResponseUpdate, None]:
        """Wrapped get_streaming_response method that handles response_format for Bedrock.
        
        Args:
            messages: List of chat messages (includes system messages with tools)
            options: Chat options including response_format
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        log_debug(f"BedrockChatClientWrapper called with {len(messages)} messages")
        log_debug(f"Chat options - response_format: {options.response_format}")
        log_debug(f"Chat options - tools: {len(options.tools) if options.tools else 0}")
        log_debug(f"Chat options - max_tokens: {options.max_tokens}")
        log_debug(f"Chat options - tool_choice: {options.tool_choice}")
        
        # Log detailed message information
        for i, msg in enumerate(messages):
            log_debug(f"Input message {i}: role={msg.role}")
            if hasattr(msg, 'contents') and msg.contents:
                for j, content in enumerate(msg.contents):
                    content_type = type(content).__name__
                    if 'Tool' in content_type or hasattr(content, 'tool_use_id'):
                        log_debug(f"Input message {i} content {j}: {content_type} (TOOL CONTENT)")
                        if hasattr(content, 'tool_use_id'):
                            log_debug(f"  tool_use_id: {getattr(content, 'tool_use_id', 'N/A')}")
                        if hasattr(content, 'name'):
                            log_debug(f"  name: {getattr(content, 'name', 'N/A')}")
                    else:
                        log_debug(f"Input message {i} content {j}: {content_type}")
        
        # Log tool information at debug level
        if options.tools:
            log_debug(f"Available tools: {[getattr(tool, 'name', str(tool)) for tool in options.tools]}")
        else:
            log_debug("No tools available in options")
        
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
        modified_options = options
        if options.max_tokens is None or options.max_tokens < 32768:
            # Create a new ChatOptions with updated max_tokens
            modified_options = ChatOptions(
                model_id=options.model_id,
                allow_multiple_tool_calls=options.allow_multiple_tool_calls,
                conversation_id=options.conversation_id,
                frequency_penalty=options.frequency_penalty,
                instructions=options.instructions,
                logit_bias=options.logit_bias,
                max_tokens=32768,  # Set to 32K tokens
                metadata=options.metadata,
                presence_penalty=options.presence_penalty,
                response_format=options.response_format,
                seed=options.seed,
                stop=options.stop,
                store=options.store,
                temperature=options.temperature,
                tool_choice=options.tool_choice,
                tools=options.tools,
                top_p=options.top_p,
                user=options.user,
                additional_properties=options.additional_properties,
            )
            log_debug(f"Updated max_tokens to {modified_options.max_tokens}")
        
        # Check if this is a tool call scenario - if so, let the agent framework handle it naturally
        has_tools = options.tools and len(options.tools) > 0
        has_tool_content = any(
            hasattr(msg, 'contents') and msg.contents and any(
                'Tool' in type(content).__name__ or 
                hasattr(content, 'tool_use_id') or
                'tool_use' in str(type(content)).lower() or
                'tool_result' in str(type(content)).lower()
                for content in msg.contents
            )
            for msg in messages
        )
        
        # Always use original method when tools are available, regardless of tool content in history
        # This prevents interference with the agent framework's tool management
        if has_tools:
            log_debug("Tools available - using original method without message modification")
            # For tool calls, use the original method without our message modifications
            # to avoid interfering with the agent framework's tool call management
            chunk_count = 0
            async for chunk in self._original_get_streaming_response(messages=messages, options=modified_options, **kwargs):
                chunk_count += 1
                yield chunk
            log_debug(f"Yielded {chunk_count} chunks from original method (tools available)")
            # Restore original method
            self.chat_client._build_converse_request = original_build_request
            return
        
        if options.response_format is None:
            # No response format specified, use original method
            log_debug("No response_format specified, using original method")
            chunk_count = 0
            async for chunk in self._original_get_streaming_response(messages=messages, options=modified_options, **kwargs):
                chunk_count += 1
                yield chunk
            log_debug(f"Yielded {chunk_count} chunks from original method")
            # Restore original method
            self.chat_client._build_converse_request = original_build_request
            return
        
        log_debug("Adding JSON schema instructions for structured output")
        
        # Only modify messages for structured output when there are no tool calls involved
        modified_messages = []
        for i, msg in enumerate(messages):
            log_debug(f"Processing message {i}: role={msg.role}")
            
            # Create a new message to avoid modifying the original
            new_contents = []
            
            if hasattr(msg, 'contents') and msg.contents:
                for j, content in enumerate(msg.contents):
                    if hasattr(content, 'text'):
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
            log_debug(f"Added message {i} to modified_messages (role={msg.role}, contents={len(new_contents)})")
        
        response_format = options.response_format
        
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
        
        # Remove response_format from options to avoid conflicts
        modified_options_no_format = ChatOptions(
            model_id=modified_options.model_id,
            allow_multiple_tool_calls=modified_options.allow_multiple_tool_calls,
            conversation_id=modified_options.conversation_id,
            frequency_penalty=modified_options.frequency_penalty,
            instructions=modified_options.instructions,
            logit_bias=modified_options.logit_bias,
            max_tokens=modified_options.max_tokens,
            metadata=modified_options.metadata,
            presence_penalty=modified_options.presence_penalty,
            response_format=None,  # Remove to avoid conflicts
            seed=modified_options.seed,
            stop=modified_options.stop,
            store=modified_options.store,
            temperature=modified_options.temperature,
            tool_choice=modified_options.tool_choice,
            tools=modified_options.tools,
            top_p=modified_options.top_p,
            user=modified_options.user,
            additional_properties=modified_options.additional_properties,
        )
        
        # Collect all response text for parsing
        accumulated_text = ""
        all_chunks = []
        
        log_debug("Starting to collect response chunks...")
        chunk_count = 0
        async for chunk in self._original_get_streaming_response(messages=modified_messages, options=modified_options_no_format, **kwargs):
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
            # Clean up the text - remove Nova thinking tags, YAML frontmatter, and markdown
            json_text = accumulated_text.strip()
            
            # Remove Nova model thinking tags
            if '<thinking>' in json_text and '</thinking>' in json_text:
                thinking_end = json_text.find('</thinking>')
                if thinking_end != -1:
                    json_text = json_text[thinking_end + 12:].strip()
                    log_debug("Removed <thinking> tags from Nova model response")
            
            # Remove YAML frontmatter (appears before JSON in some responses)
            # Format: ---\nagent: ...\ntimestamp: ...\n---\n
            if json_text.startswith('---'):
                # Find the closing --- of the frontmatter
                frontmatter_end = json_text.find('---', 3)
                if frontmatter_end != -1:
                    json_text = json_text[frontmatter_end + 3:].strip()
                    log_debug("Removed YAML frontmatter from response")
            
            # Remove markdown code blocks
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            elif json_text.startswith('```'):
                json_text = json_text[3:]
            
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
    # DISABLED: Wrapping causes deepcopy issues with agent_framework
    # The wrapper modifies chat_client._inner_get_streaming_response which gets
    # stored in agent.default_options and causes pickle errors when deepcopied.
    # 
    # For now, Bedrock structured outputs are not supported.
    # TODO: Find a way to wrap without modifying the chat_client instance
    log_debug(f"Bedrock wrapping disabled for provider {provider} to avoid deepcopy issues")


class BedrockChatClientTraceWrapper:
    """Wrapper that adds detailed tracing for Bedrock chat client calls."""
    
    def __init__(self, chat_client):
        """Initialize the wrapper with a chat client instance.
        
        Args:
            chat_client: The Bedrock chat client instance to wrap
        """
        self.chat_client = chat_client
        self._original_get_streaming_response = chat_client._inner_get_streaming_response
        self._cached_tools = None  # Cache tools for reuse when needed
        self._call_counter = 0  # Counter for API calls to number the dump files
        
        # Replace the _inner_get_streaming_response method with our wrapper
        chat_client._inner_get_streaming_response = self._traced_get_streaming_response
    
    def _log_trace(self, message: str, data: any = None):
        """Log trace information to both debug log and trace file."""
        import json
        import os
        from pathlib import Path
        
        log_debug(f"BEDROCK_TRACE: {message}")
        
        # Also write to trace file if very verbose mode is enabled
        try:
            # Check if we're in very verbose mode by looking for trace log file
            trace_file = None
            for possible_path in [
                Path.cwd() / "aletheia_trace.log",
                Path.home() / ".aletheia" / "aletheia_trace.log",
            ]:
                if possible_path.exists():
                    trace_file = possible_path
                    break
            
            if trace_file:
                with open(trace_file, "a", encoding="utf-8") as f:
                    f.write(f"BEDROCK_TRACE: {message}\n")
                    if data is not None:
                        try:
                            if hasattr(data, '__dict__'):
                                # For objects with attributes
                                f.write(f"BEDROCK_TRACE_DATA: {json.dumps(data.__dict__, indent=2, default=str)}\n")
                            else:
                                # For other data types
                                f.write(f"BEDROCK_TRACE_DATA: {json.dumps(data, indent=2, default=str)}\n")
                        except Exception as e:
                            f.write(f"BEDROCK_TRACE_DATA: {str(data)} (JSON serialization failed: {e})\n")
                    f.write("---\n")
        except Exception as e:
            log_debug(f"Failed to write trace data: {e}")
    
    def _get_session_dir(self):
        """Find the current session directory.
        
        Returns:
            Path to session directory or None if not found
        """
        from pathlib import Path
        
        # Find the session directory by looking for aletheia_trace.log
        session_dir = None
        for possible_path in [
            Path.cwd(),
            Path.home() / ".aletheia",
        ]:
            trace_file = possible_path / "aletheia_trace.log"
            if trace_file.exists():
                # Get the parent directory (should be the session directory)
                session_dir = trace_file.parent
                break
        
        if not session_dir:
            # Fallback: try to find session directory in ~/.aletheia/sessions/
            aletheia_dir = Path.home() / ".aletheia"
            if aletheia_dir.exists():
                # Find the most recent session directory
                sessions_dir = aletheia_dir / "sessions"
                if sessions_dir.exists():
                    session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
                    if session_dirs:
                        # Get the most recently modified session
                        session_dir = max(session_dirs, key=lambda d: d.stat().st_mtime)
        
        return session_dir
    
    def _dump_input_messages(self, messages: List[ChatMessage], options: ChatOptions, request_id: str):
        """Dump the input messages as they arrive to the wrapper (before cleaning).
        
        Only dumps when trace logging is enabled (--very-verbose flag).
        
        Args:
            messages: Original input messages
            options: Original chat options
            request_id: Unique request identifier for correlation
        """
        import json
        from pathlib import Path
        from aletheia.utils.logging import is_trace_enabled
        
        # Only dump if trace logging is enabled (--very-verbose)
        if not is_trace_enabled():
            return
        
        try:
            session_dir = self._get_session_dir()
            if not session_dir:
                return
            
            # Create bedrock_requests directory if it doesn't exist
            requests_dir = session_dir / "bedrock_requests"
            requests_dir.mkdir(exist_ok=True)
            
            # Create input data structure
            input_data = {
                "request_id": request_id,
                "stage": "input",
                "description": "Messages as received by wrapper (before cleaning)",
                "message_count": len(messages),
                "options": {
                    "model_id": options.model_id,
                    "max_tokens": options.max_tokens,
                    "temperature": options.temperature,
                    "tool_choice": str(options.tool_choice) if options.tool_choice else None,
                    "tools_count": len(options.tools) if options.tools else 0,
                    "response_format": str(options.response_format) if options.response_format else None,
                },
                "messages": []
            }
            
            # Convert messages to serializable format
            for i, msg in enumerate(messages):
                msg_data = {
                    "index": i,
                    "role": str(msg.role),
                    "contents": []
                }
                
                if hasattr(msg, 'contents') and msg.contents:
                    for j, content in enumerate(msg.contents):
                        content_info = {
                            "index": j,
                            "type": type(content).__name__
                        }
                        
                        # Add content details based on type
                        if hasattr(content, 'text'):
                            content_info["text"] = content.text[:200] + "..." if len(content.text) > 200 else content.text
                        if hasattr(content, 'name'):
                            content_info["name"] = content.name
                        if hasattr(content, 'call_id'):
                            content_info["call_id"] = content.call_id
                        if hasattr(content, 'tool_use_id'):
                            content_info["tool_use_id"] = content.tool_use_id
                        
                        msg_data["contents"].append(content_info)
                
                input_data["messages"].append(msg_data)
            
            # Write to file
            filename = f"input_{request_id}.json"
            filepath = requests_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(input_data, f, indent=2, default=str)
            
            self._log_trace(f"📥 INPUT: {filepath.name}")
            
        except Exception as e:
            log_debug(f"Failed to dump input messages: {e}")
    
    def _dump_bedrock_request(self, request: dict, request_id: str):
        """Dump the complete Bedrock API request to a separate JSON file for detailed analysis.
        
        Only dumps when trace logging is enabled (--very-verbose flag).
        
        Args:
            request: The Bedrock Converse API request dictionary
            request_id: Unique request identifier for correlation
        """
        import json
        from pathlib import Path
        from aletheia.utils.logging import is_trace_enabled
        
        # Only dump if trace logging is enabled (--very-verbose)
        if not is_trace_enabled():
            return
        
        try:
            session_dir = self._get_session_dir()
            if not session_dir:
                return
            
            # Create bedrock_requests directory if it doesn't exist
            requests_dir = session_dir / "bedrock_requests"
            requests_dir.mkdir(exist_ok=True)
            
            # Add metadata to request
            request_with_metadata = {
                "request_id": request_id,
                "stage": "request",
                "description": "Final Bedrock API request (after cleaning and conversion)",
                "bedrock_request": self._sanitize_for_json(request)
            }
            
            # Write to file
            filename = f"request_{request_id}.json"
            filepath = requests_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(request_with_metadata, f, indent=2, default=str)
            
            self._log_trace(f"📤 REQUEST: {filepath.name}")
            
        except Exception as e:
            log_debug(f"Failed to dump Bedrock request: {e}")
    
    def _dump_bedrock_response(self, response_data: dict, request_id: str, error: Exception = None):
        """Dump the Bedrock API response (or error) to a separate JSON file.
        
        Only dumps when trace logging is enabled (--very-verbose flag).
        
        Args:
            response_data: Response data (chunks, metadata, etc.)
            request_id: Unique request identifier for correlation
            error: Exception if an error occurred
        """
        import json
        from pathlib import Path
        from datetime import datetime
        from aletheia.utils.logging import is_trace_enabled
        
        # Only dump if trace logging is enabled (--very-verbose)
        if not is_trace_enabled():
            return
        
        try:
            session_dir = self._get_session_dir()
            if not session_dir:
                return
            
            # Create bedrock_requests directory if it doesn't exist
            requests_dir = session_dir / "bedrock_requests"
            requests_dir.mkdir(exist_ok=True)
            
            # Create response data structure
            response_file_data = {
                "request_id": request_id,
                "stage": "response",
                "description": "Bedrock API response or error",
                "timestamp": datetime.now().isoformat(),
                "success": error is None,
            }
            
            if error:
                response_file_data["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                    "details": getattr(error, 'response', {}) if hasattr(error, 'response') else {}
                }
            else:
                response_file_data["response"] = self._sanitize_for_json(response_data)
            
            # Write to file
            filename = f"response_{request_id}.json"
            filepath = requests_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(response_file_data, f, indent=2, default=str)
            
            status = "❌ ERROR" if error else "✅ SUCCESS"
            self._log_trace(f"📨 RESPONSE: {filepath.name} - {status}")
            
        except Exception as e:
            log_debug(f"Failed to dump Bedrock response: {e}")
    
    def _sanitize_for_json(self, obj):
        """Recursively sanitize an object for JSON serialization.
        
        Args:
            obj: Object to sanitize
            
        Returns:
            JSON-serializable version of the object
        """
        import json
        
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._sanitize_for_json(obj.__dict__)
        else:
            return str(obj)
    
    def _clean_messages_for_bedrock(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Clean messages to ensure Bedrock API compliance.
        
        Bedrock has strict rules:
        1. User messages cannot contain tool uses (FunctionCallContent with name and tool_use_id)
        2. Assistant messages cannot contain tool results (FunctionResultContent)
        3. Bedrock doesn't support "tool" role - these get converted to "user" role
        4. Each toolResult must have a corresponding toolUse in the previous assistant turn
        5. Tool/User messages can ONLY contain FunctionResultContent (and optionally text for user messages)
        6. Tool/User messages CANNOT contain FunctionCallContent
        
        This method:
        - Filters out invalid content from messages
        - Converts tool role messages to user role (to match Bedrock's conversion)
        - Ensures user messages only have tool results and text, never tool uses
        - Removes orphaned toolResults (results without corresponding toolUse)
        - **SPLITS mixed-content tool messages** into separate user and assistant messages
        
        Args:
            messages: Original list of chat messages
            
        Returns:
            Cleaned list of chat messages
        """
        from agent_framework import Role, TextContent, ChatMessage
        from agent_framework._types import FunctionCallContent, FunctionResultContent
        
        cleaned_messages = []
        
        # Track which tool calls we're filtering out so we can also remove their results
        filtered_call_ids = set()
        
        # First pass: identify internal tool calls (toolUse with result in same message)
        # These are tool calls that were executed within the same turn
        for i, msg in enumerate(messages):
            if not hasattr(msg, 'contents') or not msg.contents:
                continue
            
            # Check if this is a tool message
            if msg.role == Role.TOOL or str(msg.role).lower() == 'tool':
                # Build a map of call_ids in this message
                call_ids_with_use = set()
                call_ids_with_result = set()
                
                for content in msg.contents:
                    call_id = getattr(content, 'call_id', getattr(content, 'tool_use_id', None))
                    if not call_id:
                        continue
                    
                    is_tool_use = (
                        isinstance(content, FunctionCallContent) or
                        (hasattr(content, 'name') and hasattr(content, 'call_id'))
                    )
                    is_tool_result = (
                        isinstance(content, FunctionResultContent) or
                        (hasattr(content, 'call_id') and not hasattr(content, 'name'))
                    )
                    
                    if is_tool_use:
                        call_ids_with_use.add(call_id)
                    if is_tool_result:
                        call_ids_with_result.add(call_id)
                
                # Find call_ids that have BOTH use and result in the same message
                # These are internal tool calls that should be filtered
                internal_calls = call_ids_with_use & call_ids_with_result
                if internal_calls:
                    filtered_call_ids.update(internal_calls)
                    self._log_trace(f"Found {len(internal_calls)} internal tool calls in message {i}: {internal_calls}")
        
        # Second pass: clean and convert messages
        for i, msg in enumerate(messages):
            # Skip empty messages
            if not hasattr(msg, 'contents') or not msg.contents:
                cleaned_messages.append(msg)
                continue
            
            # Determine the effective role for Bedrock
            # Bedrock converts "tool" role to "user" role, so we do it here to have full control
            effective_role = msg.role
            is_tool_message = msg.role == Role.TOOL or str(msg.role).lower() == 'tool'
            
            if is_tool_message:
                effective_role = Role.USER
                self._log_trace(f"Converting message {i} from role=tool to role=user (Bedrock requirement)")
            
            # **NEW: Check if this is a mixed-content tool message that needs conversion**
            # Tool messages can have FunctionResultContent, FunctionCallContent, and TextContent
            # But Bedrock requires:
            # - User messages (converted from tool): Only TextContent or FunctionResultContent
            # - User messages CANNOT have FunctionCallContent
            #
            # ONLY when a tool message has BOTH FunctionCallContent AND FunctionResultContent,
            # we convert the FunctionCallContent to text so it can be passed as context.
            # This happens when a sub-agent returns its conversation history.
            
            if is_tool_message:
                # Categorize contents
                tool_results = []
                tool_calls = []
                text_contents = []
                other_contents = []
                
                for content in msg.contents:
                    is_tool_use = (
                        isinstance(content, FunctionCallContent) or
                        (hasattr(content, 'name') and hasattr(content, 'call_id')) or
                        (hasattr(content, 'name') and hasattr(content, 'tool_use_id'))
                    )
                    is_tool_result = (
                        isinstance(content, FunctionResultContent) or
                        (hasattr(content, 'call_id') and not hasattr(content, 'name')) or
                        (hasattr(content, 'tool_use_id') and not hasattr(content, 'name'))
                    )
                    is_text = isinstance(content, TextContent) or hasattr(content, 'text')
                    
                    if is_tool_use:
                        tool_calls.append(content)
                    elif is_tool_result:
                        tool_results.append(content)
                    elif is_text:
                        text_contents.append(content)
                    else:
                        other_contents.append(content)
                
                # ONLY convert tool calls to text if we have BOTH tool calls AND tool results
                # This indicates a mixed-content message from sub-agent history
                if tool_calls and tool_results:
                    self._log_trace(f"Message {i} is a MIXED-CONTENT tool message with {len(tool_calls)} tool calls and {len(tool_results)} tool results - CONVERTING tool calls to text")
                    
                    # Build a set of call_ids that have tool calls in this message
                    tool_call_ids = set()
                    for tool_call in tool_calls:
                        call_id = getattr(tool_call, 'call_id', getattr(tool_call, 'tool_use_id', None))
                        if call_id:
                            tool_call_ids.add(call_id)
                    
                    # Separate tool results into two groups:
                    # 1. Results that have corresponding tool calls in this message (paired)
                    # 2. Results that don't have tool calls in this message (orphaned - from previous messages)
                    # IMPORTANT: We create NEW FunctionResultContent objects to avoid mutating input data
                    paired_results = []
                    orphaned_results = []
                    
                    for tool_result in tool_results:
                        call_id = getattr(tool_result, 'call_id', getattr(tool_result, 'tool_use_id', None))
                        
                        # Create a NEW FunctionResultContent object (deep copy to avoid mutation)
                        new_result = FunctionResultContent(
                            call_id=call_id,
                            result=getattr(tool_result, 'result', None),
                            exception=getattr(tool_result, 'exception', None)
                        )
                        
                        if call_id and call_id in tool_call_ids:
                            paired_results.append(new_result)
                        else:
                            orphaned_results.append(new_result)
                    
                    self._log_trace(f"Found {len(paired_results)} paired results and {len(orphaned_results)} orphaned results")
                    
                    # Convert tool calls to text representation
                    for tool_call in tool_calls:
                        call_id = getattr(tool_call, 'call_id', getattr(tool_call, 'tool_use_id', 'unknown'))
                        name = getattr(tool_call, 'name', 'unknown')
                        
                        # Create a text representation of the tool call
                        tool_call_text = f"[Tool Call: {name} (id: {call_id})]"
                        
                        # Add input if available
                        if hasattr(tool_call, 'input') and tool_call.input:
                            import json
                            try:
                                input_str = json.dumps(tool_call.input, indent=2)
                                tool_call_text += f"\nInput: {input_str}"
                            except:
                                tool_call_text += f"\nInput: {tool_call.input}"
                        
                        text_contents.append(TextContent(text=tool_call_text))
                        self._log_trace(f"Converted tool call {name} to text representation")
                    
                    # Convert PAIRED tool results to text as well (since their tool calls were converted)
                    for tool_result in paired_results:
                        call_id = getattr(tool_result, 'call_id', getattr(tool_result, 'tool_use_id', 'unknown'))
                        
                        # Create a text representation of the tool result
                        tool_result_text = f"[Tool Result for: {call_id}]"
                        
                        # Add status if available
                        if hasattr(tool_result, 'status'):
                            tool_result_text += f"\nStatus: {tool_result.status}"
                        
                        # Add content if available
                        if hasattr(tool_result, 'content') and tool_result.content:
                            import json
                            try:
                                # Handle different content formats
                                if isinstance(tool_result.content, list):
                                    for item in tool_result.content:
                                        if hasattr(item, 'text'):
                                            tool_result_text += f"\nOutput: {item.text}"
                                        elif hasattr(item, 'json'):
                                            output_str = json.dumps(item.json, indent=2)
                                            tool_result_text += f"\nOutput (JSON): {output_str}"
                                        else:
                                            tool_result_text += f"\nOutput: {item}"
                                else:
                                    tool_result_text += f"\nOutput: {tool_result.content}"
                            except:
                                tool_result_text += f"\nOutput: {tool_result.content}"
                        
                        text_contents.append(TextContent(text=tool_result_text))
                        self._log_trace(f"Converted paired tool result ({call_id}) to text representation")
                    
                    # Now create a single user message with:
                    # - Orphaned tool results (keep as FunctionResultContent - they have tool uses in previous messages)
                    # - Text contents (including converted tool calls and paired results)
                    user_contents = orphaned_results + text_contents + other_contents
                    if user_contents:
                        user_msg = ChatMessage(
                            role=Role.USER,
                            contents=user_contents,
                            author_name=getattr(msg, 'author_name', None),
                            message_id=getattr(msg, 'message_id', None),
                            additional_properties=getattr(msg, 'additional_properties', {}),
                            raw_representation=getattr(msg, 'raw_representation', None)
                        )
                        cleaned_messages.append(user_msg)
                        self._log_trace(f"Created user message with {len(orphaned_results)} orphaned tool results, {len(text_contents)} text contents (including {len(tool_calls)} converted tool calls and {len(paired_results)} converted paired results)")
                    
                    # Skip the normal processing for this message
                    continue
                # If tool message has ONLY tool calls (no results) or ONLY results (no calls),
                # let normal filtering handle it
            
            # Normal processing for non-mixed-content messages
            # Filter contents based on effective role
            new_contents = []
            has_tool_use = False
            has_tool_result = False
            has_text = False
            
            for content in msg.contents:
                content_type = type(content).__name__
                
                # Identify tool use (FunctionCallContent with name and call_id)
                is_tool_use = (
                    isinstance(content, FunctionCallContent) or
                    (hasattr(content, 'name') and hasattr(content, 'call_id')) or
                    (hasattr(content, 'name') and hasattr(content, 'tool_use_id'))  # Bedrock format
                )
                
                # Identify tool result (FunctionResultContent)
                is_tool_result = (
                    isinstance(content, FunctionResultContent) or
                    (hasattr(content, 'call_id') and not hasattr(content, 'name')) or
                    (hasattr(content, 'tool_use_id') and not hasattr(content, 'name'))  # Bedrock format
                )
                
                # Identify text content
                is_text = isinstance(content, TextContent) or hasattr(content, 'text')
                
                # Get call_id for tracking
                call_id = None
                if hasattr(content, 'call_id'):
                    call_id = content.call_id
                elif hasattr(content, 'tool_use_id'):
                    call_id = content.tool_use_id
                
                # Apply filtering rules based on EFFECTIVE role (after tool->user conversion)
                if effective_role == Role.ASSISTANT:
                    # Assistant messages can have tool uses and text, but NOT tool results
                    if is_tool_result:
                        self._log_trace(f"Filtering out tool result from assistant message {i}")
                        if call_id:
                            filtered_call_ids.add(call_id)
                        continue
                    
                    # Create NEW content object to avoid mutating input
                    if is_tool_use:
                        new_content = FunctionCallContent(
                            name=getattr(content, 'name', 'unknown'),
                            call_id=call_id,
                            input=getattr(content, 'input', {})
                        )
                        new_contents.append(new_content)
                        has_tool_use = True
                    elif is_text:
                        new_content = TextContent(text=getattr(content, 'text', ''))
                        new_contents.append(new_content)
                        has_text = True
                    else:
                        # For other content types, append as-is (rare case)
                        new_contents.append(content)
                        
                elif effective_role == Role.USER:
                    # User messages can have tool results and text, but NOT tool uses
                    # This is CRITICAL because tool role messages become user messages in Bedrock
                    if is_tool_use:
                        # Check if this is an internal tool call (has result in same message)
                        if call_id and call_id in filtered_call_ids:
                            self._log_trace(f"Filtering out internal toolUse from {msg.role} message {i} (call_id: {call_id})")
                        else:
                            self._log_trace(f"Filtering out tool use from {msg.role} message {i} (will be user in Bedrock)")
                            # Track this call_id so we can also remove its result if it appears later
                            if call_id:
                                filtered_call_ids.add(call_id)
                        continue
                    
                    # Filter out tool results that are part of internal tool calls
                    if is_tool_result and call_id and call_id in filtered_call_ids:
                        self._log_trace(f"Filtering out internal toolResult from {msg.role} message {i} (call_id: {call_id})")
                        continue
                    
                    # Create NEW content object to avoid mutating input
                    if is_tool_result:
                        new_content = FunctionResultContent(
                            call_id=call_id,
                            result=getattr(content, 'result', None),
                            exception=getattr(content, 'exception', None)
                        )
                        new_contents.append(new_content)
                        has_tool_result = True
                    elif is_text:
                        new_content = TextContent(text=getattr(content, 'text', ''))
                        new_contents.append(new_content)
                        has_text = True
                    else:
                        # For other content types, append as-is (rare case)
                        new_contents.append(content)
                        
                else:
                    # For other roles (like SYSTEM), create new TextContent objects
                    if is_text:
                        new_content = TextContent(text=getattr(content, 'text', ''))
                        new_contents.append(new_content)
                    else:
                        # For non-text content in system messages, append as-is
                        new_contents.append(content)
            
            # Only include the message if it has content after filtering
            if new_contents:
                # Create a new message with filtered contents and effective role
                cleaned_msg = ChatMessage(
                    role=effective_role,  # Use effective role (tool->user conversion)
                    contents=new_contents,
                    author_name=getattr(msg, 'author_name', None),
                    message_id=getattr(msg, 'message_id', None),
                    additional_properties=getattr(msg, 'additional_properties', {}),
                    raw_representation=getattr(msg, 'raw_representation', None)
                )
                cleaned_messages.append(cleaned_msg)
                
                self._log_trace(f"Message {i} ({msg.role}->{effective_role}): kept {len(new_contents)}/{len(msg.contents)} contents")
            else:
                self._log_trace(f"Message {i} ({msg.role}): filtered out completely (no valid content)")
        
        # Final validation pass: Ensure every FunctionResultContent has a corresponding FunctionCallContent
        # in a previous assistant message
        self._log_trace("=== FINAL VALIDATION: Checking tool use/result pairing ===")
        
        # Track all tool uses (call_ids) from assistant messages
        available_tool_uses = set()
        validated_messages = []
        
        for i, msg in enumerate(cleaned_messages):
            if not hasattr(msg, 'contents') or not msg.contents:
                validated_messages.append(msg)
                continue
            
            # If this is an assistant message, collect all tool use call_ids
            # AND create new content objects to avoid mutating input
            if msg.role == Role.ASSISTANT:
                new_contents = []
                for content in msg.contents:
                    is_tool_use = (
                        isinstance(content, FunctionCallContent) or
                        (hasattr(content, 'name') and hasattr(content, 'call_id')) or
                        (hasattr(content, 'name') and hasattr(content, 'tool_use_id'))
                    )
                    if is_tool_use:
                        call_id = getattr(content, 'call_id', getattr(content, 'tool_use_id', None))
                        if call_id:
                            available_tool_uses.add(call_id)
                            self._log_trace(f"Message {i}: Found tool use {call_id}")
                        
                        # Create NEW FunctionCallContent
                        new_content = FunctionCallContent(
                            name=getattr(content, 'name', 'unknown'),
                            call_id=call_id,
                            input=getattr(content, 'input', {})
                        )
                        new_contents.append(new_content)
                    elif isinstance(content, TextContent) or hasattr(content, 'text'):
                        # Create NEW TextContent
                        new_content = TextContent(text=getattr(content, 'text', ''))
                        new_contents.append(new_content)
                    else:
                        # For other content types, append as-is (rare case)
                        new_contents.append(content)
                
                # Create new assistant message with new content objects
                new_msg = ChatMessage(
                    role=msg.role,
                    contents=new_contents,
                    author_name=getattr(msg, 'author_name', None),
                    message_id=getattr(msg, 'message_id', None),
                    additional_properties=getattr(msg, 'additional_properties', {}),
                    raw_representation=getattr(msg, 'raw_representation', None)
                )
                validated_messages.append(new_msg)
            
            # If this is a user message, validate all tool results have corresponding tool uses
            elif msg.role == Role.USER:
                valid_contents = []
                orphaned_results = []
                
                for content in msg.contents:
                    is_tool_result = (
                        isinstance(content, FunctionResultContent) or
                        (hasattr(content, 'call_id') and not hasattr(content, 'name')) or
                        (hasattr(content, 'tool_use_id') and not hasattr(content, 'name'))
                    )
                    
                    if is_tool_result:
                        call_id = getattr(content, 'call_id', getattr(content, 'tool_use_id', None))
                        if call_id and call_id in available_tool_uses:
                            # Valid - has corresponding tool use
                            # Create NEW FunctionResultContent to avoid mutating input
                            new_content = FunctionResultContent(
                                call_id=call_id,
                                result=getattr(content, 'result', None),
                                exception=getattr(content, 'exception', None)
                            )
                            valid_contents.append(new_content)
                            self._log_trace(f"Message {i}: Tool result {call_id} is valid (has corresponding tool use)")
                        else:
                            # Orphaned - no corresponding tool use found
                            orphaned_results.append(call_id)
                            self._log_trace(f"Message {i}: Tool result {call_id} is ORPHANED (no corresponding tool use) - FILTERING OUT")
                    else:
                        # Not a tool result - create new TextContent if it's text
                        if isinstance(content, TextContent) or hasattr(content, 'text'):
                            new_content = TextContent(text=getattr(content, 'text', ''))
                            valid_contents.append(new_content)
                        else:
                            # For other content types, append as-is (rare case)
                            valid_contents.append(content)
                
                # Only add the message if it has valid contents after filtering orphaned results
                if valid_contents:
                    validated_msg = ChatMessage(
                        role=msg.role,
                        contents=valid_contents,
                        author_name=getattr(msg, 'author_name', None),
                        message_id=getattr(msg, 'message_id', None),
                        additional_properties=getattr(msg, 'additional_properties', {}),
                        raw_representation=getattr(msg, 'raw_representation', None)
                    )
                    validated_messages.append(validated_msg)
                    if orphaned_results:
                        self._log_trace(f"Message {i}: Filtered out {len(orphaned_results)} orphaned tool results")
                else:
                    self._log_trace(f"Message {i}: Completely filtered out (only had orphaned tool results)")
            
            else:
                # Other roles (SYSTEM, etc.) - keep as-is
                validated_messages.append(msg)
        
        self._log_trace(f"Validation complete: {len(cleaned_messages)} -> {len(validated_messages)} messages")
        
        return validated_messages
    
    def _has_tool_content(self, messages: List[ChatMessage]) -> bool:
        """Check if any message in the conversation contains tool-related content.
        
        Args:
            messages: List of chat messages
            
        Returns:
            True if any message contains tool use or tool result content
        """
        from agent_framework._types import FunctionCallContent, FunctionResultContent
        
        for msg in messages:
            if not hasattr(msg, 'contents') or not msg.contents:
                continue
                
            for content in msg.contents:
                # Check for tool use (FunctionCallContent)
                is_tool_use = (
                    isinstance(content, FunctionCallContent) or
                    (hasattr(content, 'name') and (hasattr(content, 'call_id') or hasattr(content, 'tool_use_id')))
                )
                
                # Check for tool result (FunctionResultContent)
                is_tool_result = (
                    isinstance(content, FunctionResultContent) or
                    ((hasattr(content, 'call_id') or hasattr(content, 'tool_use_id')) and not hasattr(content, 'name'))
                )
                
                if is_tool_use or is_tool_result:
                    return True
        
        return False
    
    async def _traced_get_streaming_response(
        self, 
        *,
        messages: List[ChatMessage],
        options: ChatOptions,
        **kwargs
    ) -> AsyncGenerator[ChatResponseUpdate, None]:
        """Traced get_streaming_response method that logs all details for debugging.
        
        Args:
            messages: List of chat messages (includes system messages with tools)
            options: Chat options including response_format
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        from datetime import datetime
        
        # CRITICAL: Create a copy of kwargs to avoid modifying framework variables
        # The framework passes kwargs that may be reused across calls
        kwargs = dict(kwargs)
        
        # Generate unique request ID for correlation across files
        # Format: call_number_timestamp
        self._call_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
        request_id = f"{self._call_counter:04d}_{timestamp}"
        
        self._log_trace(f"=== BEDROCK CALL START (ID: {request_id}) ===")
        self._log_trace(f"Number of messages (before cleaning): {len(messages)}")
        self._log_trace(f"Response format: {options.response_format}")
        self._log_trace(f"Tools available: {len(options.tools) if options.tools else 0}")
        self._log_trace(f"Max tokens: {options.max_tokens}")
        self._log_trace(f"Tool choice: {options.tool_choice}")
        self._log_trace(f"Kwargs tool_choice: {kwargs.get('tool_choice', 'NOT SET')}")
        
        # Dump input messages (before cleaning)
        self._dump_input_messages(messages, options, request_id)
        
        # Log message summary BEFORE cleaning
        for i, msg in enumerate(messages):
            if hasattr(msg, 'contents') and msg.contents:
                content_types = []
                for content in msg.contents:
                    ctype = type(content).__name__
                    is_func_call = 'FunctionCall' in ctype or (hasattr(content, 'name') and hasattr(content, 'call_id'))
                    is_func_result = 'FunctionResult' in ctype or (hasattr(content, 'call_id') and not hasattr(content, 'name'))
                    
                    if is_func_call:
                        content_types.append('FUNC_CALL')
                    elif is_func_result:
                        content_types.append('FUNC_RESULT')
                    elif hasattr(content, 'text'):
                        content_types.append('TEXT')
                    else:
                        content_types.append(ctype)
                
                self._log_trace(f"Message {i} BEFORE: role={msg.role}, contents=[{', '.join(content_types)}]")
        
        # Clean up messages to ensure Bedrock API compliance
        # Rule: User messages cannot contain tool uses (FunctionCallContent)
        # Rule: Assistant messages cannot contain tool results (FunctionResultContent)
        cleaned_messages = self._clean_messages_for_bedrock(messages)
        self._log_trace(f"Number of messages (after cleaning): {len(cleaned_messages)}")
        
        # Use cleaned messages instead of original
        messages = cleaned_messages
        
        # Override max_tokens for Bedrock to avoid truncation
        # Bedrock defaults to 1024 tokens which is too small for structured responses
        # IMPORTANT: Create a new ChatOptions object instead of modifying the original
        # to avoid affecting framework logic
        if options.max_tokens is None or options.max_tokens < 8192:
            self._log_trace(f"Increasing max_tokens from {options.max_tokens} to 8192 to avoid truncation")
            options = ChatOptions(
                model_id=options.model_id,
                allow_multiple_tool_calls=options.allow_multiple_tool_calls,
                conversation_id=options.conversation_id,
                frequency_penalty=options.frequency_penalty,
                instructions=options.instructions,
                logit_bias=options.logit_bias,
                max_tokens=8192,  # Set to 8K tokens minimum
                metadata=options.metadata,
                presence_penalty=options.presence_penalty,
                response_format=options.response_format,
                seed=options.seed,
                stop=options.stop,
                store=options.store,
                temperature=options.temperature,
                tool_choice=options.tool_choice,
                tools=options.tools,
                top_p=options.top_p,
                user=options.user,
                additional_properties=options.additional_properties,
            )
        else:
            # Even if max_tokens is OK, create a copy to avoid modifying the original
            options = ChatOptions(
                model_id=options.model_id,
                allow_multiple_tool_calls=options.allow_multiple_tool_calls,
                conversation_id=options.conversation_id,
                frequency_penalty=options.frequency_penalty,
                instructions=options.instructions,
                logit_bias=options.logit_bias,
                max_tokens=options.max_tokens,
                metadata=options.metadata,
                presence_penalty=options.presence_penalty,
                response_format=options.response_format,
                seed=options.seed,
                stop=options.stop,
                store=options.store,
                temperature=options.temperature,
                tool_choice=options.tool_choice,
                tools=options.tools,
                top_p=options.top_p,
                user=options.user,
                additional_properties=options.additional_properties,
            )
        
        # Cache tools when they're provided
        if options.tools and len(options.tools) > 0:
            self._cached_tools = options.tools
            self._log_trace(f"Caching {len(options.tools)} tools for future use")
        
        # Check if conversation history contains any tool-related content
        has_tool_content_in_history = self._has_tool_content(messages)
        
        # AGGRESSIVE TOOL RESTORATION:
        # The agent framework removes tools after first use, but Bedrock requires tools
        # to be present if there's ANY tool content in the conversation history.
        # We restore cached tools in two scenarios:
        # 1. No tools provided but history has tool content (Bedrock API requirement)
        # 2. No tools provided and we have cached tools (enable continued tool use)
        #
        # CRITICAL FIX: We also update tool_choice from "none" to "auto" when restoring tools.
        # Without this, the model receives tools but is told not to use them (tool_choice="none"),
        # which causes empty responses in multi-turn conversations.
        
        # ADDITIONAL FIX: Check kwargs for tool_choice="none" that persists from previous calls
        # The framework modifies kwargs in place, setting tool_choice="none" after tool execution
        # This persists across calls even when options is recreated
        kwargs_tool_choice = kwargs.get("tool_choice")
        if kwargs_tool_choice == "none" and self._cached_tools:
            self._log_trace(f"⚠️  DETECTED: kwargs has tool_choice='none' from previous call")
            self._log_trace(f"   This will cause empty responses even with tools available")
            self._log_trace(f"   Removing tool_choice from kwargs to allow fresh evaluation")
            # Remove it from kwargs so it doesn't override our logic
            kwargs.pop("tool_choice", None)
        
        if options.tools is None or len(options.tools) == 0:
            if self._cached_tools:
                # Determine reason for restoration and appropriate tool_choice
                if has_tool_content_in_history:
                    # MUST restore tools - Bedrock API will fail without them
                    reason = "required by Bedrock API (tool content in history)"
                    new_tool_choice = "auto"
                elif options.tool_choice == "none":
                    # Agent framework explicitly disabled tools, but we need them for continued conversation
                    reason = "enabling continued conversation (was 'none')"
                    new_tool_choice = "auto"
                else:
                    # Default case - enable continued tool use
                    reason = "enabling continued tool use"
                    new_tool_choice = "auto"
                
                self._log_trace(f"No tools provided but have cached tools - restoring {len(self._cached_tools)} tools")
                self._log_trace(f"Reason: {reason}")
                self._log_trace(f"Updating tool_choice from '{options.tool_choice}' to '{new_tool_choice}'")
                
                options = ChatOptions(
                    model_id=options.model_id,
                    allow_multiple_tool_calls=options.allow_multiple_tool_calls,
                    conversation_id=options.conversation_id,
                    frequency_penalty=options.frequency_penalty,
                    instructions=options.instructions,
                    logit_bias=options.logit_bias,
                    max_tokens=options.max_tokens,
                    metadata=options.metadata,
                    presence_penalty=options.presence_penalty,
                    response_format=options.response_format,
                    seed=options.seed,
                    stop=options.stop,
                    store=options.store,
                    temperature=options.temperature,
                    tool_choice=new_tool_choice,  # FIX: Update from "none" to "auto" to enable responses
                    tools=self._cached_tools,  # Reuse cached tools
                    top_p=options.top_p,
                    user=options.user,
                    additional_properties=options.additional_properties,
                )
            elif has_tool_content_in_history:
                # No cached tools but history has tool content - this will fail
                self._log_trace(f"WARNING: No tools provided and no cached tools available, but conversation has tool content")
                self._log_trace(f"This will cause Bedrock API error")
            else:
                # No tools, no cached tools, no tool content - safe to proceed without tools
                if options.tool_choice is not None:
                    self._log_trace(f"No tools and no tool content in history, setting tool_choice to None")
                    options = ChatOptions(
                        model_id=options.model_id,
                        allow_multiple_tool_calls=options.allow_multiple_tool_calls,
                        conversation_id=options.conversation_id,
                        frequency_penalty=options.frequency_penalty,
                        instructions=options.instructions,
                        logit_bias=options.logit_bias,
                        max_tokens=options.max_tokens,
                        metadata=options.metadata,
                        presence_penalty=options.presence_penalty,
                        response_format=options.response_format,
                        seed=options.seed,
                        stop=options.stop,
                        store=options.store,
                        temperature=options.temperature,
                        tool_choice=None,  # Set to None when no tools and no tool content
                        tools=options.tools,
                        top_p=options.top_p,
                        user=options.user,
                        additional_properties=options.additional_properties,
                    )
        
        # Log detailed message information AFTER cleaning
        for i, msg in enumerate(messages):
            self._log_trace(f"--- Message {i} (AFTER CLEANING) ---")
            self._log_trace(f"Role: {msg.role}")
            self._log_trace(f"Contents count: {len(msg.contents) if hasattr(msg, 'contents') and msg.contents else 0}")
            
            if hasattr(msg, 'contents') and msg.contents:
                for j, content in enumerate(msg.contents):
                    content_type = type(content).__name__
                    self._log_trace(f"Content {j}: {content_type}")
                    
                    # Check if this is tool-related content
                    is_function_call = 'FunctionCall' in content_type or (hasattr(content, 'name') and hasattr(content, 'call_id'))
                    is_function_result = 'FunctionResult' in content_type or (hasattr(content, 'call_id') and not hasattr(content, 'name'))
                    
                    if is_function_call:
                        self._log_trace(f"⚠️  FUNCTION CALL DETECTED in {msg.role} message")
                        if hasattr(content, 'name'):
                            self._log_trace(f"   Function name: {content.name}")
                        if hasattr(content, 'call_id'):
                            self._log_trace(f"   Call ID: {content.call_id}")
                    elif is_function_result:
                        self._log_trace(f"✓ FUNCTION RESULT in {msg.role} message")
                        if hasattr(content, 'call_id'):
                            self._log_trace(f"   Call ID: {content.call_id}")
                    elif hasattr(content, 'text'):
                        text_preview = content.text[:100] + "..." if len(content.text) > 100 else content.text
                        self._log_trace(f"Text: {text_preview}")
                    else:
                        self._log_trace(f"Other: {str(content)[:100]}")
        
        # Log tools information
        if options.tools:
            self._log_trace(f"--- Available Tools ---")
            for i, tool in enumerate(options.tools):
                tool_name = getattr(tool, 'name', f'tool_{i}')
                self._log_trace(f"Tool {i}: {tool_name}")
        
        # Temporarily patch the _build_converse_request method to log the actual request
        original_build_request = self.chat_client._build_converse_request
        
        def traced_build_request(*args, **kwargs):
            request = original_build_request(*args, **kwargs)
            
            # Dump the complete request to a separate JSON file
            self._dump_bedrock_request(request, request_id)
            
            self._log_trace(f"--- BEDROCK REQUEST #{request_id} ---")
            self._log_trace(f"Model ID: {request.get('modelId')}")
            self._log_trace(f"Messages in request: {len(request.get('messages', []))}")
            
            # Log each message in the request
            for i, req_msg in enumerate(request.get('messages', [])):
                role = req_msg.get('role')
                self._log_trace(f"Request message {i}: role={role}")
                contents = req_msg.get('content', [])
                
                # Check for invalid content in user messages
                has_tool_use = False
                has_tool_result = False
                
                for j, content in enumerate(contents):
                    if isinstance(content, dict):
                        content_type = content.get('type', 'unknown')
                        self._log_trace(f"Request content {j}: type={content_type}")
                        
                        if content_type == 'toolUse':
                            has_tool_use = True
                            self._log_trace(f"⚠️  TOOL_USE: id={content.get('id')}, name={content.get('name')}")
                        elif content_type == 'toolResult':
                            has_tool_result = True
                            self._log_trace(f"TOOL_RESULT: toolUseId={content.get('toolUseId')}")
                        elif content_type == 'text':
                            text_preview = content.get('text', '')[:100]
                            self._log_trace(f"TEXT: {text_preview}")
                        else:
                            self._log_trace(f"UNKNOWN TYPE: {content_type}, keys: {list(content.keys())}")
                
                # Validate message content based on role
                if role == 'user' and has_tool_use:
                    self._log_trace(f"❌ VALIDATION ERROR: User message {i} contains toolUse - THIS WILL FAIL!")
                if role == 'assistant' and has_tool_result:
                    self._log_trace(f"❌ VALIDATION ERROR: Assistant message {i} contains toolResult - THIS WILL FAIL!")
            
            # Log tool configuration
            tool_config = request.get('toolConfig', {})
            if tool_config:
                tools = tool_config.get('tools', [])
                self._log_trace(f"Tool config: {len(tools)} tools")
                tool_choice = tool_config.get('toolChoice', 'auto')
                self._log_trace(f"Tool choice: {tool_choice}")
            
            return request
        
        # Apply the patch
        self.chat_client._build_converse_request = traced_build_request
        
        # Track response data for dumping
        response_chunks = []
        response_error = None
        
        try:
            # Call the original method and trace the response
            self._log_trace(f"--- CALLING ORIGINAL METHOD ---")
            chunk_count = 0
            async for chunk in self._original_get_streaming_response(messages=messages, options=options, **kwargs):
                chunk_count += 1
                response_chunks.append(chunk)
                if chunk_count <= 5:  # Log first few chunks
                    self._log_trace(f"Response chunk {chunk_count}: {type(chunk).__name__}")
                    if hasattr(chunk, 'contents') and chunk.contents:
                        for content in chunk.contents:
                            if hasattr(content, 'text') and content.text:
                                text_preview = content.text[:50] + "..." if len(content.text) > 50 else content.text
                                self._log_trace(f"Chunk text: {text_preview}")
                yield chunk
            
            self._log_trace(f"Total chunks yielded: {chunk_count}")
            self._log_trace(f"=== BEDROCK CALL END (ID: {request_id}) ===")
            
            # Dump successful response with detailed chunk information
            detailed_chunks = []
            for i, chunk in enumerate(response_chunks):
                chunk_info = {
                    "index": i,
                    "type": type(chunk).__name__,
                    "role": str(chunk.role) if hasattr(chunk, 'role') else None,
                    "contents": []
                }
                
                if hasattr(chunk, 'contents') and chunk.contents:
                    for j, content in enumerate(chunk.contents):
                        content_info = {
                            "index": j,
                            "type": type(content).__name__
                        }
                        
                        # Capture text content
                        if hasattr(content, 'text'):
                            content_info["text"] = content.text
                        
                        # Capture tool use information
                        if hasattr(content, 'name'):
                            content_info["name"] = content.name
                        if hasattr(content, 'call_id'):
                            content_info["call_id"] = content.call_id
                        if hasattr(content, 'tool_use_id'):
                            content_info["tool_use_id"] = content.tool_use_id
                        if hasattr(content, 'input'):
                            content_info["input"] = str(content.input)[:500]  # Limit size
                        
                        # Capture tool result information
                        if hasattr(content, 'output'):
                            content_info["output"] = str(content.output)[:500]  # Limit size
                        if hasattr(content, 'status'):
                            content_info["status"] = content.status
                        
                        chunk_info["contents"].append(content_info)
                
                # Capture other chunk attributes
                if hasattr(chunk, 'message_id'):
                    chunk_info["message_id"] = chunk.message_id
                if hasattr(chunk, 'response_id'):
                    chunk_info["response_id"] = chunk.response_id
                
                detailed_chunks.append(chunk_info)
            
            response_data = {
                "chunk_count": chunk_count,
                "chunks": detailed_chunks
            }
            self._dump_bedrock_response(response_data, request_id)
            
        except Exception as e:
            response_error = e
            self._log_trace(f"ERROR in Bedrock call: {str(e)}")
            self._log_trace(f"Error type: {type(e).__name__}")
            
            # Extract detailed error information
            error_details = {
                "exception_type": type(e).__name__,
                "exception_message": str(e)
            }
            
            # For boto3 ClientError, extract detailed error information
            if hasattr(e, 'response'):
                error_details["boto3_response"] = {
                    "Error": e.response.get('Error', {}),
                    "ResponseMetadata": e.response.get('ResponseMetadata', {}),
                    "HTTPStatusCode": e.response.get('ResponseMetadata', {}).get('HTTPStatusCode'),
                }
                
                # Log the specific error code and message
                error_code = e.response.get('Error', {}).get('Code')
                error_message = e.response.get('Error', {}).get('Message')
                self._log_trace(f"Boto3 Error Code: {error_code}")
                self._log_trace(f"Boto3 Error Message: {error_message}")
            
            # Dump error response with detailed information
            self._dump_bedrock_response(error_details, request_id, error=e)
            
            raise
        finally:
            # Always restore the original method
            self.chat_client._build_converse_request = original_build_request