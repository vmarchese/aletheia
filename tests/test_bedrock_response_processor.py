"""
Tests for Bedrock Converse API response processing utilities.
"""

import pytest
from datetime import datetime
from agent_framework import ChatMessage, TextContent, Role, FinishReason, UsageDetails, ChatResponse, ChatResponseUpdate
from aletheia.agents.bedrock_response_processor import ConverseResponseProcessor


class TestConverseResponseProcessor:
    """Test cases for ConverseResponseProcessor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = ConverseResponseProcessor()

    def test_create_chat_response_basic(self):
        """Test basic conversion of Converse API response to ChatResponse."""
        converse_response = {
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
            }
        }
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        result = self.processor.create_chat_response(converse_response, model_id)

        # Check basic structure
        assert isinstance(result, ChatResponse)
        assert result.model_id == model_id
        assert result.finish_reason == FinishReason.STOP
        
        # Check message content
        assert len(result.messages) == 1
        assert result.messages[0].role == Role.ASSISTANT
        assert len(result.messages[0].contents) == 1
        assert result.messages[0].contents[0].text == "Hello! I'm doing well, thank you for asking."
        
        # Check usage details
        assert result.usage_details.input_token_count == 10
        assert result.usage_details.output_token_count == 12
        assert result.usage_details.total_token_count == 22
        
        # Check metadata
        assert result.response_id.startswith("converse-")
        assert result.created_at is not None

    def test_create_chat_response_multiple_content_blocks(self):
        """Test conversion with multiple content blocks."""
        converse_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "First part. "},
                        {"text": "Second part."}
                    ]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 5,
                "outputTokens": 8,
                "totalTokens": 13
            }
        }
        model_id = "test-model"

        result = self.processor.create_chat_response(converse_response, model_id)

        # Check that both content blocks are converted
        assert len(result.messages[0].contents) == 2
        assert result.messages[0].contents[0].text == "First part. "
        assert result.messages[0].contents[1].text == "Second part."

    def test_create_chat_response_different_stop_reasons(self):
        """Test mapping of different stop reasons to finish reasons."""
        test_cases = [
            ("end_turn", FinishReason.STOP),
            ("max_tokens", FinishReason.LENGTH),
            ("stop_sequence", FinishReason.STOP),
            ("tool_use", FinishReason.TOOL_CALLS),
            ("content_filtered", FinishReason.CONTENT_FILTER),
            ("unknown_reason", FinishReason.STOP),  # Default case
        ]

        for stop_reason, expected_finish_reason in test_cases:
            converse_response = {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "Test response"}]
                    }
                },
                "stopReason": stop_reason,
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}
            }

            result = self.processor.create_chat_response(converse_response, "test-model")
            assert result.finish_reason == expected_finish_reason

    def test_create_chat_response_missing_usage(self):
        """Test handling of missing usage information."""
        converse_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Test response"}]
                }
            },
            "stopReason": "end_turn"
            # No usage field
        }

        result = self.processor.create_chat_response(converse_response, "test-model")

        # Should default to zero values
        assert result.usage_details.input_token_count == 0
        assert result.usage_details.output_token_count == 0
        assert result.usage_details.total_token_count == 0

    def test_create_chat_response_empty_content(self):
        """Test handling of empty content blocks."""
        converse_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": []  # Empty content
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 1, "outputTokens": 0, "totalTokens": 1}
        }

        result = self.processor.create_chat_response(converse_response, "test-model")

        # Should handle empty content gracefully
        assert len(result.messages[0].contents) == 0

    def test_process_streaming_event_content_delta(self):
        """Test processing of contentBlockDelta streaming events."""
        event = {
            "contentBlockDelta": {
                "delta": {
                    "text": "Hello"
                },
                "contentBlockIndex": 0
            }
        }

        result = self.processor.process_streaming_event(event)

        assert isinstance(result, ChatResponseUpdate)
        assert result.role == Role.ASSISTANT
        assert len(result.contents) == 1
        assert result.contents[0].text == "Hello"
        assert result.finish_reason is None

    def test_process_streaming_event_message_stop(self):
        """Test processing of messageStop streaming events."""
        event = {
            "messageStop": {
                "stopReason": "end_turn"
            }
        }

        result = self.processor.process_streaming_event(event)

        assert isinstance(result, ChatResponseUpdate)
        assert result.role == Role.ASSISTANT
        assert len(result.contents) == 0
        assert result.finish_reason == FinishReason.STOP

    def test_process_streaming_event_content_block_start(self):
        """Test processing of contentBlockStart streaming events."""
        event = {
            "contentBlockStart": {
                "start": {
                    "text": ""
                },
                "contentBlockIndex": 0
            }
        }

        result = self.processor.process_streaming_event(event)

        # Should return None for start events
        assert result is None

    def test_process_streaming_event_metadata(self):
        """Test processing of metadata streaming events."""
        event = {
            "metadata": {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 12,
                    "totalTokens": 22
                }
            }
        }

        result = self.processor.process_streaming_event(event)

        # Should return None for metadata events
        assert result is None

    def test_process_streaming_event_unknown(self):
        """Test processing of unknown streaming events."""
        event = {
            "unknownEvent": {
                "data": "some data"
            }
        }

        result = self.processor.process_streaming_event(event)

        # Should return None for unknown events
        assert result is None

    def test_extract_output_message(self):
        """Test extraction of output message from response."""
        converse_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Test message"}]
                }
            }
        }

        result = self.processor._extract_output_message(converse_response)

        assert result["role"] == "assistant"
        assert result["content"] == [{"text": "Test message"}]

    def test_extract_output_message_missing(self):
        """Test extraction when output message is missing."""
        converse_response = {}

        result = self.processor._extract_output_message(converse_response)

        # Should return empty dict when missing
        assert result == {}

    def test_convert_content_blocks(self):
        """Test conversion of content blocks to TextContent objects."""
        output_message = {
            "content": [
                {"text": "First block"},
                {"text": "Second block"},
                {"image": "base64data"}  # Non-text block should be ignored
            ]
        }

        result = self.processor._convert_content_blocks(output_message)

        # Should only convert text blocks
        assert len(result) == 2
        assert all(isinstance(content, TextContent) for content in result)
        assert result[0].text == "First block"
        assert result[1].text == "Second block"

    def test_convert_content_blocks_empty(self):
        """Test conversion of empty content blocks."""
        output_message = {"content": []}

        result = self.processor._convert_content_blocks(output_message)

        assert result == []

    def test_map_usage_information(self):
        """Test mapping of usage information."""
        converse_response = {
            "usage": {
                "inputTokens": 15,
                "outputTokens": 25,
                "totalTokens": 40
            }
        }

        result = self.processor._map_usage_information(converse_response)

        assert isinstance(result, UsageDetails)
        assert result.input_token_count == 15
        assert result.output_token_count == 25
        assert result.total_token_count == 40

    def test_map_usage_information_partial(self):
        """Test mapping of partial usage information."""
        converse_response = {
            "usage": {
                "inputTokens": 10,
                "outputTokens": 15
                # totalTokens missing
            }
        }

        result = self.processor._map_usage_information(converse_response)

        assert result.input_token_count == 10
        assert result.output_token_count == 15
        assert result.total_token_count == 25  # Should calculate from input + output

    def test_generate_response_metadata(self):
        """Test generation of response metadata."""
        converse_response = {"test": "data"}

        response_id, created_at = self.processor._generate_response_metadata(converse_response)

        assert response_id.startswith("converse-")
        assert isinstance(created_at, str)
        # Check that it's a valid ISO format timestamp
        datetime.fromisoformat(created_at.replace('Z', '+00:00'))

    def test_map_stop_reason_to_finish_reason(self):
        """Test mapping of stop reasons to finish reasons."""
        test_cases = [
            ("end_turn", FinishReason.STOP),
            ("max_tokens", FinishReason.LENGTH),
            ("stop_sequence", FinishReason.STOP),
            ("tool_use", FinishReason.TOOL_CALLS),
            ("content_filtered", FinishReason.CONTENT_FILTER),
            ("unknown", FinishReason.STOP),
        ]

        for stop_reason, expected in test_cases:
            result = self.processor._map_stop_reason_to_finish_reason(stop_reason)
            assert result == expected