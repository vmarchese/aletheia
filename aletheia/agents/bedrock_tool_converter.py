"""
Bedrock Converse API message conversion utilities.
"""

import inspect
from collections.abc import Sequence
from typing import Any, Dict, List, Optional

from agent_framework._types import ChatMessage
from agent_framework import ToolProtocol


class ConverseMessageConverter:
    """Converts ChatMessage objects to Bedrock Converse API format."""

    def convert_to_converse_format(
        self, messages: Sequence[ChatMessage]
    ) -> dict[str, Any]:
        """
        Convert ChatMessage objects to Converse API format.

        Args:
            messages: Sequence of ChatMessage objects

        Returns:
            Dictionary with 'system' and 'messages' keys formatted for Converse API
        """
        system_messages = self.extract_system_messages(messages)
        conversation_messages = self.convert_conversation_messages(messages)

        return {"system": system_messages, "messages": conversation_messages}

    def convert_tools_to_converse_format(self, tools: Sequence[ToolProtocol]) -> List[Dict[str, Any]]:
        """
        Convert ToolProtocol objects to Bedrock tool definitions.

        Args:
            tools: Sequence of ToolProtocol objects

        Returns:
            List of tool definitions formatted for Bedrock Converse API
        """
        tool_definitions = []
        
        for tool in tools:
            tool_spec = self._create_tool_spec(tool)
            if tool_spec:
                tool_definitions.append({
                    "toolSpec": tool_spec
                })
        
        return tool_definitions

    def convert_tool_choice_to_converse_format(self, tool_choice: Any) -> Dict[str, Any]:
        """
        Convert tool choice parameter to Converse API format.

        Args:
            tool_choice: Tool choice parameter (can be "auto", "any", "none", or specific tool)

        Returns:
            Dictionary with tool choice configuration for Converse API
        """
        if tool_choice is None or tool_choice == "auto":
            return {"auto": {}}
        elif tool_choice == "any":
            return {"any": {}}
        elif tool_choice == "none":
            return {"none": {}}
        elif isinstance(tool_choice, dict) and "name" in tool_choice:
            # Specific tool selection
            return {
                "tool": {
                    "name": tool_choice["name"]
                }
            }
        else:
            # Default to auto if unrecognized format
            return {"auto": {}}

    def extract_system_messages(
        self, messages: Sequence[ChatMessage]
    ) -> list[dict[str, str]]:
        """
        Extract and format system messages for Converse API.

        Args:
            messages: Sequence of ChatMessage objects

        Returns:
            List of system message dictionaries with 'text' key
        """
        system_messages = []

        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)

            if role == "system":
                # Extract text content from message
                content_text = self._extract_text_content(msg)
                if content_text.strip():  # Only add non-empty system messages
                    system_messages.append({"text": content_text})

        return system_messages

    def convert_conversation_messages(
        self, messages: Sequence[ChatMessage]
    ) -> list[dict[str, Any]]:
        """
        Convert user/assistant messages to Converse API format.

        Args:
            messages: Sequence of ChatMessage objects

        Returns:
            List of conversation message dictionaries with role and content structure
        """
        conversation_messages = []

        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)

            if role in ["user", "assistant"]:
                # Check if message has tool-related content
                content_blocks = self._convert_message_content_blocks(msg)
                if content_blocks:  # Only add non-empty messages
                    conversation_messages.append(
                        {"role": role, "content": content_blocks}
                    )
            elif role == "tool":
                # Tool result messages should be converted to user messages with toolResult blocks
                content_blocks = self._convert_message_content_blocks(msg)
                if content_blocks:  # Only add non-empty messages
                    conversation_messages.append(
                        {"role": "user", "content": content_blocks}
                    )

        return conversation_messages

    def _convert_message_content_blocks(self, message: ChatMessage) -> List[Dict[str, Any]]:
        """
        Convert message content to Converse API content blocks.

        Args:
            message: ChatMessage object

        Returns:
            List of content blocks for Converse API
        """
        content_blocks = []
        
        # Process each content item in the message
        for content in message.contents:
            if hasattr(content, 'text') and content.text.strip():
                # Text content
                content_blocks.append({"text": content.text})
            elif hasattr(content, 'call_id') and hasattr(content, 'name'):
                # FunctionCallContent - convert to toolUse
                arguments = content.arguments
                if isinstance(arguments, str):
                    try:
                        import json
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                elif arguments is None:
                    arguments = {}
                
                content_blocks.append({
                    "toolUse": {
                        "toolUseId": content.call_id,
                        "name": content.name,
                        "input": arguments
                    }
                })
            elif hasattr(content, 'call_id') and hasattr(content, 'result'):
                # FunctionResultContent - convert to toolResult
                content_blocks.append({
                    "toolResult": {
                        "toolUseId": content.call_id,
                        "content": [{"text": str(content.result)}]
                    }
                })
        
        # Fallback: Check for tool-related content in message attributes (legacy support)
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                content_blocks.append({
                    "toolUse": {
                        "toolUseId": tool_call.get("id", f"tool_{hash(str(tool_call))}"),
                        "name": tool_call.get("name", "unknown_tool"),
                        "input": tool_call.get("arguments", {})
                    }
                })
        
        if hasattr(message, 'tool_results') and message.tool_results:
            for tool_result in message.tool_results:
                content_blocks.append({
                    "toolResult": {
                        "toolUseId": tool_result.get("tool_call_id", "unknown_id"),
                        "content": [{"text": str(tool_result.get("content", ""))}]
                    }
                })
        
        return content_blocks

    def create_tool_result_message(self, tool_call_id: str, result: str) -> Dict[str, Any]:
        """
        Create a tool result message for subsequent conversation.

        Args:
            tool_call_id: ID of the tool call this result corresponds to
            result: Result content from tool execution

        Returns:
            Message dictionary formatted for Converse API
        """
        return {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_call_id,
                        "content": [{"text": result}]
                    }
                }
            ]
        }

    def create_tool_result_messages(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create multiple tool result messages for multi-turn conversations.

        Args:
            tool_results: List of tool result dictionaries with 'tool_call_id' and 'content' keys

        Returns:
            List of message dictionaries formatted for Converse API
        """
        messages = []
        for tool_result in tool_results:
            tool_call_id = tool_result.get("tool_call_id", "unknown_id")
            content = str(tool_result.get("content", ""))
            messages.append(self.create_tool_result_message(tool_call_id, content))
        return messages

    def append_tool_results_to_conversation(
        self, 
        conversation_messages: List[Dict[str, Any]], 
        tool_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Append tool results to an existing conversation for multi-turn interactions.

        Args:
            conversation_messages: Existing conversation messages
            tool_results: List of tool result dictionaries

        Returns:
            Updated conversation messages with tool results appended
        """
        updated_messages = conversation_messages.copy()
        tool_result_messages = self.create_tool_result_messages(tool_results)
        updated_messages.extend(tool_result_messages)
        return updated_messages

    def _extract_text_content(self, message: ChatMessage) -> str:
        """
        Extract text content from a ChatMessage.

        Args:
            message: ChatMessage object

        Returns:
            Concatenated text content from all content blocks
        """
        content_text = ""

        for content in message.contents:
            if hasattr(content, "text"):
                content_text += content.text
            elif hasattr(content, "to_dict"):
                content_dict = content.to_dict()
                if "text" in content_dict:
                    content_text += content_dict["text"]

        return content_text

    def _create_tool_spec(self, tool: ToolProtocol) -> Optional[Dict[str, Any]]:
        """
        Create a tool specification for Bedrock Converse API.

        Args:
            tool: ToolProtocol object

        Returns:
            Tool specification dictionary or None if tool cannot be converted
        """
        try:
            # Get tool name - check for name attribute first (ToolProtocol), then __name__ (functions)
            if hasattr(tool, 'name'):
                tool_name = tool.name
            elif hasattr(tool, '__name__'):
                tool_name = tool.__name__
            else:
                # Fallback to string representation, but this should be avoided
                tool_name = str(tool)
            
            # Get tool description
            if hasattr(tool, 'description'):
                description = tool.description
            else:
                # Get function signature and docstring as fallback
                doc = inspect.getdoc(tool) or f"Tool: {tool_name}"
                description = doc
            
            # Create input schema from function signature or parameters
            if hasattr(tool, 'parameters'):
                # Use the parameters attribute if available (ToolProtocol)
                # Check if it's a method or property
                parameters_attr = getattr(tool, 'parameters')
                if callable(parameters_attr):
                    input_schema = parameters_attr()
                else:
                    input_schema = parameters_attr
            else:
                # Fall back to introspecting function signature
                sig = inspect.signature(tool)
                input_schema = self._create_input_schema_from_signature(sig)
            
            tool_spec = {
                "name": tool_name,
                "description": description,
                "inputSchema": {
                    "json": input_schema
                }
            }
            
            return tool_spec
        except Exception as e:
            # If we can't introspect the tool, skip it
            return None

    def _create_input_schema_from_signature(self, sig: inspect.Signature) -> Dict[str, Any]:
        """
        Create JSON schema from function signature.

        Args:
            sig: Function signature

        Returns:
            JSON schema dictionary
        """
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            # Skip 'self' parameter
            if param_name == 'self':
                continue
                
            # Get parameter type and description from annotation
            param_type = "string"  # Default type
            description = f"Parameter: {param_name}"
            
            if param.annotation != inspect.Parameter.empty:
                # Handle Annotated types (common in the codebase)
                if hasattr(param.annotation, '__origin__') and hasattr(param.annotation, '__metadata__'):
                    # This is an Annotated type
                    if param.annotation.__metadata__:
                        description = param.annotation.__metadata__[0]
                    # Get the actual type from the annotation
                    actual_type = param.annotation.__args__[0] if param.annotation.__args__ else str
                else:
                    actual_type = param.annotation
                
                # Map Python types to JSON schema types
                if actual_type == str:
                    param_type = "string"
                elif actual_type == int:
                    param_type = "integer"
                elif actual_type == float:
                    param_type = "number"
                elif actual_type == bool:
                    param_type = "boolean"
                elif actual_type == list:
                    param_type = "array"
                elif actual_type == dict:
                    param_type = "object"
            
            properties[param_name] = {
                "type": param_type,
                "description": description
            }
            
            # Add to required if no default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
            
        return schema
