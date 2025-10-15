"""
Unit tests for Semantic Kernel LLM provider.

Tests the SemanticKernelProvider class and LLMFactory integration with SK.
"""

import os
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from aletheia.llm.provider import (
    SemanticKernelProvider,
    LLMFactory,
    LLMMessage,
    LLMRole,
    LLMResponse,
    LLMError,
    LLMAuthenticationError,
)


class TestSemanticKernelProvider:
    """Tests for SemanticKernelProvider class."""
    
    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = SemanticKernelProvider(api_key="test-key", model="gpt-4o")
        
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4o"
        assert provider.default_timeout == 60
    
    def test_init_from_env_var(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            provider = SemanticKernelProvider(model="gpt-4o-mini")
            
            assert provider.api_key == "env-key"
            assert provider.model == "gpt-4o-mini"
    
    def test_init_without_api_key_raises_error(self):
        """Test that missing API key raises authentication error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMAuthenticationError, match="OpenAI API key not provided"):
                SemanticKernelProvider()
    
    def test_supports_model(self):
        """Test model support checking."""
        provider = SemanticKernelProvider(api_key="test-key")
        
        # Exact matches
        assert provider.supports_model("gpt-4o")
        assert provider.supports_model("gpt-4o-mini")
        assert provider.supports_model("o1-preview")
        
        # Prefix matches (versioned models)
        assert provider.supports_model("gpt-4o-2024-08-06")
        assert provider.supports_model("gpt-4-turbo-preview")
        
        # Unsupported models
        assert not provider.supports_model("claude-3")
        assert not provider.supports_model("llama-2")
    
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    def test_service_lazy_initialization(self, mock_chat_completion):
        """Test that SK service is lazily initialized."""
        provider = SemanticKernelProvider(api_key="test-key", model="gpt-4o")
        
        # Service not initialized yet
        assert provider._service is None
        
        # Access service property
        service = provider.service
        
        # Should be initialized now
        assert provider._service is not None
        mock_chat_completion.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o",
            api_key="test-key"
        )
    
    @patch("semantic_kernel.Kernel")
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    def test_kernel_initialization(self, mock_chat_completion, mock_kernel):
        """Test that SK kernel is initialized with service."""
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        provider = SemanticKernelProvider(api_key="test-key", model="gpt-4o")
        
        # Access kernel
        kernel = provider.kernel
        
        # Verify kernel creation and service addition
        mock_kernel.assert_called_once()
        mock_kernel_instance.add_service.assert_called_once_with(mock_service)
    
    @pytest.mark.asyncio
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    @patch("semantic_kernel.Kernel")
    @patch("semantic_kernel.contents.ChatHistory")
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatPromptExecutionSettings")
    async def test_complete_async_success(
        self,
        mock_settings,
        mock_chat_history,
        mock_kernel,
        mock_chat_completion
    ):
        """Test async completion with SK."""
        # Setup mocks
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        
        # Mock response
        mock_response_item = Mock()
        mock_response_item.content = "Test response"
        mock_finish_reason = Mock()
        mock_finish_reason.name = "stop"
        mock_response_item.finish_reason = mock_finish_reason
        mock_response_item.metadata = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        
        mock_service.get_chat_message_contents = AsyncMock(return_value=[mock_response_item])
        
        # Create provider and test
        provider = SemanticKernelProvider(api_key="test-key", model="gpt-4o")
        
        messages = [
            LLMMessage(role=LLMRole.SYSTEM, content="You are helpful"),
            LLMMessage(role=LLMRole.USER, content="Hello")
        ]
        
        response = await provider._complete_async(messages, temperature=0.8, max_tokens=100)
        
        # Verify response
        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.model == "gpt-4o"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
    
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    @patch("semantic_kernel.Kernel")
    @patch("semantic_kernel.contents.ChatHistory")
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatPromptExecutionSettings")
    def test_complete_with_string_input(
        self,
        mock_settings,
        mock_chat_history,
        mock_kernel,
        mock_chat_completion
    ):
        """Test completion with string input (converted to user message)."""
        # Setup mocks
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        
        # Mock response
        mock_response_item = Mock()
        mock_response_item.content = "Response to string"
        mock_response_item.finish_reason = Mock(name="stop")
        mock_response_item.metadata = {"usage": {}}
        
        mock_service.get_chat_message_contents = AsyncMock(return_value=[mock_response_item])
        
        # Create provider and test
        provider = SemanticKernelProvider(api_key="test-key")
        
        response = provider.complete("Hello, world!")
        
        # Verify response
        assert response.content == "Response to string"
    
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    @patch("semantic_kernel.Kernel")
    def test_complete_with_sk_error(self, mock_kernel, mock_chat_completion):
        """Test that SK errors are properly wrapped."""
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        
        # Mock error
        mock_service.get_chat_message_contents = AsyncMock(
            side_effect=Exception("SK service error")
        )
        
        provider = SemanticKernelProvider(api_key="test-key")
        
        with pytest.raises(LLMError, match="Semantic Kernel error"):
            provider.complete("Test")
    
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    @patch("semantic_kernel.Kernel")
    def test_complete_with_empty_response(self, mock_kernel, mock_chat_completion):
        """Test handling of empty response."""
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        
        # Mock empty response
        mock_service.get_chat_message_contents = AsyncMock(return_value=[])
        
        provider = SemanticKernelProvider(api_key="test-key")
        
        with pytest.raises(LLMError, match="No response from Semantic Kernel service"):
            provider.complete("Test")


class TestLLMFactoryWithSK:
    """Tests for LLMFactory with Semantic Kernel support."""
    
    def setup_method(self):
        """Clear cache before each test."""
        LLMFactory.clear_cache()
    
    def test_create_openai_provider_by_default(self):
        """Test that OpenAIProvider is created by default."""
        config = {"model": "gpt-4o", "api_key": "test-key"}
        
        provider = LLMFactory.create_provider(config)
        
        # Should be OpenAIProvider (not SK)
        from aletheia.llm.provider import OpenAIProvider
        assert isinstance(provider, OpenAIProvider)
        assert not isinstance(provider, SemanticKernelProvider)
    
    def test_create_sk_provider_with_config_flag(self):
        """Test creating SK provider with config flag."""
        config = {
            "model": "gpt-4o",
            "api_key": "test-key",
            "use_semantic_kernel": True
        }
        
        provider = LLMFactory.create_provider(config)
        
        assert isinstance(provider, SemanticKernelProvider)
        assert provider.model == "gpt-4o"
    
    def test_create_sk_provider_with_parameter_flag(self):
        """Test creating SK provider with function parameter."""
        config = {"model": "gpt-4o-mini", "api_key": "test-key"}
        
        provider = LLMFactory.create_provider(config, use_semantic_kernel=True)
        
        assert isinstance(provider, SemanticKernelProvider)
        assert provider.model == "gpt-4o-mini"
    
    def test_create_sk_provider_with_env_flag(self):
        """Test creating SK provider with environment variable."""
        config = {"model": "gpt-4o", "api_key": "test-key"}
        
        with patch.dict(os.environ, {"USE_SEMANTIC_KERNEL": "true"}):
            provider = LLMFactory.create_provider(config)
            
            assert isinstance(provider, SemanticKernelProvider)
    
    def test_flag_priority_parameter_over_config(self):
        """Test that parameter flag overrides config."""
        config = {
            "model": "gpt-4o",
            "api_key": "test-key",
            "use_semantic_kernel": False  # Config says no SK
        }
        
        # But parameter says yes
        provider = LLMFactory.create_provider(config, use_semantic_kernel=True)
        
        assert isinstance(provider, SemanticKernelProvider)
    
    def test_flag_priority_config_over_env(self):
        """Test that config flag overrides environment."""
        config = {
            "model": "gpt-4o",
            "api_key": "test-key",
            "use_semantic_kernel": False  # Config says no SK
        }
        
        # But env says yes
        with patch.dict(os.environ, {"USE_SEMANTIC_KERNEL": "true"}):
            provider = LLMFactory.create_provider(config)
            
            # Config should win
            from aletheia.llm.provider import OpenAIProvider
            assert isinstance(provider, OpenAIProvider)
            assert not isinstance(provider, SemanticKernelProvider)
    
    def test_cache_respects_sk_flag(self):
        """Test that cache key includes SK flag."""
        config = {"model": "gpt-4o", "api_key": "test-key"}
        
        # Create OpenAI provider
        provider1 = LLMFactory.create_provider(config, use_semantic_kernel=False)
        
        # Create SK provider (should not use cached OpenAI provider)
        provider2 = LLMFactory.create_provider(config, use_semantic_kernel=True)
        
        # Should be different instances and types
        assert provider1 is not provider2
        from aletheia.llm.provider import OpenAIProvider
        assert isinstance(provider1, OpenAIProvider)
        assert isinstance(provider2, SemanticKernelProvider)
    
    def test_env_var_parsing_variations(self):
        """Test different environment variable value formats."""
        config = {"model": "gpt-4o", "api_key": "test-key"}
        
        # Test "1"
        with patch.dict(os.environ, {"USE_SEMANTIC_KERNEL": "1"}):
            provider = LLMFactory.create_provider(config)
            assert isinstance(provider, SemanticKernelProvider)
        
        LLMFactory.clear_cache()
        
        # Test "yes"
        with patch.dict(os.environ, {"USE_SEMANTIC_KERNEL": "yes"}):
            provider = LLMFactory.create_provider(config)
            assert isinstance(provider, SemanticKernelProvider)
        
        LLMFactory.clear_cache()
        
        # Test "false"
        with patch.dict(os.environ, {"USE_SEMANTIC_KERNEL": "false"}):
            provider = LLMFactory.create_provider(config)
            from aletheia.llm.provider import OpenAIProvider
            assert isinstance(provider, OpenAIProvider)


class TestSemanticKernelIntegration:
    """Integration-style tests for SK provider."""
    
    @patch("semantic_kernel.connectors.ai.open_ai.OpenAIChatCompletion")
    @patch("semantic_kernel.Kernel")
    def test_complete_with_multiple_messages(self, mock_kernel, mock_chat_completion):
        """Test completion with multiple message types."""
        # Setup mocks
        mock_service = Mock()
        mock_chat_completion.return_value = mock_service
        
        mock_kernel_instance = Mock()
        mock_kernel.return_value = mock_kernel_instance
        
        # Mock response
        mock_response_item = Mock()
        mock_response_item.content = "Multi-message response"
        mock_response_item.finish_reason = Mock(name="stop")
        mock_response_item.metadata = {"usage": {"total_tokens": 50}}
        
        mock_service.get_chat_message_contents = AsyncMock(return_value=[mock_response_item])
        
        # Create provider
        provider = SemanticKernelProvider(api_key="test-key")
        
        # Test with system + user + assistant messages
        messages = [
            LLMMessage(role=LLMRole.SYSTEM, content="You are helpful"),
            LLMMessage(role=LLMRole.USER, content="What is 2+2?"),
            LLMMessage(role=LLMRole.ASSISTANT, content="4"),
            LLMMessage(role=LLMRole.USER, content="What is 3+3?")
        ]
        
        response = provider.complete(messages, temperature=0.5, max_tokens=50)
        
        assert response.content == "Multi-message response"
        assert response.usage["total_tokens"] == 50
    
    def test_sk_provider_backward_compatibility(self):
        """Test that SK provider maintains interface compatibility."""
        provider = SemanticKernelProvider(api_key="test-key", model="gpt-4o")
        
        # Should have same interface as OpenAIProvider
        assert hasattr(provider, "complete")
        assert hasattr(provider, "supports_model")
        assert hasattr(provider, "model")
        assert hasattr(provider, "api_key")
        
        # Should support same models
        assert provider.supports_model("gpt-4o")
        assert provider.supports_model("gpt-4o-mini")
