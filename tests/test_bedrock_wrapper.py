"""
Tests for the Bedrock response format wrapper.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator

from aletheia.agents.bedrock_wrapper import BedrockResponseFormatWrapper, BedrockResponseWrapper, wrap_bedrock_agent
from aletheia.agents.model import AgentResponse, Findings, Decisions, NextActions


class MockResponse:
    """Mock response object for testing."""
    def __init__(self, text: str, contents=None):
        self.text = text
        self.contents = contents or []


class MockChatAgent:
    """Mock ChatAgent for testing."""
    def __init__(self):
        self.run_stream = AsyncMock()


@pytest.fixture
def mock_chat_agent():
    """Create a mock ChatAgent."""
    return MockChatAgent()


@pytest.fixture
def sample_agent_response():
    """Create a sample AgentResponse for testing."""
    return {
        "confidence": 0.85,
        "agent": "test_agent",
        "findings": {
            "summary": "Test findings summary",
            "details": "Detailed test findings",
            "tool_outputs": [],
            "additional_output": None,
            "skill_used": None,
            "knowledge_searched": False
        },
        "decisions": {
            "approach": "Test approach",
            "tools_used": ["tool1", "tool2"],
            "skills_loaded": [],
            "rationale": "Test rationale",
            "checklist": ["item1", "item2"],
            "additional_output": None
        },
        "next_actions": {
            "steps": ["step1", "step2"],
            "additional_output": None
        },
        "errors": None
    }


class TestBedrockResponseWrapper:
    """Test cases for BedrockResponseWrapper."""

    def test_response_wrapper_initialization(self):
        """Test that the response wrapper initializes correctly."""
        wrapper = BedrockResponseWrapper("test text")
        assert wrapper.text == "test text"
        assert wrapper.contents == []
        
        # Test with contents
        contents = ["usage_info"]
        wrapper = BedrockResponseWrapper("test text", contents)
        assert wrapper.text == "test text"
        assert wrapper.contents == contents


class TestBedrockResponseFormatWrapper:
    """Test cases for BedrockResponseFormatWrapper."""

    def test_wrapper_initialization(self, mock_chat_agent):
        """Test that the wrapper properly initializes and replaces run_stream."""
        original_run_stream = mock_chat_agent.run_stream
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        # Verify the run_stream method was replaced
        assert mock_chat_agent.run_stream != original_run_stream
        assert wrapper._original_run_stream == original_run_stream

    @pytest.mark.asyncio
    async def test_run_stream_without_response_format(self, mock_chat_agent):
        """Test that calls without response_format use the original method."""
        # Setup mock to return a simple response
        async def mock_stream(*args, **kwargs):
            yield MockResponse("test response")
        
        mock_chat_agent.run_stream = mock_stream
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        # Call without response_format
        responses = []
        async for response in wrapper._wrapped_run_stream([]):
            responses.append(response)
        
        assert len(responses) == 1
        assert responses[0].text == "test response"

    @pytest.mark.asyncio
    async def test_run_stream_with_response_format(self, mock_chat_agent, sample_agent_response):
        """Test that calls with response_format add JSON instructions."""
        # Setup mock to return JSON response
        json_response = json.dumps(sample_agent_response)
        
        async def mock_stream(messages, **kwargs):
            # Verify that JSON instructions were added
            assert len(messages) > 0
            # Check if system message with JSON instructions was added
            has_json_instructions = any(
                "JSON" in str(msg.contents[0].text) if msg.contents else False
                for msg in messages
            )
            assert has_json_instructions
            yield MockResponse(json_response)
        
        mock_chat_agent.run_stream = mock_stream
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        # Call with response_format
        responses = []
        async for response in wrapper._wrapped_run_stream([], response_format=AgentResponse):
            responses.append(response)
        
        assert len(responses) == 1
        # Verify the response contains valid JSON
        parsed = json.loads(responses[0].text)
        assert parsed["confidence"] == 0.85
        assert parsed["agent"] == "test_agent"
        # Verify it's a BedrockResponseWrapper
        assert isinstance(responses[0], BedrockResponseWrapper)

    def test_extract_json_from_text(self, mock_chat_agent):
        """Test JSON extraction from various text formats."""
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        # Test clean JSON
        clean_json = '{"test": "value"}'
        result = wrapper._extract_json_from_text(clean_json)
        assert result == clean_json
        
        # Test JSON with markdown
        markdown_json = '```json\n{"test": "value"}\n```'
        result = wrapper._extract_json_from_text(markdown_json)
        assert result == '{"test": "value"}'
        
        # Test JSON with extra text
        text_with_json = 'Here is the response: {"test": "value"} and some more text'
        result = wrapper._extract_json_from_text(text_with_json)
        assert result == '{"test": "value"}'
        
        # Test incomplete JSON
        incomplete_json = '{"test": "value"'
        result = wrapper._extract_json_from_text(incomplete_json)
        assert result is None
        
        # Test no JSON
        no_json = 'This is just text without JSON'
        result = wrapper._extract_json_from_text(no_json)
        assert result is None

    def test_try_parse_json_valid(self, mock_chat_agent, sample_agent_response):
        """Test parsing valid JSON against AgentResponse schema."""
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        json_text = json.dumps(sample_agent_response)
        result = wrapper._try_parse_json(json_text, AgentResponse)
        
        assert result is not None
        assert result["confidence"] == 0.85
        assert result["agent"] == "test_agent"

    def test_try_parse_json_invalid(self, mock_chat_agent):
        """Test parsing invalid JSON."""
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        # Invalid JSON syntax
        invalid_json = '{"test": invalid}'
        result = wrapper._try_parse_json(invalid_json, AgentResponse)
        assert result is None
        
        # Valid JSON but invalid schema
        valid_json_invalid_schema = '{"wrong": "schema"}'
        result = wrapper._try_parse_json(valid_json_invalid_schema, AgentResponse)
        assert result is None

    def test_create_json_instructions(self, mock_chat_agent):
        """Test creation of JSON formatting instructions."""
        wrapper = BedrockResponseFormatWrapper(mock_chat_agent)
        
        instructions = wrapper._create_json_instructions(AgentResponse, AgentResponse.model_json_schema())
        
        assert "JSON" in instructions
        assert "AgentResponse" in instructions
        assert "confidence" in instructions
        assert "agent" in instructions
        assert "findings" in instructions
        assert "decisions" in instructions
        assert "next_actions" in instructions


class TestWrapBedrockAgent:
    """Test cases for the wrap_bedrock_agent function."""

    def test_wrap_bedrock_agent_with_bedrock_provider(self, mock_chat_agent):
        """Test that Bedrock agents get wrapped."""
        original_run_stream = mock_chat_agent.run_stream
        
        wrap_bedrock_agent(mock_chat_agent, "bedrock")
        
        # Verify the run_stream method was replaced
        assert mock_chat_agent.run_stream != original_run_stream

    def test_wrap_bedrock_agent_with_other_providers(self, mock_chat_agent):
        """Test that non-Bedrock agents don't get wrapped."""
        original_run_stream = mock_chat_agent.run_stream
        
        # Test with Azure
        wrap_bedrock_agent(mock_chat_agent, "azure")
        assert mock_chat_agent.run_stream == original_run_stream
        
        # Test with OpenAI
        wrap_bedrock_agent(mock_chat_agent, "openai")
        assert mock_chat_agent.run_stream == original_run_stream


if __name__ == "__main__":
    pytest.main([__file__])