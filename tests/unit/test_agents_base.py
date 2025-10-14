"""Unit tests for aletheia.agents.base module."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from aletheia.agents.base import BaseAgent
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.llm.provider import LLMProvider


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""
    
    def execute(self, **kwargs):
        """Simple execute implementation."""
        return {"status": "success", "data": kwargs}


class TestBaseAgent:
    """Tests for BaseAgent class."""
    
    def test_initialization(self, tmp_path):
        """Test agent initialization with valid config."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY"
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad)
        
        assert agent.config == config
        assert agent.scratchpad == scratchpad
        assert agent.agent_name == "concrete"
    
    def test_initialization_with_custom_name(self, tmp_path):
        """Test agent initialization with custom agent name."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad, agent_name="custom_agent")
        
        assert agent.agent_name == "custom_agent"
    
    def test_initialization_missing_llm_config(self, tmp_path):
        """Test agent initialization fails without LLM config."""
        config = {}
        scratchpad = MagicMock(spec=Scratchpad)
        
        with pytest.raises(ValueError, match="Missing 'llm' configuration"):
            ConcreteAgent(config, scratchpad)
    
    def test_read_scratchpad(self, tmp_path):
        """Test reading from scratchpad."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        scratchpad.read_section.return_value = {"test": "data"}
        
        agent = ConcreteAgent(config, scratchpad)
        result = agent.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
        
        assert result == {"test": "data"}
        scratchpad.read_section.assert_called_once_with(ScratchpadSection.PROBLEM_DESCRIPTION)
    
    def test_write_scratchpad(self, tmp_path):
        """Test writing to scratchpad."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad)
        data = {"test": "data"}
        agent.write_scratchpad(ScratchpadSection.DATA_COLLECTED, data)
        
        scratchpad.write_section.assert_called_once_with(ScratchpadSection.DATA_COLLECTED, data)
        scratchpad.save.assert_called_once()
    
    def test_append_scratchpad(self, tmp_path):
        """Test appending to scratchpad."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad)
        data = {"new": "entry"}
        agent.append_scratchpad(ScratchpadSection.PATTERN_ANALYSIS, data)
        
        scratchpad.append_to_section.assert_called_once_with(
            ScratchpadSection.PATTERN_ANALYSIS, data
        )
        scratchpad.save.assert_called_once()
    
    def test_get_llm_default_config(self, tmp_path):
        """Test getting LLM provider with default config."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY"
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("aletheia.agents.base.LLMFactory.create_provider") as mock_create:
                mock_provider = MagicMock(spec=LLMProvider)
                mock_create.return_value = mock_provider
                
                agent = ConcreteAgent(config, scratchpad)
                provider = agent.get_llm()
                
                assert provider == mock_provider
                mock_create.assert_called_once_with({
                    "model": "gpt-4o",
                    "api_key_env": "OPENAI_API_KEY"
                })
    
    def test_get_llm_agent_specific_config(self, tmp_path):
        """Test getting LLM provider with agent-specific config."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY",
                "agents": {
                    "concrete": {
                        "model": "gpt-4o-mini",
                        "timeout": 30
                    }
                }
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("aletheia.agents.base.LLMFactory.create_provider") as mock_create:
                mock_provider = MagicMock(spec=LLMProvider)
                mock_create.return_value = mock_provider
                
                agent = ConcreteAgent(config, scratchpad)
                provider = agent.get_llm()
                
                assert provider == mock_provider
                mock_create.assert_called_once_with({
                    "model": "gpt-4o-mini",
                    "api_key_env": "OPENAI_API_KEY",
                    "timeout": 30
                })
    
    def test_get_llm_with_base_url(self, tmp_path):
        """Test getting LLM provider with custom base URL."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY",
                "agents": {
                    "concrete": {
                        "model": "gpt-4o",
                        "base_url": "https://custom.openai.com"
                    }
                }
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("aletheia.agents.base.LLMFactory.create_provider") as mock_create:
                mock_provider = MagicMock(spec=LLMProvider)
                mock_create.return_value = mock_provider
                
                agent = ConcreteAgent(config, scratchpad)
                provider = agent.get_llm()
                
                mock_create.assert_called_once_with({
                    "model": "gpt-4o",
                    "api_key_env": "OPENAI_API_KEY",
                    "base_url": "https://custom.openai.com"
                })
    
    def test_get_llm_caching(self, tmp_path):
        """Test that LLM provider is cached after first access."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY"
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("aletheia.agents.base.LLMFactory.create_provider") as mock_create:
                mock_provider = MagicMock(spec=LLMProvider)
                mock_create.return_value = mock_provider
                
                agent = ConcreteAgent(config, scratchpad)
                provider1 = agent.get_llm()
                provider2 = agent.get_llm()
                
                assert provider1 == provider2
                mock_create.assert_called_once()  # Only called once
    
    def test_execute_abstract_method(self, tmp_path):
        """Test that execute must be implemented by subclass."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        # Cannot instantiate BaseAgent directly
        with pytest.raises(TypeError):
            BaseAgent(config, scratchpad)
    
    def test_execute_implementation(self, tmp_path):
        """Test concrete execute implementation."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad)
        result = agent.execute(test_param="value")
        
        assert result["status"] == "success"
        assert result["data"]["test_param"] == "value"
    
    def test_repr(self, tmp_path):
        """Test string representation."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        agent = ConcreteAgent(config, scratchpad)
        
        assert repr(agent) == "ConcreteAgent(agent_name='concrete')"
    
    def test_agent_name_extraction(self, tmp_path):
        """Test agent name extraction from class name."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = MagicMock(spec=Scratchpad)
        
        class DataFetcherAgent(BaseAgent):
            def execute(self, **kwargs):
                return {}
        
        agent = DataFetcherAgent(config, scratchpad)
        assert agent.agent_name == "datafetcher"
    
    def test_get_llm_with_explicit_api_key(self, tmp_path):
        """Test getting LLM provider with explicit API key in config."""
        config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key": "explicit-key-123",
                "api_key_env": "OPENAI_API_KEY"
            }
        }
        scratchpad = MagicMock(spec=Scratchpad)
        
        with patch("aletheia.agents.base.LLMFactory.create_provider") as mock_create:
            mock_provider = MagicMock(spec=LLMProvider)
            mock_create.return_value = mock_provider
            
            agent = ConcreteAgent(config, scratchpad)
            provider = agent.get_llm()
            
            # Should pass explicit api_key to factory
            call_args = mock_create.call_args[0][0]
            assert call_args["api_key"] == "explicit-key-123"
