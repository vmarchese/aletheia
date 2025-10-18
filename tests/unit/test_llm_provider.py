"""
Unit tests for LLM provider abstraction.

Tests cover:
- LLMMessage and LLMResponse dataclasses
- LLMProvider interface
- OpenAIProvider implementation
- LLMFactory
- Error handling and retry logic
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from aletheia.llm.provider import (
    LLMMessage,
    LLMResponse,
    LLMRole,
    LLMProvider,
    OpenAIProvider,
    LLMFactory,
    LLMError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMTimeoutError,
)


# ============================================================================
# Test LLMMessage
# ============================================================================

class TestLLMMessage:
    """Test LLMMessage dataclass."""
    
    def test_create_message(self):
        """Test creating a basic message."""
        msg = LLMMessage(role=LLMRole.USER, content="Hello")
        assert msg.role == LLMRole.USER
        assert msg.content == "Hello"
        assert msg.name is None
        assert msg.metadata == {}
    
    def test_create_message_with_name(self):
        """Test creating a message with name."""
        msg = LLMMessage(role=LLMRole.ASSISTANT, content="Hi", name="bot")
        assert msg.name == "bot"
    
    def test_create_message_with_metadata(self):
        """Test creating a message with metadata."""
        metadata = {"timestamp": 1234567890}
        msg = LLMMessage(role=LLMRole.SYSTEM, content="System prompt", metadata=metadata)
        assert msg.metadata == metadata
    
    def test_to_dict(self):
        """Test converting message to dictionary."""
        msg = LLMMessage(role=LLMRole.USER, content="Test")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Test"}
    
    def test_to_dict_with_name(self):
        """Test converting message with name to dictionary."""
        msg = LLMMessage(role=LLMRole.ASSISTANT, content="Response", name="assistant")
        result = msg.to_dict()
        assert result == {"role": "assistant", "content": "Response", "name": "assistant"}
    
    def test_role_enum_values(self):
        """Test LLMRole enum values."""
        assert LLMRole.SYSTEM.value == "system"
        assert LLMRole.USER.value == "user"
        assert LLMRole.ASSISTANT.value == "assistant"


# ============================================================================
# Test LLMResponse
# ============================================================================

class TestLLMResponse:
    """Test LLMResponse dataclass."""
    
    def test_create_response(self):
        """Test creating a basic response."""
        resp = LLMResponse(content="Hello", model="gpt-4o")
        assert resp.content == "Hello"
        assert resp.model == "gpt-4o"
        assert resp.usage == {}
        assert resp.finish_reason is None
        assert resp.metadata == {}
    
    def test_create_response_with_usage(self):
        """Test creating response with usage data."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        resp = LLMResponse(content="Test", model="gpt-4o", usage=usage)
        assert resp.usage == usage
    
    def test_create_response_with_finish_reason(self):
        """Test creating response with finish reason."""
        resp = LLMResponse(content="Test", model="gpt-4o", finish_reason="stop")
        assert resp.finish_reason == "stop"


# ============================================================================
# Test Error Classes
# ============================================================================

class TestLLMErrors:
    """Test LLM error exceptions."""
    
    def test_llm_error(self):
        """Test base LLMError."""
        with pytest.raises(LLMError):
            raise LLMError("Test error")
    
    def test_rate_limit_error(self):
        """Test LLMRateLimitError."""
        with pytest.raises(LLMRateLimitError):
            raise LLMRateLimitError("Rate limit exceeded")
    
    def test_authentication_error(self):
        """Test LLMAuthenticationError."""
        with pytest.raises(LLMAuthenticationError):
            raise LLMAuthenticationError("Invalid API key")
    
    def test_timeout_error(self):
        """Test LLMTimeoutError."""
        with pytest.raises(LLMTimeoutError):
            raise LLMTimeoutError("Request timed out")
    
    def test_error_inheritance(self):
        """Test error class inheritance."""
        assert issubclass(LLMRateLimitError, LLMError)
        assert issubclass(LLMAuthenticationError, LLMError)
        assert issubclass(LLMTimeoutError, LLMError)


# ============================================================================
# Test OpenAIProvider
# ============================================================================

class TestOpenAIProvider:
    """Test OpenAI provider implementation."""
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123"})
    def test_init_with_env_var(self):
        """Test initialization with environment variable."""
        provider = OpenAIProvider()
        assert provider.api_key == "test-key-123"
        assert provider.model == "gpt-4o"
    
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = OpenAIProvider(api_key="custom-key")
        assert provider.api_key == "custom-key"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(LLMAuthenticationError) as exc_info:
            OpenAIProvider()
        assert "API key not provided" in str(exc_info.value)
    
    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        provider = OpenAIProvider(api_key="test", model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"
    
    def test_init_with_base_url(self):
        """Test initialization with custom base URL."""
        provider = OpenAIProvider(api_key="test", base_url="https://custom.api")
        assert provider.base_url == "https://custom.api"
    
    def test_init_with_timeout(self):
        """Test initialization with custom timeout."""
        provider = OpenAIProvider(api_key="test", timeout=120)
        assert provider.default_timeout == 120
    
    def test_supports_model_exact_match(self):
        """Test model support check with exact match."""
        provider = OpenAIProvider(api_key="test")
        assert provider.supports_model("gpt-4o") is True
        assert provider.supports_model("gpt-4o-mini") is True
        assert provider.supports_model("o1-preview") is True
    
    def test_supports_model_prefix_match(self):
        """Test model support check with prefix match."""
        provider = OpenAIProvider(api_key="test")
        assert provider.supports_model("gpt-4o-2024-08-06") is True
        assert provider.supports_model("gpt-4-turbo-preview") is True
    
    def test_supports_model_unsupported(self):
        """Test model support check with unsupported model."""
        provider = OpenAIProvider(api_key="test")
        assert provider.supports_model("claude-3") is False
        assert provider.supports_model("llama-2") is False
    
    def test_normalize_messages_string(self):
        """Test normalizing string input to messages."""
        provider = OpenAIProvider(api_key="test")
        messages = provider._normalize_messages("Hello")
        assert len(messages) == 1
        assert messages[0].role == LLMRole.USER
        assert messages[0].content == "Hello"
    
    def test_normalize_messages_list(self):
        """Test normalizing list of messages."""
        provider = OpenAIProvider(api_key="test")
        input_messages = [
            LLMMessage(role=LLMRole.SYSTEM, content="System"),
            LLMMessage(role=LLMRole.USER, content="User"),
        ]
        messages = provider._normalize_messages(input_messages)
        assert messages == input_messages
    
    def test_normalize_messages_dict_list(self):
        """Test normalizing list of dict messages (common pattern)."""
        provider = OpenAIProvider(api_key="test")
        input_messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
        ]
        messages = provider._normalize_messages(input_messages)
        assert len(messages) == 2
        assert messages[0].role == LLMRole.SYSTEM
        assert messages[0].content == "System"
        assert messages[1].role == LLMRole.USER
        assert messages[1].content == "User"
    
    @patch("openai.OpenAI")
    def test_complete_simple_string(self, mock_openai_class):
        """Test completion with simple string input."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock the response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, how can I help?"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        provider = OpenAIProvider(api_key="test")
        response = provider.complete("Hello")
        
        assert response.content == "Hello, how can I help?"
        assert response.model == "gpt-4o"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
    
    @patch("openai.OpenAI")
    def test_complete_with_messages(self, mock_openai_class):
        """Test completion with list of messages."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 40
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test")
        messages = [
            LLMMessage(role=LLMRole.SYSTEM, content="You are helpful"),
            LLMMessage(role=LLMRole.USER, content="Hello"),
        ]
        response = provider.complete(messages)
        
        assert response.content == "Response"
        # Check the API was called with correct messages
        call_args = mock_client.chat.completions.create.call_args
        assert len(call_args.kwargs["messages"]) == 2
    
    @patch("openai.OpenAI")
    def test_complete_with_temperature(self, mock_openai_class):
        """Test completion with custom temperature."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test")
        provider.complete("Hello", temperature=0.2)
        
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.2
    
    @patch("openai.OpenAI")
    def test_complete_with_max_tokens(self, mock_openai_class):
        """Test completion with max_tokens."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "length"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 110
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test")
        response = provider.complete("Hello", max_tokens=100)
        
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 100
        assert response.finish_reason == "length"
    
    @patch("openai.OpenAI")
    def test_complete_with_custom_model(self, mock_openai_class):
        """Test completion with custom model override."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        provider.complete("Hello", model="gpt-4o-mini")
        
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o-mini"
    
    @patch("openai.OpenAI")
    @patch("time.sleep")
    def test_complete_rate_limit_retry(self, mock_sleep, mock_openai_class):
        """Test retry logic on rate limit error."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # First two calls fail with rate limit, third succeeds
        mock_choice = MagicMock()
        mock_choice.message.content = "Success"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        mock_client.chat.completions.create.side_effect = [
            Exception("rate_limit exceeded"),
            Exception("rate limit error"),
            mock_response,
        ]
        
        provider = OpenAIProvider(api_key="test")
        response = provider.complete("Hello")
        
        assert response.content == "Success"
        assert mock_client.chat.completions.create.call_count == 3
        assert mock_sleep.call_count == 2  # Slept twice before success
    
    @patch("openai.OpenAI")
    @patch("time.sleep")
    def test_complete_rate_limit_exhausted(self, mock_sleep, mock_openai_class):
        """Test rate limit error after exhausting retries."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # All attempts fail
        mock_client.chat.completions.create.side_effect = Exception("rate_limit exceeded")
        
        provider = OpenAIProvider(api_key="test")
        
        with pytest.raises(LLMRateLimitError) as exc_info:
            provider.complete("Hello")
        
        assert "Rate limit exceeded" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 3
    
    @patch("openai.OpenAI")
    def test_complete_authentication_error(self, mock_openai_class):
        """Test authentication error handling."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("invalid api_key")
        
        provider = OpenAIProvider(api_key="invalid")
        
        with pytest.raises(LLMAuthenticationError) as exc_info:
            provider.complete("Hello")
        
        assert "Authentication failed" in str(exc_info.value)
    
    @patch("openai.OpenAI")
    def test_complete_timeout_error(self, mock_openai_class):
        """Test timeout error handling."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("request timeout")
        
        provider = OpenAIProvider(api_key="test")
        
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.complete("Hello")
        
        assert "timed out" in str(exc_info.value)
    
    @patch("openai.OpenAI")
    def test_complete_general_error(self, mock_openai_class):
        """Test general error handling."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("unknown error")
        
        provider = OpenAIProvider(api_key="test")
        
        with pytest.raises(LLMError) as exc_info:
            provider.complete("Hello")
        
        assert "OpenAI API error" in str(exc_info.value)


# ============================================================================
# Test LLMFactory
# ============================================================================

class TestLLMFactory:
    """Test LLM factory."""
    
    def setup_method(self):
        """Clear cache before each test."""
        LLMFactory.clear_cache()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_openai_provider_default(self):
        """Test creating OpenAI provider with defaults."""
        config = {"model": "gpt-4o"}
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"
        assert provider.api_key == "test-key"
    
    def test_create_openai_provider_with_api_key(self):
        """Test creating OpenAI provider with explicit API key."""
        config = {"model": "gpt-4o", "api_key": "explicit-key"}
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "explicit-key"
    
    @patch.dict(os.environ, {"CUSTOM_KEY": "custom-value"})
    def test_create_openai_provider_with_env_var(self):
        """Test creating OpenAI provider with custom env var."""
        config = {"model": "gpt-4o", "api_key_env": "CUSTOM_KEY"}
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.api_key == "custom-value"
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_openai_provider_with_timeout(self):
        """Test creating OpenAI provider with custom timeout."""
        config = {"model": "gpt-4o", "timeout": 120}
        provider = LLMFactory.create_provider(config)
        
        assert provider.default_timeout == 120
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_openai_provider_with_base_url(self):
        """Test creating OpenAI provider with custom base URL."""
        config = {"model": "gpt-4o", "base_url": "https://custom.api"}
        provider = LLMFactory.create_provider(config)
        
        assert provider.base_url == "https://custom.api"
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_provider_gpt4_mini(self):
        """Test creating provider for gpt-4o-mini."""
        config = {"model": "gpt-4o-mini"}
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o-mini"
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_provider_o1_preview(self):
        """Test creating provider for o1-preview."""
        config = {"model": "o1-preview"}
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "o1-preview"
    
    def test_create_provider_unsupported_model(self):
        """Test creating provider with unsupported model."""
        config = {"model": "claude-3"}
        
        with pytest.raises(ValueError) as exc_info:
            LLMFactory.create_provider(config)
        
        assert "Unsupported model" in str(exc_info.value)
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_provider_caching(self):
        """Test that providers are cached."""
        config = {"model": "gpt-4o"}
        
        provider1 = LLMFactory.create_provider(config, use_cache=True)
        provider2 = LLMFactory.create_provider(config, use_cache=True)
        
        assert provider1 is provider2  # Same instance
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_provider_no_caching(self):
        """Test creating providers without caching."""
        config = {"model": "gpt-4o"}
        
        provider1 = LLMFactory.create_provider(config, use_cache=False)
        provider2 = LLMFactory.create_provider(config, use_cache=False)
        
        assert provider1 is not provider2  # Different instances
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_clear_cache(self):
        """Test clearing provider cache."""
        config = {"model": "gpt-4o"}
        
        provider1 = LLMFactory.create_provider(config, use_cache=True)
        LLMFactory.clear_cache()
        provider2 = LLMFactory.create_provider(config, use_cache=True)
        
        assert provider1 is not provider2
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_cache_key_with_different_env_vars(self):
        """Test that different env vars create different cache entries."""
        config1 = {"model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}
        config2 = {"model": "gpt-4o", "api_key_env": "CUSTOM_KEY"}
        
        provider1 = LLMFactory.create_provider(config1, use_cache=True)
        
        with patch.dict(os.environ, {"CUSTOM_KEY": "different-key"}):
            provider2 = LLMFactory.create_provider(config2, use_cache=True)
        
        # Should be different providers due to different env var names
        assert provider1 is not provider2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    @patch("openai.OpenAI")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_factory_to_completion(self, mock_openai_class):
        """Test complete workflow from factory to completion."""
        # Mock OpenAI
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 15
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Create provider via factory
        config = {"model": "gpt-4o"}
        provider = LLMFactory.create_provider(config)
        
        # Generate completion
        response = provider.complete("Say hello")
        
        assert response.content == "Hello, world!"
        assert response.usage["total_tokens"] == 15
    
    @patch("openai.OpenAI")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_multi_turn_conversation(self, mock_openai_class):
        """Test multi-turn conversation."""
        # Clear cache to avoid interference from previous tests
        LLMFactory.clear_cache()
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock responses
        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1234567890
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 30
        mock_response.usage.total_tokens = 50
        
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = LLMFactory.create_provider({"model": "gpt-4o"})
        
        # Build conversation
        messages = [
            LLMMessage(role=LLMRole.SYSTEM, content="You are helpful"),
            LLMMessage(role=LLMRole.USER, content="Hello"),
        ]
        
        response1 = provider.complete(messages)
        assert response1.content == "Response"
        
        # Add response and continue
        messages.append(LLMMessage(role=LLMRole.ASSISTANT, content=response1.content))
        messages.append(LLMMessage(role=LLMRole.USER, content="Tell me more"))
        
        response2 = provider.complete(messages)
        assert response2.content == "Response"
        
        # Should have been called twice
        assert mock_client.chat.completions.create.call_count == 2
