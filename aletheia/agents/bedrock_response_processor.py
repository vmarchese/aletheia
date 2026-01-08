"""
Bedrock Converse API response processing utilities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_framework._types import (
    ChatMessage,
    ChatResponse,
    ChatResponseUpdate,
    FinishReason,
    FunctionCallContent,
    Role,
    TextContent,
    UsageDetails,
)


class ConverseResponseProcessor:
    """Processes Bedrock Converse API responses and converts them to ChatResponse format."""

    def create_chat_response(
        self, converse_response: Dict[str, Any], model_id: str
    ) -> ChatResponse:
        """
        Convert Converse API response to ChatResponse format.

        Args:
            converse_response: Raw response from Bedrock Converse API
            model_id: The model ID used for the request

        Returns:
            ChatResponse object with converted data
        """
        # Extract output message
        output_message = self._extract_output_message(converse_response)
        
        # Convert content blocks to TextContent objects
        message_contents = self._convert_content_blocks(output_message)
        
        # Create ChatMessage
        chat_message = ChatMessage(
            role=Role.ASSISTANT,
            contents=message_contents
        )
        
        # Map usage information
        usage_details = self._map_usage_information(converse_response)
        
        # Map completion reason
        finish_reason = self._map_completion_reason(converse_response)
        
        # Generate response metadata
        response_id, created_at = self._generate_response_metadata(converse_response)
        
        return ChatResponse(
            response_id=response_id,
            created_at=created_at,
            usage_details=usage_details,
            messages=[chat_message],
            model_id=model_id,
            finish_reason=finish_reason
        )

    def process_streaming_event(
        self, event: Dict[str, Any]
    ) -> Optional[ChatResponseUpdate]:
        """
        Process individual streaming events from Converse API.

        Args:
            event: Individual event from the streaming response

        Returns:
            ChatResponseUpdate object if the event contains content, None otherwise
        """
        # Handle contentBlockDelta events
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"]["delta"]
            if "text" in delta:
                return ChatResponseUpdate(
                    role=Role.ASSISTANT,
                    contents=[TextContent(text=delta["text"])],
                    model_id="",  # Will be set by caller
                    response_id="",  # Will be set by caller
                    message_id="",  # Will be set by caller
                    created_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    finish_reason=None
                )
            elif "toolUse" in delta:
                # Handle tool use delta events (partial tool calls)
                # For streaming, we don't yield partial tool calls as they're incomplete
                return None
        
        # Handle contentBlockStart events
        elif "contentBlockStart" in event:
            start_block = event["contentBlockStart"]["start"]
            if "toolUse" in start_block:
                # Handle tool use start events - don't yield content for tool starts
                return None
            # Text content block start doesn't need to yield content
            return None
        
        # Handle messageStop events
        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason", "end_turn")
            finish_reason = self._map_stop_reason_to_finish_reason(stop_reason)
            
            return ChatResponseUpdate(
                role=Role.ASSISTANT,
                contents=[],
                model_id="",  # Will be set by caller
                response_id="",  # Will be set by caller
                message_id="",  # Will be set by caller
                created_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                finish_reason=finish_reason
            )
        
        # Handle metadata events (no content to yield, but could be used for final stats)
        elif "metadata" in event:
            return None
        
        return None

    def _extract_output_message(self, converse_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the output message from Converse API response.

        Args:
            converse_response: Raw Converse API response

        Returns:
            Output message dictionary
        """
        output = converse_response.get("output", {})
        return output.get("message", {})

    def _convert_content_blocks(self, output_message: Dict[str, Any]) -> list[TextContent | FunctionCallContent]:
        """
        Convert content blocks to TextContent and FunctionCallContent objects.

        Args:
            output_message: Output message from Converse API response

        Returns:
            List of TextContent and FunctionCallContent objects
        """
        content_blocks = output_message.get("content", [])
        contents = []
        
        for block in content_blocks:
            if "text" in block:
                contents.append(TextContent(text=block["text"]))
            elif "toolUse" in block:
                # Convert tool use to FunctionCallContent for agent framework compatibility
                tool_use = block["toolUse"]
                contents.append(FunctionCallContent(
                    call_id=tool_use.get("toolUseId", f"tool_{hash(str(tool_use))}"),
                    name=tool_use.get("name", "unknown_tool"),
                    arguments=tool_use.get("input", {}),
                    raw_representation=tool_use
                ))
        
        return contents





    def _map_usage_information(self, converse_response: Dict[str, Any]) -> UsageDetails:
        """
        Map usage information to UsageDetails format.

        Args:
            converse_response: Raw Converse API response

        Returns:
            UsageDetails object with token counts
        """
        usage = converse_response.get("usage", {})
        
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", input_tokens + output_tokens)
        
        return UsageDetails(
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            total_token_count=total_tokens
        )

    def _map_completion_reason(self, converse_response: Dict[str, Any]) -> FinishReason:
        """
        Map stopReason to FinishReason values.

        Args:
            converse_response: Raw Converse API response

        Returns:
            FinishReason enum value
        """
        stop_reason = converse_response.get("stopReason", "end_turn")
        return self._map_stop_reason_to_finish_reason(stop_reason)

    def _map_stop_reason_to_finish_reason(self, stop_reason: str) -> FinishReason:
        """
        Map Converse API stop reason to FinishReason enum.

        Args:
            stop_reason: Stop reason from Converse API

        Returns:
            FinishReason enum value
        """
        # Map Converse API stop reasons to FinishReason values
        reason_mapping = {
            "end_turn": FinishReason.STOP,
            "max_tokens": FinishReason.LENGTH,
            "stop_sequence": FinishReason.STOP,
            "tool_use": FinishReason.TOOL_CALLS,
            "content_filtered": FinishReason.CONTENT_FILTER,
        }
        
        return reason_mapping.get(stop_reason, FinishReason.STOP)

    def _generate_response_metadata(
        self, converse_response: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Generate appropriate response metadata.

        Args:
            converse_response: Raw Converse API response

        Returns:
            Tuple of (response_id, created_at)
        """
        # Generate a response ID based on the response content
        response_id = f"converse-{hash(str(converse_response))}"
        
        # Use current timestamp for created_at
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        return response_id, created_at