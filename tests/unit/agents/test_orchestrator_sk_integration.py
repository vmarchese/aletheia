"""Unit tests for OrchestratorAgent SK orchestration integration."""

import os
import pytest
from unittest.mock import Mock, patch

from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.scratchpad import Scratchpad


@pytest.fixture
def mock_scratchpad():
    """Create a mock scratchpad."""
    scratchpad = Mock(spec=Scratchpad)
    scratchpad.write_section = Mock()
    scratchpad.read_section = Mock(return_value={})
    return scratchpad


@pytest.fixture
def config_with_sk_orchestration():
    """Create config with SK orchestration enabled."""
    return {
        "llm": {"default_model": "gpt-4o", "api_key": "test-key"},
        "ui": {"confirmation_level": "normal", "agent_visibility": True},
        "orchestration": {"use_semantic_kernel": True}
    }


@pytest.fixture
def config_without_sk_orchestration():
    """Create config without SK orchestration."""
    return {
        "llm": {"default_model": "gpt-4o", "api_key": "test-key"},
        "ui": {"confirmation_level": "normal", "agent_visibility": False},
        "orchestration": {"use_semantic_kernel": False}
    }


class TestOrchestratorSKIntegration:
    """Tests for OrchestratorAgent SK orchestration integration."""
    
    def test_sk_orchestration_disabled_by_default(self, mock_scratchpad):
        """Test SK orchestration is disabled by default."""
        config = {
            "llm": {"default_model": "gpt-4o"},
            "ui": {}
        }
        
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        
        assert orchestrator.use_sk_orchestration is False
        assert orchestrator.sk_orchestration is None
    
    def test_sk_orchestration_enabled_via_config(self, config_with_sk_orchestration, mock_scratchpad):
        """Test SK orchestration can be enabled via config."""
        with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
            orchestrator = OrchestratorAgent(config_with_sk_orchestration, mock_scratchpad)
            
            assert orchestrator.use_sk_orchestration is True
    
    def test_sk_orchestration_disabled_via_config(self, config_without_sk_orchestration, mock_scratchpad):
        """Test SK orchestration can be disabled via config."""
        orchestrator = OrchestratorAgent(config_without_sk_orchestration, mock_scratchpad)
        
        assert orchestrator.use_sk_orchestration is False
    
    def test_sk_orchestration_enabled_via_env_var_true(self, mock_scratchpad):
        """Test SK orchestration enabled via environment variable."""
        config = {"llm": {}, "ui": {}}
        
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'true'}):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config, mock_scratchpad)
                
                assert orchestrator.use_sk_orchestration is True
    
    def test_sk_orchestration_enabled_via_env_var_1(self, mock_scratchpad):
        """Test SK orchestration enabled via environment variable (1)."""
        config = {"llm": {}, "ui": {}}
        
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': '1'}):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config, mock_scratchpad)
                
                assert orchestrator.use_sk_orchestration is True
    
    def test_sk_orchestration_enabled_via_env_var_yes(self, mock_scratchpad):
        """Test SK orchestration enabled via environment variable (yes)."""
        config = {"llm": {}, "ui": {}}
        
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'yes'}):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config, mock_scratchpad)
                
                assert orchestrator.use_sk_orchestration is True
    
    def test_sk_orchestration_disabled_via_env_var_false(self, config_with_sk_orchestration, mock_scratchpad):
        """Test SK orchestration disabled via environment variable overrides config."""
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'false'}):
            orchestrator = OrchestratorAgent(config_with_sk_orchestration, mock_scratchpad)
            
            # Env var should override config
            assert orchestrator.use_sk_orchestration is False
    
    def test_sk_orchestration_disabled_via_env_var_0(self, config_with_sk_orchestration, mock_scratchpad):
        """Test SK orchestration disabled via environment variable (0)."""
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': '0'}):
            orchestrator = OrchestratorAgent(config_with_sk_orchestration, mock_scratchpad)
            
            assert orchestrator.use_sk_orchestration is False
    
    def test_sk_orchestration_disabled_via_env_var_no(self, config_with_sk_orchestration, mock_scratchpad):
        """Test SK orchestration disabled via environment variable (no)."""
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'no'}):
            orchestrator = OrchestratorAgent(config_with_sk_orchestration, mock_scratchpad)
            
            assert orchestrator.use_sk_orchestration is False
    
    def test_sk_orchestration_unavailable(self, config_with_sk_orchestration, mock_scratchpad):
        """Test SK orchestration disabled when not available."""
        with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', False):
            orchestrator = OrchestratorAgent(config_with_sk_orchestration, mock_scratchpad)
            
            # Even if config says True, should be False if not available
            assert orchestrator.use_sk_orchestration is False
    
    def test_env_var_precedence_over_config(self, config_without_sk_orchestration, mock_scratchpad):
        """Test environment variable takes precedence over config."""
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'true'}):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config_without_sk_orchestration, mock_scratchpad)
                
                # Env var should override config
                assert orchestrator.use_sk_orchestration is True
    
    def test_initialization_with_custom_name(self, mock_scratchpad):
        """Test orchestrator initialization with custom name."""
        config = {"llm": {}, "ui": {}}
        
        orchestrator = OrchestratorAgent(config, mock_scratchpad, agent_name="custom_orchestrator")
        
        assert orchestrator.agent_name == "custom_orchestrator"
        assert orchestrator.use_sk_orchestration is False
    
    def test_confirmation_level_from_config(self, mock_scratchpad):
        """Test confirmation level is read from config."""
        config = {
            "llm": {},
            "ui": {"confirmation_level": "verbose"}
        }
        
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        
        assert orchestrator.confirmation_level == "verbose"
    
    def test_agent_visibility_from_config(self, mock_scratchpad):
        """Test agent visibility is read from config."""
        config = {
            "llm": {},
            "ui": {"agent_visibility": True}
        }
        
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        
        assert orchestrator.agent_visibility is True
    
    def test_default_ui_settings(self, mock_scratchpad):
        """Test default UI settings when not in config."""
        config = {"llm": {}}
        
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        
        assert orchestrator.confirmation_level == "normal"
        assert orchestrator.agent_visibility is False


class TestShouldUseSKOrchestration:
    """Tests for _should_use_sk_orchestration method."""
    
    def test_env_var_true(self, mock_scratchpad):
        """Test environment variable true."""
        config = {"llm": {}}
        
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'true'}):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config, mock_scratchpad)
                result = orchestrator._should_use_sk_orchestration(config)
                
                assert result is True
    
    def test_env_var_false(self, mock_scratchpad):
        """Test environment variable false."""
        config = {"llm": {}, "orchestration": {"use_semantic_kernel": True}}
        
        with patch.dict(os.environ, {'USE_SK_ORCHESTRATION': 'false'}):
            orchestrator = OrchestratorAgent(config, mock_scratchpad)
            result = orchestrator._should_use_sk_orchestration(config)
            
            assert result is False
    
    def test_config_true_no_env(self, mock_scratchpad):
        """Test config true with no environment variable."""
        config = {"llm": {}, "orchestration": {"use_semantic_kernel": True}}
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('aletheia.agents.orchestrator.SK_ORCHESTRATION_AVAILABLE', True):
                orchestrator = OrchestratorAgent(config, mock_scratchpad)
                result = orchestrator._should_use_sk_orchestration(config)
                
                assert result is True
    
    def test_config_false_no_env(self, mock_scratchpad):
        """Test config false with no environment variable."""
        config = {"llm": {}, "orchestration": {"use_semantic_kernel": False}}
        
        with patch.dict(os.environ, {}, clear=True):
            orchestrator = OrchestratorAgent(config, mock_scratchpad)
            result = orchestrator._should_use_sk_orchestration(config)
            
            assert result is False
    
    def test_default_false_no_env_no_config(self, mock_scratchpad):
        """Test default false when no env var or config."""
        config = {"llm": {}}
        
        with patch.dict(os.environ, {}, clear=True):
            orchestrator = OrchestratorAgent(config, mock_scratchpad)
            result = orchestrator._should_use_sk_orchestration(config)
            
            assert result is False
