"""
Tests for Bedrock Converse API message conversion utilities.
"""

import pytest
from agent_framework import ChatMessage, TextContent, Role
from aletheia.agents.bedrock_tool_converter import ConverseMessageConverter


class TestConverseMessageConverter:
    """Test cases for ConverseMessageConverter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.converter = ConverseMessageConverter()

    def test_convert_user_message(self):
        """Test conversion of a simple user message."""
        messages = [
            ChatMessage(
                role=Role.USER, contents=[TextContent(text="Hello, how are you?")]
            )
        ]

        result = self.converter.convert_to_converse_format(messages)

        assert result["system"] == []
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == [{"text": "Hello, how are you?"}]

    def test_convert_assistant_message(self):
        """Test conversion of an assistant message."""
        messages = [
            ChatMessage(
                role=Role.ASSISTANT,
                contents=[TextContent(text="I'm doing well, thank you!")],
            )
        ]

        result = self.converter.convert_to_converse_format(messages)

        assert result["system"] == []
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "assistant"
        assert result["messages"][0]["content"] == [
            {"text": "I'm doing well, thank you!"}
        ]

    def test_convert_system_message(self):
        """Test conversion of a system message."""
        messages = [
            ChatMessage(
                role=Role.SYSTEM,
                contents=[TextContent(text="You are a helpful assistant.")],
            )
        ]

        result = self.converter.convert_to_converse_format(messages)

        assert len(result["system"]) == 1
        assert result["system"][0]["text"] == "You are a helpful assistant."
        assert result["messages"] == []

    def test_convert_mixed_messages(self):
        """Test conversion of mixed message types."""
        messages = [
            ChatMessage(
                role=Role.SYSTEM,
                contents=[TextContent(text="You are a helpful assistant.")],
            ),
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello!")]),
            ChatMessage(role=Role.ASSISTANT, contents=[TextContent(text="Hi there!")]),
            ChatMessage(role=Role.USER, contents=[TextContent(text="How are you?")]),
        ]

        result = self.converter.convert_to_converse_format(messages)

        # Check system messages
        assert len(result["system"]) == 1
        assert result["system"][0]["text"] == "You are a helpful assistant."

        # Check conversation messages
        assert len(result["messages"]) == 3
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == [{"text": "Hello!"}]
        assert result["messages"][1]["role"] == "assistant"
        assert result["messages"][1]["content"] == [{"text": "Hi there!"}]
        assert result["messages"][2]["role"] == "user"
        assert result["messages"][2]["content"] == [{"text": "How are you?"}]

    def test_convert_multiple_system_messages(self):
        """Test conversion of multiple system messages."""
        messages = [
            ChatMessage(
                role=Role.SYSTEM, contents=[TextContent(text="You are helpful.")]
            ),
            ChatMessage(role=Role.SYSTEM, contents=[TextContent(text="Be concise.")]),
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello!")]),
        ]

        result = self.converter.convert_to_converse_format(messages)

        # Check system messages
        assert len(result["system"]) == 2
        assert result["system"][0]["text"] == "You are helpful."
        assert result["system"][1]["text"] == "Be concise."

        # Check conversation messages
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == [{"text": "Hello!"}]

    def test_convert_empty_messages(self):
        """Test conversion of empty message list."""
        messages = []

        result = self.converter.convert_to_converse_format(messages)

        assert result["system"] == []
        assert result["messages"] == []

    def test_convert_messages_with_empty_content(self):
        """Test conversion of messages with empty content."""
        messages = [
            ChatMessage(role=Role.USER, contents=[TextContent(text="")]),
            ChatMessage(
                role=Role.SYSTEM, contents=[TextContent(text="   ")]
            ),  # whitespace only
            ChatMessage(role=Role.USER, contents=[TextContent(text="Hello!")]),
        ]

        result = self.converter.convert_to_converse_format(messages)

        # Empty/whitespace-only messages should be filtered out
        assert result["system"] == []
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == [{"text": "Hello!"}]

    def test_extract_system_messages(self):
        """Test system message extraction specifically."""
        messages = [
            ChatMessage(
                role=Role.SYSTEM, contents=[TextContent(text="System message 1")]
            ),
            ChatMessage(role=Role.USER, contents=[TextContent(text="User message")]),
            ChatMessage(
                role=Role.SYSTEM, contents=[TextContent(text="System message 2")]
            ),
        ]

        result = self.converter.extract_system_messages(messages)

        assert len(result) == 2
        assert result[0]["text"] == "System message 1"
        assert result[1]["text"] == "System message 2"

    def test_convert_conversation_messages(self):
        """Test conversation message conversion specifically."""
        messages = [
            ChatMessage(
                role=Role.SYSTEM, contents=[TextContent(text="System message")]
            ),
            ChatMessage(role=Role.USER, contents=[TextContent(text="User message")]),
            ChatMessage(
                role=Role.ASSISTANT, contents=[TextContent(text="Assistant message")]
            ),
        ]

        result = self.converter.convert_conversation_messages(messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == [{"text": "User message"}]
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == [{"text": "Assistant message"}]

    def test_multiple_content_blocks(self):
        """Test messages with multiple content blocks."""
        # Create a message with multiple TextContent objects
        contents = [TextContent(text="First part. "), TextContent(text="Second part.")]
        messages = [ChatMessage(role=Role.USER, contents=contents)]

        result = self.converter.convert_to_converse_format(messages)

        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == [
            {"text": "First part. Second part."}
        ]
