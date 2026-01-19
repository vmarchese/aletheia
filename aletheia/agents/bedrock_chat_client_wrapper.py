"""
Bedrock chat client wrapper that adds detailed tracing for debugging.

This wrapper provides comprehensive logging and request/response dumping
for Bedrock API calls to aid in troubleshooting and development.
"""
import json
from typing import Any, AsyncIterable, Dict, List, Optional, Type, Union

from agent_framework import ChatMessage, TextContent, Role, FunctionCallContent, FunctionResultContent
from agent_framework._types import ChatOptions as ChatOptionsTypedDict, ChatResponseUpdate
from aletheia.utils.logging import log_debug, log_error


class ChatOptions:
    """Local wrapper class for chat options that provides attribute access to dict values.
    
    The agent framework's ChatOptions is a TypedDict (returns a dict), but we want
    attribute access for cleaner code. This wrapper provides that while maintaining
    compatibility with the dict-based interface.
    """
    
    def __init__(self, options_dict: dict[str, Any]):
        """Initialize from options dict.
        
        Args:
            options_dict: The options dictionary from the framework
        """
        self._dict = options_dict
    
    @property
    def model_id(self) -> Optional[str]:
        return self._dict.get('model_id')
    
    @property
    def max_tokens(self) -> Optional[int]:
        return self._dict.get('max_tokens')
    
    @property
    def temperature(self) -> Optional[float]:
        return self._dict.get('temperature')
    
    @property
    def top_p(self) -> Optional[float]:
        return self._dict.get('top_p')
    
    @property
    def tools(self) -> Optional[Any]:
        return self._dict.get('tools')
    
    @property
    def tool_choice(self) -> Optional[Any]:
        return self._dict.get('tool_choice')
    
    @property
    def response_format(self) -> Optional[Any]:
        return self._dict.get('response_format')
    
    @property
    def allow_multiple_tool_calls(self) -> Optional[bool]:
        return self._dict.get('allow_multiple_tool_calls')
    
    @property
    def conversation_id(self) -> Optional[str]:
        return self._dict.get('conversation_id')
    
    @property
    def frequency_penalty(self) -> Optional[float]:
        return self._dict.get('frequency_penalty')
    
    @property
    def presence_penalty(self) -> Optional[float]:
        return self._dict.get('presence_penalty')
    
    @property
    def instructions(self) -> Optional[str]:
        return self._dict.get('instructions')
    
    @property
    def logit_bias(self) -> Optional[Dict]:
        return self._dict.get('logit_bias')
    
    @property
    def metadata(self) -> Optional[Dict]:
        return self._dict.get('metadata')
    
    @property
    def seed(self) -> Optional[int]:
        return self._dict.get('seed')
    
    @property
    def stop(self) -> Optional[Any]:
        return self._dict.get('stop')
    
    @property
    def store(self) -> Optional[bool]:
        return self._dict.get('store')
    
    @property
    def user(self) -> Optional[str]:
        return self._dict.get('user')
    
    @property
    def additional_properties(self) -> Optional[Dict]:
        return self._dict.get('additional_properties', {})
    
    def to_dict(self) -> dict[str, Any]:
        """Convert back to dict for framework interface.
        
        Returns:
            Dictionary with all non-None values
        """
        return {k: v for k, v in self._dict.items() if v is not None}
    
    def update(self, **kwargs):
        """Update options values.
        
        Args:
            **kwargs: Key-value pairs to update
        """
        self._dict.update(kwargs)


def wrap_bedrock_chat_client(chat_client, provider: str) -> None:
    """Wrap a chat client with Bedrock response format support if needed.
    
    Args:
        chat_client: The chat client instance to potentially wrap
        provider: The LLM provider name ("bedrock", "azure", "openai")
    """
    if provider == "bedrock":
        log_debug("Bedrock provider detected - Adding trace wrapper for debugging")
        BedrockChatClientTraceWrapper(chat_client)
    else:
        log_debug(f"Provider {provider} already supports response_format, no chat client wrapping needed")


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
    
    def _dump_input_messages(self, messages: List[ChatMessage], chat_options: ChatOptions, request_id: str):
        """Dump the input messages as they arrive to the wrapper (before cleaning).
        
        Only dumps when trace logging is enabled (--very-verbose flag).
        
        Args:
            messages: Original input messages
            chat_options: ChatOptions object (converted from dict internally)
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
                "chat_options": {
                    "model_id": chat_options.model_id,
                    "max_tokens": chat_options.max_tokens,
                    "temperature": chat_options.temperature,
                    "tool_choice": str(chat_options.tool_choice) if chat_options.tool_choice else None,
                    "tools_count": len(chat_options.tools) if chat_options.tools else 0,
                    "response_format": str(chat_options.response_format) if chat_options.response_format else None,
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
    
    def _strip_markdown_code_blocks(self, text: str) -> str:
        """Strip markdown code blocks from text content.
        
        Bedrock often wraps JSON responses in markdown code blocks like:
        ```json
        {...}
        ```
        
        This method strips those markers to return pure JSON/text.
        
        Args:
            text: Text that may contain markdown code blocks
            
        Returns:
            Text with markdown code blocks stripped
        """
        if not text:
            return text
        
        text = text.strip()
        
        # Check if text starts with markdown code block
        if text.startswith('```json'):
            text = text[7:].strip()  # Remove ```json
        elif text.startswith('```'):
            text = text[3:].strip()  # Remove ```
        
        # Check if text ends with markdown code block
        if text.endswith('```'):
            text = text[:-3].strip()  # Remove trailing ```
        
        return text
    
    async def _traced_get_streaming_response(
        self, 
        *,
        messages: List[ChatMessage],
        options: dict[str, Any],
        **kwargs
    ) -> AsyncIterable[ChatResponseUpdate]:
        """Traced get_streaming_response method that logs all details for debugging.
        
        Args:
            messages: List of chat messages (includes system messages with tools)
            options: Chat options dict (framework interface requirement)
            **kwargs: Additional arguments
            
        Yields:
            Streaming response chunks
        """
        from datetime import datetime
        
        # Wrap the options dict in our local ChatOptions class for attribute access
        chat_options = ChatOptions(options)
        
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
        self._log_trace(f"Response format: {chat_options.response_format}")
        self._log_trace(f"Tools available: {len(chat_options.tools) if chat_options.tools else 0}")
        self._log_trace(f"Max tokens: {chat_options.max_tokens}")
        self._log_trace(f"Tool choice: {chat_options.tool_choice}")
        self._log_trace(f"Kwargs tool_choice: {kwargs.get('tool_choice', 'NOT SET')}")
        
        # Dump input messages (before cleaning)
        self._dump_input_messages(messages, chat_options, request_id)
        
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
        if chat_options.max_tokens is None or chat_options.max_tokens < 8192:
            self._log_trace(f"Increasing max_tokens from {chat_options.max_tokens} to 8192 to avoid truncation")
            chat_options.update(max_tokens=8192)
        
        # Cache tools when they're provided
        if chat_options.tools and len(chat_options.tools) > 0:
            self._cached_tools = chat_options.tools
            self._log_trace(f"Caching {len(chat_options.tools)} tools for future use")
        
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
        # This persists across calls even when chat_options is recreated
        kwargs_tool_choice = kwargs.get("tool_choice")
        if kwargs_tool_choice == "none" and self._cached_tools:
            self._log_trace(f"⚠️  DETECTED: kwargs has tool_choice='none' from previous call")
            self._log_trace(f"   This will cause empty responses even with tools available")
            self._log_trace(f"   Removing tool_choice from kwargs to allow fresh evaluation")
            # Remove it from kwargs so it doesn't override our logic
            kwargs.pop("tool_choice", None)
        
        if chat_options.tools is None or len(chat_options.tools) == 0:
            if self._cached_tools:
                # Determine reason for restoration and appropriate tool_choice
                if has_tool_content_in_history:
                    # MUST restore tools - Bedrock API will fail without them
                    reason = "required by Bedrock API (tool content in history)"
                    new_tool_choice = "auto"
                elif chat_options.tool_choice == "none":
                    # Agent framework set tool_choice="none" to indicate analysis mode
                    # Convert to "auto" and restore tools - let the model decide
                    # The model should be smart enough to analyze existing data vs fetching new data
                    reason = "converting 'none' to 'auto' (let model decide)"
                    new_tool_choice = "auto"
                else:
                    # Default case - enable continued tool use
                    reason = "enabling continued tool use"
                    new_tool_choice = "auto"
                
                self._log_trace(f"No tools provided but have cached tools - restoring {len(self._cached_tools)} tools")
                self._log_trace(f"Reason: {reason}")
                self._log_trace(f"Updating tool_choice from '{chat_options.tool_choice}' to '{new_tool_choice}'")
                
                # Update options with restored tools and new tool_choice
                chat_options.update(
                    tool_choice=new_tool_choice,
                    tools=self._cached_tools
                )
            elif has_tool_content_in_history:
                # No cached tools but history has tool content - this will fail
                self._log_trace(f"WARNING: No tools provided and no cached tools available, but conversation has tool content")
                self._log_trace(f"This will cause Bedrock API error")
            else:
                # No tools, no cached tools, no tool content - safe to proceed without tools
                if chat_options.tool_choice is not None:
                    self._log_trace(f"No tools and no tool content in history, setting tool_choice to None")
                    chat_options.update(tool_choice=None)
        
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
        if chat_options.tools:
            self._log_trace(f"--- Available Tools ---")
            for i, tool in enumerate(chat_options.tools):
                tool_name = getattr(tool, 'name', f'tool_{i}')
                self._log_trace(f"Tool {i}: {tool_name}")
        
        # Temporarily patch the _prepare_options method to log the actual request
        # In the new framework, _prepare_options builds the request dict that's passed to bedrock
        original_prepare_options = self.chat_client._prepare_options
        
        def traced_prepare_options(*args, **kwargs):
            request = original_prepare_options(*args, **kwargs)
            
            # FIX: Handle tool_choice="none" which Bedrock doesn't support
            # Bedrock only accepts: {"auto": {}}, {"any": {}}, or {"tool": {"name": "..."}}
            # 
            # When tool_choice is "none", the framework wants to hint that the model
            # should analyze existing data rather than fetch new data.
            # 
            # The correct fix: Convert "none" to "auto" and keep tools available.
            # This allows the model to decide whether to use tools or just respond.
            # With tool_choice="auto", the model should be smart enough to:
            # - Analyze existing conversation data when appropriate
            # - Use tools to fetch new data when needed
            tool_config = request.get('toolConfig', {})
            if tool_config:
                tool_choice = tool_config.get('toolChoice', {})
                
                # Check if toolChoice is {"none": {}} which is invalid for Bedrock
                if isinstance(tool_choice, dict) and "none" in tool_choice:
                    self._log_trace(f"⚠️  FIXING INVALID TOOL_CHOICE: Detected toolChoice={tool_choice}")
                    self._log_trace(f"   Bedrock doesn't support 'none'")
                    self._log_trace(f"   Converting to 'auto' - let model decide whether to use tools")
                    
                    # Convert "none" to "auto" - let the model decide
                    # The model should be smart enough to analyze vs fetch based on context
                    tool_config['toolChoice'] = {"auto": {}}
                    self._log_trace(f"   ✅ toolChoice changed to 'auto' - model can choose")
            
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
            
            # Log tool configuration (after fix)
            tool_config = request.get('toolConfig', {})
            if tool_config:
                tools = tool_config.get('tools', [])
                self._log_trace(f"Tool config: {len(tools)} tools")
                tool_choice = tool_config.get('toolChoice', 'auto')
                self._log_trace(f"Tool choice: {tool_choice}")
            else:
                self._log_trace(f"Tool config: None (tools disabled for this request)")
            
            return request
        
        # Apply the patch
        self.chat_client._prepare_options = traced_prepare_options
        
        # Track response data for dumping
        response_chunks = []
        response_error = None
        
        try:
            # Call the original method and trace the response
            self._log_trace(f"--- CALLING ORIGINAL METHOD ---")
            
            # Convert ChatOptions wrapper back to dict for the framework interface
            options_dict = chat_options.to_dict()
            
            chunk_count = 0
            async for chunk in self._original_get_streaming_response(messages=messages, options=options_dict, **kwargs):
                chunk_count += 1
                response_chunks.append(chunk)
                
                # Strip markdown code blocks from TextContent before yielding
                # This fixes the issue where Bedrock wraps JSON in ```json ... ```
                if hasattr(chunk, 'contents') and chunk.contents:
                    modified_contents = []
                    has_text_content = False
                    
                    for content in chunk.contents:
                        if isinstance(content, TextContent) and hasattr(content, 'text'):
                            # Strip markdown code blocks from text
                            cleaned_text = self._strip_markdown_code_blocks(content.text)
                            
                            # Log if we stripped markdown (only for first few chunks)
                            if chunk_count <= 5 and cleaned_text != content.text:
                                self._log_trace(f"Stripped markdown code blocks from chunk {chunk_count}")
                                self._log_trace(f"Original length: {len(content.text)}, Cleaned length: {len(cleaned_text)}")
                            
                            # Create new TextContent with cleaned text
                            modified_content = TextContent(text=cleaned_text)
                            modified_contents.append(modified_content)
                            has_text_content = True
                        else:
                            # Keep other content types as-is (FunctionCallContent, UsageContent, etc.)
                            modified_contents.append(content)
                    
                    # Only create a new chunk if we actually modified text content
                    if has_text_content:
                        # Create new chunk with modified contents
                        # We need to preserve all chunk attributes
                        modified_chunk = ChatResponseUpdate(
                            role=chunk.role if hasattr(chunk, 'role') else None,
                            contents=modified_contents,
                            message_id=chunk.message_id if hasattr(chunk, 'message_id') else None,
                            response_id=chunk.response_id if hasattr(chunk, 'response_id') else None
                        )
                        chunk = modified_chunk
                
                if chunk_count <= 5:  # Log first few chunks
                    self._log_trace(f"Response chunk {chunk_count}: {type(chunk).__name__}")
                    if hasattr(chunk, 'contents') and chunk.contents:
                        for content in chunk.contents:
                            if hasattr(content, 'text') and content.text:
                                text_preview = content.text[:50] + "..." if len(content.text) > 50 else content.text
                                self._log_trace(f"Chunk text (after cleaning): {text_preview}")
                
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
            self.chat_client._prepare_options = original_prepare_options
