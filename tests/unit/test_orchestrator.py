"""Unit tests for the Orchestrator Agent.

Tests cover:
- Session initialization
- Agent routing
- Error handling and recovery
- User interaction flow
- Guided mode workflow
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from aletheia.agents.orchestrator import OrchestratorAgent, InvestigationPhase
from aletheia.scratchpad import Scratchpad, ScratchpadSection


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
def config():
    """Create test configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
            "agents": {
                "orchestrator": {
                    "model": "gpt-4o"
                }
            }
        },
        "ui": {
            "confirmation_level": "normal",
            "agent_visibility": False
        }
    }


@pytest.fixture
def orchestrator(config, mock_scratchpad):
    """Create orchestrator instance."""
    return OrchestratorAgent(config, mock_scratchpad)


class TestOrchestratorInitialization:
    """Test orchestrator initialization."""
    
    def test_init_basic(self, config, mock_scratchpad):
        """Test basic initialization."""
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        
        assert orchestrator.config == config
        assert orchestrator.scratchpad == mock_scratchpad
        assert orchestrator.agent_name == "orchestrator"
        assert orchestrator.current_phase == InvestigationPhase.INITIALIZATION
        assert orchestrator.agent_registry == {}
    
    def test_init_with_custom_name(self, config, mock_scratchpad):
        """Test initialization with custom agent name."""
        orchestrator = OrchestratorAgent(config, mock_scratchpad, agent_name="custom")
        assert orchestrator.agent_name == "custom"
    
    def test_init_ui_config(self, config, mock_scratchpad):
        """Test UI configuration extraction."""
        orchestrator = OrchestratorAgent(config, mock_scratchpad)
        assert orchestrator.confirmation_level == "normal"
        assert orchestrator.agent_visibility is False
    
    def test_init_missing_llm_config(self, mock_scratchpad):
        """Test initialization with missing LLM config."""
        config = {}
        with pytest.raises(ValueError, match="Missing 'llm' configuration"):
            OrchestratorAgent(config, mock_scratchpad)


class TestAgentRegistration:
    """Test agent registration."""
    
    def test_register_agent(self, orchestrator):
        """Test registering an agent."""
        mock_agent = Mock()
        orchestrator.register_agent("test_agent", mock_agent)
        
        assert "test_agent" in orchestrator.agent_registry
        assert orchestrator.agent_registry["test_agent"] == mock_agent
    
    def test_register_multiple_agents(self, orchestrator):
        """Test registering multiple agents."""
        agent1 = Mock()
        agent2 = Mock()
        
        orchestrator.register_agent("agent1", agent1)
        orchestrator.register_agent("agent2", agent2)
        
        assert len(orchestrator.agent_registry) == 2
        assert orchestrator.agent_registry["agent1"] == agent1
        assert orchestrator.agent_registry["agent2"] == agent2


class TestSessionStart:
    """Test session initialization."""
    
    def test_start_session_with_params(self, orchestrator):
        """Test session start with provided parameters."""
        result = orchestrator.start_session(
            problem_description="API errors",
            time_window="2h",
            affected_services=["payments-svc"],
            mode="guided"
        )
        
        assert result["problem_description"] == "API errors"
        assert result["time_window"] == "2h"
        assert result["affected_services"] == ["payments-svc"]
        
        # Verify scratchpad was updated
        orchestrator.scratchpad.write_section.assert_called_once()
        call_args = orchestrator.scratchpad.write_section.call_args
        assert call_args[0][0] == ScratchpadSection.PROBLEM_DESCRIPTION
        
        problem_data = call_args[0][1]
        assert problem_data["description"] == "API errors"
        assert problem_data["time_window"] == "2h"
        assert problem_data["affected_services"] == ["payments-svc"]
        assert problem_data["interaction_mode"] == "guided"
        assert "started_at" in problem_data
        
        # Verify phase transition
        assert orchestrator.current_phase == InvestigationPhase.DATA_COLLECTION
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_start_session_interactive(self, mock_ask, orchestrator):
        """Test session start with interactive prompts."""
        # Mock user inputs
        mock_ask.side_effect = [
            "API 500 errors",  # problem description
            "payments-svc, checkout-svc"  # services
        ]
        
        with patch.object(orchestrator, '_display_menu', return_value="Last 30 minutes"):
            result = orchestrator.start_session()
        
        assert result["problem_description"] == "API 500 errors"
        assert result["time_window"] == "30m"
        assert result["affected_services"] == ["payments-svc", "checkout-svc"]


class TestAgentRouting:
    """Test agent routing."""
    
    def test_route_to_agent_success(self, orchestrator):
        """Test successful routing to agent."""
        mock_agent = Mock()
        mock_agent.execute = Mock(return_value={"status": "success"})
        mock_agent.__class__.__name__ = "TestAgent"
        
        orchestrator.register_agent("test_agent", mock_agent)
        
        result = orchestrator.route_to_agent("test_agent", param1="value1")
        
        assert result["success"] is True
        assert result["result"]["status"] == "success"
        mock_agent.execute.assert_called_once_with(param1="value1")
    
    def test_route_to_unregistered_agent(self, orchestrator):
        """Test routing to unregistered agent."""
        with pytest.raises(ValueError, match="Agent 'unknown' not registered"):
            orchestrator.route_to_agent("unknown")
    
    def test_route_to_agent_with_error(self, orchestrator):
        """Test routing when agent raises error."""
        mock_agent = Mock()
        mock_agent.execute = Mock(side_effect=ValueError("Test error"))
        mock_agent.__class__.__name__ = "TestAgent"
        
        orchestrator.register_agent("test_agent", mock_agent)
        
        with patch.object(orchestrator, 'handle_error') as mock_handle_error:
            mock_handle_error.return_value = {"success": False, "error": "Test error"}
            result = orchestrator.route_to_agent("test_agent")
        
        assert result["success"] is False
        mock_handle_error.assert_called_once()
    
    def test_route_with_agent_visibility(self, orchestrator):
        """Test routing with agent visibility enabled."""
        orchestrator.agent_visibility = True
        
        mock_agent = Mock()
        mock_agent.execute = Mock(return_value={"status": "success"})
        mock_agent.__class__.__name__ = "TestAgent"
        
        orchestrator.register_agent("test_agent", mock_agent)
        
        with patch.object(orchestrator.console, 'print') as mock_print:
            orchestrator.route_to_agent("test_agent")
            mock_print.assert_called()


class TestErrorHandling:
    """Test error handling and recovery."""
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_handle_error_with_retry(self, mock_ask, orchestrator):
        """Test error handling with retry option."""
        error = ConnectionError("Connection failed")
        
        # Mock recovery action selection
        with patch.object(orchestrator, '_display_menu', return_value="Retry"):
            with patch.object(orchestrator, '_retry_agent') as mock_retry:
                mock_retry.return_value = {"success": True}
                result = orchestrator.handle_error("test_agent", error)
        
        assert result["success"] is True
        mock_retry.assert_called_once_with("test_agent")
    
    def test_handle_error_with_skip(self, orchestrator):
        """Test error handling with skip option."""
        error = ValueError("Test error")
        
        with patch.object(orchestrator, '_display_menu', return_value="Skip this step"):
            result = orchestrator.handle_error("test_agent", error)
        
        assert result["success"] is False
        assert result["skipped"] is True
        assert "error" in result
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_handle_error_with_manual_intervention(self, mock_ask, orchestrator):
        """Test error handling with manual intervention."""
        error = ValueError("Test error")
        
        with patch.object(orchestrator, '_display_menu', return_value="Manual intervention"):
            result = orchestrator.handle_error("test_agent", error)
        
        assert result["success"] is True
        assert result.get("manual") is True
        mock_ask.assert_called()
    
    def test_handle_error_with_abort(self, orchestrator):
        """Test error handling with abort."""
        error = ValueError("Test error")
        
        with patch.object(orchestrator, '_display_menu', return_value="Abort investigation"):
            with pytest.raises(ValueError, match="Test error"):
                orchestrator.handle_error("test_agent", error)
    
    def test_is_retryable_error(self, orchestrator):
        """Test retryable error detection."""
        assert orchestrator._is_retryable_error(ConnectionError()) is True
        assert orchestrator._is_retryable_error(TimeoutError()) is True
        assert orchestrator._is_retryable_error(ValueError()) is False


class TestUserInteraction:
    """Test user interaction."""
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_handle_user_interaction_text(self, mock_ask, orchestrator):
        """Test text input interaction."""
        mock_ask.return_value = "user input"
        result = orchestrator.handle_user_interaction("Enter value")
        
        assert result == "user input"
        mock_ask.assert_called_once_with("Enter value", default=None)
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_handle_user_interaction_menu(self, mock_ask, orchestrator):
        """Test menu interaction."""
        mock_ask.return_value = "1"
        
        with patch.object(orchestrator, '_display_menu', return_value="Choice 1"):
            result = orchestrator.handle_user_interaction(
                "Select option",
                choices=["Choice 1", "Choice 2"]
            )
        
        assert result == "Choice 1"
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_display_menu(self, mock_ask, orchestrator):
        """Test menu display."""
        mock_ask.return_value = "2"
        
        choices = ["Option 1", "Option 2", "Option 3"]
        result = orchestrator._display_menu("Select", choices)
        
        assert result == "Option 2"
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_display_menu_invalid_then_valid(self, mock_ask, orchestrator):
        """Test menu with invalid input then valid."""
        mock_ask.side_effect = ["invalid", "0", "4", "2"]
        
        choices = ["Option 1", "Option 2", "Option 3"]
        result = orchestrator._display_menu("Select", choices)
        
        assert result == "Option 2"


class TestPresentFindings:
    """Test findings presentation."""
    
    def test_present_findings_success(self, orchestrator):
        """Test presenting findings with diagnosis."""
        diagnosis = {
            "root_cause": {
                "type": "nil_pointer_dereference",
                "confidence": 0.86,
                "description": "Nil pointer dereference in features.go"
            },
            "recommended_actions": [
                {"priority": "immediate", "action": "Rollback to v1.18"},
                {"priority": "high", "action": "Apply patch"}
            ]
        }
        
        orchestrator.scratchpad.read_section.return_value = diagnosis
        
        with patch.object(orchestrator.console, 'print'):
            result = orchestrator.present_findings()
        
        assert result == diagnosis
        orchestrator.scratchpad.read_section.assert_called_once_with(
            ScratchpadSection.FINAL_DIAGNOSIS
        )
    
    def test_present_findings_no_diagnosis(self, orchestrator):
        """Test presenting findings with no diagnosis."""
        orchestrator.scratchpad.read_section.return_value = None
        
        with patch.object(orchestrator.console, 'print'):
            result = orchestrator.present_findings()
        
        assert result == {}


class TestConfirmationLevels:
    """Test confirmation level handling."""
    
    @patch('aletheia.agents.orchestrator.Confirm.ask')
    def test_should_confirm_minimal(self, mock_confirm, orchestrator):
        """Test confirmation with minimal level."""
        orchestrator.confirmation_level = "minimal"
        
        result = orchestrator._should_confirm("Do something?")
        
        assert result is True
        mock_confirm.assert_not_called()
    
    @patch('aletheia.agents.orchestrator.Confirm.ask')
    def test_should_confirm_verbose(self, mock_confirm, orchestrator):
        """Test confirmation with verbose level."""
        orchestrator.confirmation_level = "verbose"
        mock_confirm.return_value = True
        
        result = orchestrator._should_confirm("Do something?")
        
        assert result is True
        mock_confirm.assert_called_once_with("Do something?", default=True)
    
    @patch('aletheia.agents.orchestrator.Confirm.ask')
    def test_should_confirm_normal_major_operation(self, mock_confirm, orchestrator):
        """Test confirmation with normal level for major operation."""
        orchestrator.confirmation_level = "normal"
        mock_confirm.return_value = True
        
        result = orchestrator._should_confirm("Collect data from sources?")
        
        assert result is True
        mock_confirm.assert_called_once()
    
    def test_should_confirm_normal_minor_operation(self, orchestrator):
        """Test confirmation with normal level for minor operation."""
        orchestrator.confirmation_level = "normal"
        
        result = orchestrator._should_confirm("Continue?")
        
        assert result is True


class TestGuidedModeExecution:
    """Test guided mode execution."""
    
    def test_execute_guided_mode_components(self, orchestrator):
        """Test guided mode execution components separately."""
        # Test that _execute_guided_mode exists and can be mocked
        assert hasattr(orchestrator, '_execute_guided_mode')
        
        # Mock the entire guided mode execution
        mock_result = {
            "status": "completed",
            "phase": InvestigationPhase.COMPLETED.value,
            "session_info": {"problem_description": "Test"},
            "findings": {}
        }
        
        with patch.object(orchestrator, '_execute_guided_mode', return_value=mock_result):
            result = orchestrator.execute(mode="guided")
        
        assert result["status"] == "completed"
        assert result["phase"] == InvestigationPhase.COMPLETED.value
    
    def test_execute_unsupported_mode(self, orchestrator):
        """Test execution with unsupported mode."""
        with pytest.raises(NotImplementedError, match="Mode 'conversational' not implemented"):
            orchestrator.execute(mode="conversational")


class TestPhaseRouting:
    """Test phase-specific routing."""
    
    @patch('aletheia.agents.orchestrator.Confirm.ask')
    def test_route_data_collection(self, mock_confirm, orchestrator):
        """Test data collection routing."""
        mock_confirm.return_value = True
        
        mock_agent = Mock()
        mock_agent.execute = Mock(return_value={})
        orchestrator.register_agent("data_fetcher", mock_agent)
        
        with patch.object(orchestrator, 'route_to_agent') as mock_route:
            mock_route.return_value = {"success": True}
            result = orchestrator._route_data_collection()
        
        assert result is True
        mock_route.assert_called_once_with("data_fetcher")
    
    def test_route_code_inspection_skip(self, orchestrator):
        """Test code inspection with skip option."""
        with patch.object(orchestrator, '_display_menu') as mock_menu:
            mock_menu.return_value = "Skip code inspection and proceed to diagnosis"
            result = orchestrator._route_code_inspection()
        
        assert result is True
    
    def test_route_root_cause_analysis(self, orchestrator):
        """Test root cause analysis routing."""
        mock_agent = Mock()
        mock_agent.execute = Mock(return_value={})
        orchestrator.register_agent("root_cause_analyst", mock_agent)
        
        with patch.object(orchestrator, 'route_to_agent') as mock_route:
            mock_route.return_value = {"success": True}
            result = orchestrator._route_root_cause_analysis()
        
        assert result is True


class TestPromptMethods:
    """Test prompt helper methods."""
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_prompt_problem_description(self, mock_ask, orchestrator):
        """Test problem description prompt."""
        mock_ask.return_value = "API errors in production"
        result = orchestrator._prompt_problem_description()
        
        assert result == "API errors in production"
    
    def test_prompt_time_window_preset(self, orchestrator):
        """Test time window prompt with preset choice."""
        with patch.object(orchestrator, '_display_menu', return_value="Last 2 hours"):
            result = orchestrator._prompt_time_window()
        
        assert result == "2h"
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_prompt_time_window_custom(self, mock_ask, orchestrator):
        """Test time window prompt with custom input."""
        mock_ask.return_value = "4h"
        
        with patch.object(orchestrator, '_display_menu', return_value="Custom"):
            result = orchestrator._prompt_time_window()
        
        assert result == "4h"
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_prompt_affected_services(self, mock_ask, orchestrator):
        """Test affected services prompt."""
        mock_ask.return_value = "service1, service2, service3"
        result = orchestrator._prompt_affected_services()
        
        assert result == ["service1", "service2", "service3"]
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_prompt_affected_services_empty(self, mock_ask, orchestrator):
        """Test affected services prompt with empty input."""
        mock_ask.return_value = ""
        result = orchestrator._prompt_affected_services()
        
        assert result == []

