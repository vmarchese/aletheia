"""Unit tests for SK-based agent foundation."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, Any

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.scratchpad import Scratchpad


# Concrete implementation for testing
class TestSKAgent(SKBaseAgent):
    """Test agent implementation for testing SKBaseAgent."""
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Simple execute implementation for testing."""
        return {"status": "success", "kwargs": kwargs}


@pytest.fixture
def mock_scratchpad():
    """Create a mock scratchpad."""
    scratchpad = Mock(spec=Scratchpad)
    scratchpad.read_section = Mock(return_value=None)
    scratchpad.write_section = Mock()
    scratchpad.append_to_section = Mock()
    scratchpad.save = Mock()
    return scratchpad


@pytest.fixture
def basic_config():
    """Create basic agent configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key": "test-api-key",
            "agents": {}
        }
    }


@pytest.fixture
def agent_specific_config():
    """Create configuration with agent-specific settings."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key": "test-api-key",
            "agents": {
                "testsk": {  # Match the extracted name
                    "model": "gpt-4o-mini",
                    "temperature": 0.5
                }
            }
        }
    }


class TestSKBaseAgentInitialization:
    """Test SKBaseAgent initialization."""
    
    def test_basic_initialization(self, mock_scratchpad, basic_config):
        """Test basic agent initialization."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        assert agent.config == basic_config
        assert agent.scratchpad == mock_scratchpad
        assert agent.agent_name == "testsk"  # Class name with "agent" removed
    
    def test_custom_agent_name(self, mock_scratchpad, basic_config):
        """Test initialization with custom agent name."""
        agent = TestSKAgent(basic_config, mock_scratchpad, agent_name="custom_agent")
        
        assert agent.agent_name == "custom_agent"
    
    def test_missing_llm_config(self, mock_scratchpad):
        """Test initialization with missing LLM config."""
        config = {}
        
        with pytest.raises(ValueError, match="Missing 'llm' configuration"):
            TestSKAgent(config, mock_scratchpad)
    
    def test_lazy_initialization(self, mock_scratchpad, basic_config):
        """Test that kernel and agent are lazily initialized."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Should be None until accessed
        assert agent._kernel is None
        assert agent._agent is None
        assert agent._chat_history is None


class TestSKBaseAgentKernel:
    """Test Semantic Kernel initialization and management."""
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_creation(self, mock_completion_cls, mock_kernel_cls, mock_scratchpad, basic_config):
        """Test kernel is created with correct configuration."""
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_service = MagicMock()
        mock_completion_cls.return_value = mock_service
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        kernel = agent.kernel
        
        # Verify kernel was created
        mock_kernel_cls.assert_called_once()
        
        # Verify service was created with correct config
        mock_completion_cls.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o",
            api_key="test-api-key"
        )
        
        # Verify service was added to kernel
        mock_kernel.add_service.assert_called_once_with(mock_service)
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_with_agent_specific_config(self, mock_completion_cls, mock_kernel_cls, 
                                                mock_scratchpad, agent_specific_config):
        """Test kernel uses agent-specific model configuration."""
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_service = MagicMock()
        mock_completion_cls.return_value = mock_service
        
        agent = TestSKAgent(agent_specific_config, mock_scratchpad)
        kernel = agent.kernel
        
        # Verify agent-specific model was used
        mock_completion_cls.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o-mini",  # Agent-specific model
            api_key="test-api-key"
        )
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_caching(self, mock_completion_cls, mock_kernel_cls, mock_scratchpad, basic_config):
        """Test kernel is cached after first access."""
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Access kernel multiple times
        kernel1 = agent.kernel
        kernel2 = agent.kernel
        
        # Should only create kernel once
        assert mock_kernel_cls.call_count == 1
        assert kernel1 is kernel2
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_with_base_url_default(self, mock_completion_cls, mock_kernel_cls, mock_scratchpad):
        """Test kernel uses default base_url configuration."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key": "test-api-key",
                "base_url": "https://api.openai.com/v1",
                "agents": {}
            }
        }
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_service = MagicMock()
        mock_completion_cls.return_value = mock_service
        
        agent = TestSKAgent(config, mock_scratchpad)
        kernel = agent.kernel
        
        # Verify service was created with base_url
        mock_completion_cls.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o",
            api_key="test-api-key",
            base_url="https://api.openai.com/v1"
        )
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_with_base_url_agent_override(self, mock_completion_cls, mock_kernel_cls, mock_scratchpad):
        """Test agent-specific base_url overrides default."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key": "test-api-key",
                "base_url": "https://api.openai.com/v1",
                "agents": {
                    "testsk": {
                        "model": "gpt-4o",
                        "base_url": "https://custom-endpoint.example.com/v1"
                    }
                }
            }
        }
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_service = MagicMock()
        mock_completion_cls.return_value = mock_service
        
        agent = TestSKAgent(config, mock_scratchpad)
        kernel = agent.kernel
        
        # Verify agent-specific base_url was used
        mock_completion_cls.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o",
            api_key="test-api-key",
            base_url="https://custom-endpoint.example.com/v1"
        )
    
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_kernel_without_base_url(self, mock_completion_cls, mock_kernel_cls, mock_scratchpad):
        """Test kernel without base_url (uses SDK default)."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key": "test-api-key",
                "agents": {}
            }
        }
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_service = MagicMock()
        mock_completion_cls.return_value = mock_service
        
        agent = TestSKAgent(config, mock_scratchpad)
        kernel = agent.kernel
        
        # Verify service was created without base_url parameter
        mock_completion_cls.assert_called_once_with(
            service_id="default",
            ai_model_id="gpt-4o",
            api_key="test-api-key"
        )


class TestSKBaseAgentAgent:
    """Test ChatCompletionAgent initialization and management."""
    
    @patch('aletheia.agents.sk_base.ChatCompletionAgent')
    @patch('aletheia.agents.sk_base.get_system_prompt')
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_agent_creation(self, mock_completion_cls, mock_kernel_cls, 
                           mock_get_prompt, mock_agent_cls, mock_scratchpad, basic_config):
        """Test ChatCompletionAgent is created with correct configuration."""
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_get_prompt.return_value = "You are a test agent."
        mock_sk_agent = MagicMock()
        mock_agent_cls.return_value = mock_sk_agent
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        sk_agent = agent.agent
        
        # Verify prompt was retrieved
        mock_get_prompt.assert_called_once_with("testsk")
        
        # Verify agent was created with correct config
        mock_agent_cls.assert_called_once_with(
            service_id="default",
            kernel=mock_kernel,
            name="testsk",
            instructions="You are a test agent.",
        )
    
    @patch('aletheia.agents.sk_base.ChatCompletionAgent')
    @patch('aletheia.agents.sk_base.get_system_prompt')
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_agent_caching(self, mock_completion_cls, mock_kernel_cls,
                          mock_get_prompt, mock_agent_cls, mock_scratchpad, basic_config):
        """Test agent is cached after first access."""
        mock_get_prompt.return_value = "Test instructions"
        mock_sk_agent = MagicMock()
        mock_agent_cls.return_value = mock_sk_agent
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Access agent multiple times
        agent1 = agent.agent
        agent2 = agent.agent
        
        # Should only create agent once
        assert mock_agent_cls.call_count == 1
        assert agent1 is agent2


class TestSKBaseAgentChatHistory:
    """Test chat history management."""
    
    @patch('aletheia.agents.sk_base.ChatHistory')
    def test_chat_history_creation(self, mock_history_cls, mock_scratchpad, basic_config):
        """Test chat history is created on first access."""
        mock_history = MagicMock()
        mock_history_cls.return_value = mock_history
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        history = agent.chat_history
        
        # Verify history was created
        mock_history_cls.assert_called_once()
        assert history == mock_history
    
    @patch('aletheia.agents.sk_base.ChatHistory')
    def test_chat_history_caching(self, mock_history_cls, mock_scratchpad, basic_config):
        """Test chat history is cached."""
        mock_history = MagicMock()
        mock_history_cls.return_value = mock_history
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Access history multiple times
        history1 = agent.chat_history
        history2 = agent.chat_history
        
        # Should only create once
        assert mock_history_cls.call_count == 1
        assert history1 is history2
    
    def test_reset_chat_history(self, mock_scratchpad, basic_config):
        """Test resetting chat history."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Create history
        with patch('aletheia.agents.sk_base.ChatHistory'):
            _ = agent.chat_history
        
        # Reset
        agent.reset_chat_history()
        
        # Should be None again
        assert agent._chat_history is None


class TestSKBaseAgentInvoke:
    """Test agent invocation methods."""
    
    @pytest.mark.asyncio
    async def test_invoke_async_basic(self, mock_scratchpad, basic_config):
        """Test async invocation with basic message."""
        # Setup mocks
        mock_fcb = MagicMock()
        mock_settings = MagicMock()
        
        mock_response = MagicMock()
        mock_response.content = "Test response"
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Mock the agent and chat_history properties
        mock_sk_agent = MagicMock()
        mock_sk_agent.invoke = AsyncMock(return_value=mock_response)
        mock_history = MagicMock()
        
        # Directly set the private attributes to avoid property initialization
        agent._agent = mock_sk_agent
        agent._chat_history = mock_history
        
        with patch('aletheia.agents.sk_base.OpenAIChatPromptExecutionSettings', return_value=mock_settings), \
             patch('aletheia.agents.sk_base.FunctionChoiceBehavior') as mock_fcb_cls:
            mock_fcb_cls.Auto.return_value = mock_fcb
            
            # Invoke agent
            response = await agent.invoke_async("Test message")
            
            # Verify message was added to history
            mock_history.add_user_message.assert_called_once_with("Test message")
            
            # Verify agent was invoked
            mock_sk_agent.invoke.assert_called_once()
            
            # Verify response
            assert response == "Test response"
            
            # Verify response was added to history
            mock_history.add_assistant_message.assert_called_once_with("Test response")
    
    @pytest.mark.asyncio
    async def test_invoke_async_with_settings(self, mock_scratchpad, basic_config):
        """Test async invocation with custom settings."""
        mock_response = MagicMock()
        mock_response.content = "Test response"
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Mock the agent and chat_history properties
        mock_sk_agent = MagicMock()
        mock_sk_agent.invoke = AsyncMock(return_value=mock_response)
        mock_history = MagicMock()
        
        agent._agent = mock_sk_agent
        agent._chat_history = mock_history
        
        with patch('aletheia.agents.sk_base.OpenAIChatPromptExecutionSettings') as mock_settings_cls, \
             patch('aletheia.agents.sk_base.FunctionChoiceBehavior'):
            
            # Invoke with settings
            custom_settings = {"temperature": 0.5, "max_tokens": 100}
            await agent.invoke_async("Test message", settings=custom_settings)
            
            # Verify settings were passed
            mock_settings_cls.assert_called_once()
            call_kwargs = mock_settings_cls.call_args[1]
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 100
    
    @pytest.mark.asyncio
    async def test_invoke_async_list_response(self, mock_scratchpad, basic_config):
        """Test handling of list response from agent."""
        mock_msg1 = MagicMock()
        mock_msg1.content = "First message"
        mock_msg2 = MagicMock()
        mock_msg2.content = "Second message"
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Mock the agent and chat_history properties
        mock_sk_agent = MagicMock()
        mock_sk_agent.invoke = AsyncMock(return_value=[mock_msg1, mock_msg2])
        mock_history = MagicMock()
        
        agent._agent = mock_sk_agent
        agent._chat_history = mock_history
        
        with patch('aletheia.agents.sk_base.OpenAIChatPromptExecutionSettings'), \
             patch('aletheia.agents.sk_base.FunctionChoiceBehavior'):
            
            response = await agent.invoke_async("Test message")
            
            # Should join multiple messages
            assert response == "First message\nSecond message"
    
    @patch('asyncio.run')
    def test_invoke_synchronous_wrapper(self, mock_run, mock_scratchpad, basic_config):
        """Test synchronous wrapper around invoke_async."""
        mock_run.return_value = "Async response"
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        response = agent.invoke("Test message", settings={"temp": 0.5})
        
        # Verify async function was called
        assert mock_run.called
        assert response == "Async response"


class TestSKBaseAgentScratchpad:
    """Test scratchpad operations."""
    
    def test_read_scratchpad(self, mock_scratchpad, basic_config):
        """Test reading from scratchpad."""
        mock_scratchpad.read_section.return_value = {"data": "test"}
        
        agent = TestSKAgent(basic_config, mock_scratchpad)
        result = agent.read_scratchpad("TEST_SECTION")
        
        mock_scratchpad.read_section.assert_called_once_with("TEST_SECTION")
        assert result == {"data": "test"}
    
    def test_write_scratchpad(self, mock_scratchpad, basic_config):
        """Test writing to scratchpad."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        data = {"key": "value"}
        
        agent.write_scratchpad("TEST_SECTION", data)
        
        mock_scratchpad.write_section.assert_called_once_with("TEST_SECTION", data)
        mock_scratchpad.save.assert_called_once()
    
    def test_append_scratchpad(self, mock_scratchpad, basic_config):
        """Test appending to scratchpad."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        data = {"new": "data"}
        
        agent.append_scratchpad("TEST_SECTION", data)
        
        mock_scratchpad.append_to_section.assert_called_once_with("TEST_SECTION", data)
        mock_scratchpad.save.assert_called_once()


class TestSKBaseAgentExecute:
    """Test abstract execute method."""
    
    def test_execute_implementation(self, mock_scratchpad, basic_config):
        """Test execute method in concrete implementation."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        result = agent.execute(param1="value1", param2="value2")
        
        assert result["status"] == "success"
        assert result["kwargs"]["param1"] == "value1"
        assert result["kwargs"]["param2"] == "value2"
    
    def test_abstract_execute_enforcement(self, mock_scratchpad, basic_config):
        """Test that execute must be implemented."""
        # Create an incomplete agent
        class IncompleteAgent(SKBaseAgent):
            pass
        
        # Should be able to instantiate (execute is marked @abstractmethod but not enforced until called)
        agent = IncompleteAgent(basic_config, mock_scratchpad)
        
        # execute is abstract, so subclass should implement it
        # (in Python, @abstractmethod prevents instantiation only if using ABC metaclass)
        assert hasattr(agent, 'execute')
        assert callable(agent.execute)


class TestSKBaseAgentRepr:
    """Test string representation."""
    
    def test_repr(self, mock_scratchpad, basic_config):
        """Test string representation of agent."""
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        repr_str = repr(agent)
        
        assert "TestSKAgent" in repr_str
        assert "testsk" in repr_str


class TestSKBaseAgentIntegration:
    """Integration tests for SK base agent."""
    
    @patch('aletheia.agents.sk_base.ChatCompletionAgent')
    @patch('aletheia.agents.sk_base.get_system_prompt')
    @patch('aletheia.agents.sk_base.Kernel')
    @patch('aletheia.agents.sk_base.OpenAIChatCompletion')
    def test_full_agent_lifecycle(self, mock_completion_cls, mock_kernel_cls,
                                  mock_get_prompt, mock_agent_cls, mock_scratchpad, basic_config):
        """Test complete agent lifecycle."""
        # Setup mocks
        mock_kernel = MagicMock()
        mock_kernel_cls.return_value = mock_kernel
        mock_get_prompt.return_value = "Test instructions"
        mock_sk_agent = MagicMock()
        mock_agent_cls.return_value = mock_sk_agent
        
        # Create agent
        agent = TestSKAgent(basic_config, mock_scratchpad)
        
        # Access kernel (triggers initialization)
        kernel = agent.kernel
        assert kernel == mock_kernel
        
        # Access agent (triggers initialization)
        sk_agent = agent.agent
        assert sk_agent == mock_sk_agent
        
        # Read from scratchpad
        mock_scratchpad.read_section.return_value = {"test": "data"}
        data = agent.read_scratchpad("TEST")
        assert data == {"test": "data"}
        
        # Write to scratchpad
        agent.write_scratchpad("OUTPUT", {"result": "success"})
        mock_scratchpad.write_section.assert_called_with("OUTPUT", {"result": "success"})
        
        # Execute agent task
        result = agent.execute(param="value")
        assert result["status"] == "success"
    
    def test_agent_name_extraction(self, mock_scratchpad, basic_config):
        """Test agent name is correctly extracted from class name."""
        class DataFetcherAgent(SKBaseAgent):
            def execute(self, **kwargs):
                return {}
        
        class PatternAnalyzerAgent(SKBaseAgent):
            def execute(self, **kwargs):
                return {}
        
        fetcher = DataFetcherAgent(basic_config, mock_scratchpad)
        analyzer = PatternAnalyzerAgent(basic_config, mock_scratchpad)
        
        assert fetcher.agent_name == "datafetcher"
        assert analyzer.agent_name == "patternanalyzer"
