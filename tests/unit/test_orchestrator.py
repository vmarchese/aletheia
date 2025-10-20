"""Unit tests for the Orchestrator Agent.

Tests cover:
- Session initialization
- Agent routing
- Error handling and recovery
- User interaction flow
- Guided mode workflow
- Conversational mode workflow
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from aletheia.agents.orchestrator import OrchestratorAgent, UserIntent
from aletheia.scratchpad import Scratchpad, ScratchpadSection


@pytest.fixture
def mock_scratchpad():
    """Create a mock scratchpad."""
    from pathlib import Path
    scratchpad = Mock(spec=Scratchpad)
    scratchpad.read_section = Mock(return_value=None)
    scratchpad.write_section = Mock()
    scratchpad.append_to_section = Mock()
    scratchpad.save = Mock()
    scratchpad.session_dir = Path("/tmp/test-session")
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
            affected_services=["payments-svc"]
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
        assert "started_at" in problem_data
    
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


class TestConversationalMode:
    """Test conversational mode implementation."""
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_understand_user_intent_fetch_data(self, mock_ask, orchestrator, mock_scratchpad):
        """Test intent understanding for data fetching."""
        mock_llm = Mock()
        intent_response = {
            "intent": "fetch_data",
            "confidence": 0.9,
            "parameters": {
                "services": ["payments-svc"],
                "time_window": "2h",
                "data_sources": ["kubernetes"],
                "keywords": ["error", "timeout"]
            },
            "reasoning": "User wants to collect logs from kubernetes"
        }
        mock_llm.complete = Mock(return_value=json.dumps(intent_response))
        
        with patch.object(orchestrator, 'get_llm', return_value=mock_llm):
            result = orchestrator._understand_user_intent(
                "Show me errors from payments service in the last 2 hours",
                []
            )
        
        assert result["intent"] == "fetch_data"
        assert result["confidence"] == 0.9
        assert "payments-svc" in result["parameters"]["services"]
        assert result["parameters"]["time_window"] == "2h"
    
    def test_decide_next_agent_fetch_data(self, orchestrator):
        """Test LLM-based agent routing decision for fetch_data intent."""
        # Mock LLM response for routing decision
        mock_llm = Mock()
        mock_llm.complete = Mock(return_value=json.dumps({
            "action": "data_fetcher",
            "reasoning": "User wants to fetch data",
            "prerequisites_met": True,
            "suggested_response": ""
        }))
        orchestrator.get_llm = Mock(return_value=mock_llm)
        
        result = orchestrator._decide_next_agent(
            "fetch_data", {}, 0.9, []
        )
        assert result["action"] == "data_fetcher"
        assert result["prerequisites_met"] is True
    
    def test_decide_next_agent_analyze_patterns(self, orchestrator, mock_scratchpad):
        """Test LLM-based agent routing decision for analyze_patterns intent."""
        # Mock that data has been collected
        mock_scratchpad.has_section = Mock(return_value=True)
        
        # Mock LLM response for routing decision
        mock_llm = Mock()
        mock_llm.complete = Mock(return_value=json.dumps({
            "action": "pattern_analyzer",
            "reasoning": "Data collected, ready to analyze patterns",
            "prerequisites_met": True,
            "suggested_response": ""
        }))
        orchestrator.get_llm = Mock(return_value=mock_llm)
        
        result = orchestrator._decide_next_agent(
            "analyze_patterns", {}, 0.9, []
        )
        assert result["action"] == "pattern_analyzer"
        assert result["prerequisites_met"] is True
    
    def test_decide_next_agent_without_dependencies(self, orchestrator, mock_scratchpad):
        """Test that LLM returns clarify when dependencies not met."""
        # Mock that no data has been collected
        mock_scratchpad.has_section = Mock(return_value=False)
        
        # Mock LLM response indicating prerequisites not met
        mock_llm = Mock()
        mock_llm.complete = Mock(return_value=json.dumps({
            "action": "clarify",
            "reasoning": "Data must be collected first",
            "prerequisites_met": False,
            "suggested_response": "I need to collect data before analyzing patterns. Shall I do that?"
        }))
        orchestrator.get_llm = Mock(return_value=mock_llm)
        
        result = orchestrator._decide_next_agent(
            "analyze_patterns", {}, 0.9, []
        )
        assert result["action"] == "clarify"
        assert result["prerequisites_met"] is False
    
    def test_llm_based_routing_no_hardcoded_logic(self, orchestrator):
        """Test that routing decisions come from LLM, not hardcoded mappings."""
        # This test verifies LLM-First design principle
        # The orchestrator should not contain hardcoded intent-to-agent mappings
        
        # Mock LLM to return unexpected agent name (not in old hardcoded mapping)
        mock_llm = Mock()
        mock_llm.complete = Mock(return_value=json.dumps({
            "action": "custom_agent",
            "reasoning": "LLM decided on custom agent",
            "prerequisites_met": True,
            "suggested_response": ""
        }))
        orchestrator.get_llm = Mock(return_value=mock_llm)
        
        result = orchestrator._decide_next_agent(
            "some_intent", {}, 0.9, []
        )
        # The result should contain whatever LLM decided
        assert result["action"] == "custom_agent"
        # Verify the method does not contain hardcoded logic by checking
        # that it accepts LLM's decision without validation
    
    def test_llm_routing_receives_full_context(self, orchestrator, mock_scratchpad):
        """Test that LLM receives conversation history and investigation state."""
        mock_scratchpad.has_section = Mock(return_value=True)
        mock_scratchpad.read_section = Mock(return_value={"some": "data"})
        
        mock_llm = Mock()
        mock_llm.complete = Mock(return_value=json.dumps({
            "action": "data_fetcher",
            "reasoning": "Ready to fetch",
            "prerequisites_met": True,
            "suggested_response": ""
        }))
        orchestrator.get_llm = Mock(return_value=mock_llm)
        
        conversation = [
            {"role": "user", "content": "Check logs", "timestamp": "2025-10-17T10:00:00"}
        ]
        
        result = orchestrator._decide_next_agent(
            "fetch_data", {"services": ["api"]}, 0.9, conversation
        )
        
        # Verify LLM was called with context
        assert mock_llm.complete.called
        call_args = mock_llm.complete.call_args[0][0]  # messages list
        user_prompt = call_args[1]["content"]
        
        # Verify context is included in prompt
        assert "fetch_data" in user_prompt  # intent
        assert "0.9" in user_prompt  # confidence
        assert "Investigation State" in user_prompt or "investigation_state" in user_prompt
    
    def test_process_initial_message(self, orchestrator, mock_scratchpad):
        """Test processing of initial conversational message."""
        mock_llm = Mock()
        intent_response = {
            "intent": "fetch_data",
            "confidence": 0.9,
            "parameters": {
                "services": ["payments"],
                "time_window": "1h",
                "data_sources": ["kubernetes"],
                "keywords": ["crash"]
            },
            "reasoning": "User wants to investigate crashes"
        }
        mock_llm.complete = Mock(return_value=json.dumps(intent_response))
        
        with patch.object(orchestrator, 'get_llm', return_value=mock_llm):
            orchestrator._process_initial_message("payments service is crashing")
        
        # Check that problem description was written
        mock_scratchpad.write_section.assert_called_once()
        call_args = mock_scratchpad.write_section.call_args
        assert call_args[0][0] == ScratchpadSection.PROBLEM_DESCRIPTION
        assert "payments service is crashing" in call_args[0][1]["description"]
    
    def test_get_investigation_state_summary_empty(self, orchestrator, mock_scratchpad):
        """Test investigation state summary when nothing is done."""
        mock_scratchpad.has_section = Mock(return_value=False)
        
        summary = orchestrator._get_investigation_state_summary()
        assert "just started" in summary.lower()
    
    def test_get_investigation_state_summary_with_data(self, orchestrator, mock_scratchpad):
        """Test investigation state summary with collected data."""
        def has_section_side_effect(section):
            return section in [
                ScratchpadSection.PROBLEM_DESCRIPTION,
                ScratchpadSection.DATA_COLLECTED
            ]
        
        mock_scratchpad.has_section = Mock(side_effect=has_section_side_effect)
        mock_scratchpad.read_section = Mock(return_value={
            "kubernetes": {"summary": "200 log entries"},
            "prometheus": {"summary": "50 metrics"}
        })
        
        summary = orchestrator._get_investigation_state_summary()
        assert "Problem description recorded" in summary
        assert "Data collected from: kubernetes, prometheus" in summary
    
    def test_handle_fetch_data_intent_success(self, orchestrator, mock_scratchpad):
        """Test handling fetch_data intent successfully."""
        with patch.object(orchestrator, 'route_to_agent', return_value={"success": True}):
            with patch.object(orchestrator, '_update_problem_parameters'):
                response = orchestrator._handle_fetch_data_intent({
                    "services": ["test-svc"],
                    "time_window": "2h"
                })
        
        assert "collected the data" in response.lower()
    
    def test_handle_analyze_patterns_intent_no_data(self, orchestrator, mock_scratchpad):
        """Test handling analyze_patterns intent without data."""
        mock_scratchpad.has_section = Mock(return_value=False)
        
        response = orchestrator._handle_analyze_patterns_intent({})
        assert "collect data first" in response.lower()
    
    def test_handle_diagnose_intent_no_data(self, orchestrator, mock_scratchpad):
        """Test handling diagnose intent without data."""
        mock_scratchpad.has_section = Mock(return_value=False)
        
        response = orchestrator._handle_diagnose_intent({})
        assert "collect some data" in response.lower()
    
    def test_handle_show_findings_intent(self, orchestrator):
        """Test handling show_findings intent."""
        with patch.object(orchestrator, 'present_findings'):
            response = orchestrator._handle_show_findings_intent()
        
        assert "anything else" in response.lower()
    
    def test_update_problem_parameters(self, orchestrator, mock_scratchpad):
        """Test updating problem parameters."""
        mock_scratchpad.read_section = Mock(return_value={
            "description": "original problem",
            "affected_services": []
        })
        
        orchestrator._update_problem_parameters({
            "services": ["new-svc"],
            "time_window": "4h"
        })
        
        # Verify write was called
        assert mock_scratchpad.write_section.called
        call_args = mock_scratchpad.write_section.call_args
        updated_data = call_args[0][1]
        assert updated_data["affected_services"] == ["new-svc"]
        assert updated_data["time_window"] == "4h"
    
    def test_check_if_complete_true(self, orchestrator, mock_scratchpad):
        """Test checking if investigation is complete."""
        mock_scratchpad.has_section = Mock(return_value=True)
        
        result = orchestrator._check_if_complete()
        assert result is True
    
    def test_check_if_complete_false(self, orchestrator, mock_scratchpad):
        """Test checking if investigation is not complete."""
        mock_scratchpad.has_section = Mock(return_value=False)
        
        result = orchestrator._check_if_complete()
        assert result is False
    
    @patch('aletheia.agents.orchestrator.Prompt.ask')
    def test_execute_conversational_mode_new_session(self, mock_ask, orchestrator, mock_scratchpad):
        """Test executing conversational mode with new session."""
        # Setup mocks
        mock_scratchpad.has_section = Mock(return_value=False)
        mock_llm = Mock()
        
        # Simulate conversation: initial message -> data fetch -> exit
        mock_ask.side_effect = [
            "show me errors from payments",  # Initial message
            "exit"  # Exit command
        ]
        
        intent_response = {
            "intent": "fetch_data",
            "confidence": 0.9,
            "parameters": {
                "services": ["payments"],
                "time_window": "2h",
                "data_sources": ["kubernetes"],
                "keywords": ["error"]
            },
            "reasoning": "User wants logs"
        }
        mock_llm.complete = Mock(return_value=json.dumps(intent_response))
        
        with patch.object(orchestrator, 'get_llm', return_value=mock_llm):
            with patch.object(orchestrator, '_display_welcome_conversational'):
                result = orchestrator._execute_conversational_mode()
        
        assert result["status"] == "interrupted"  # User typed 'exit'
        assert result["mode"] == "conversational"
        assert result["conversation_length"] > 0

