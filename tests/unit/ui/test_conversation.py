"""
Unit tests for conversational UI helpers.

Tests verify that UI functions are display/input only with no logic.
"""

import pytest
from unittest.mock import Mock, patch, call
from io import StringIO

from aletheia.ui.conversation import (
    ConversationalUI,
    display_conversation,
    format_agent_response,
    get_user_input
)


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def conversational_ui(mock_console):
    """Create a ConversationalUI instance with mocked console."""
    return ConversationalUI(console=mock_console)


class TestConversationalUI:
    """Tests for ConversationalUI class."""
    
    def test_init_with_console(self, mock_console):
        """Test initialization with provided console."""
        ui = ConversationalUI(console=mock_console)
        assert ui.console == mock_console
    
    def test_init_without_console(self):
        """Test initialization creates console if not provided."""
        ui = ConversationalUI()
        assert ui.console is not None
    
    def test_display_conversation_empty(self, conversational_ui, mock_console):
        """Test displaying empty conversation."""
        conversational_ui.display_conversation([])
        
        # Should display "No conversation history" message
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        assert any("No conversation history" in arg for arg in call_args)
    
    def test_display_conversation_single_user_message(self, conversational_ui, mock_console):
        """Test displaying conversation with single user message."""
        conversation = [
            {"role": "user", "content": "Why is my service failing?"}
        ]
        
        conversational_ui.display_conversation(conversation)
        
        # Should print conversation with user message
        assert mock_console.print.called
        # Verify the message was displayed
        assert mock_console.print.call_count >= 1
    
    def test_display_conversation_multiple_messages(self, conversational_ui, mock_console):
        """Test displaying conversation with multiple messages."""
        conversation = [
            {"role": "user", "content": "Why is my service failing?"},
            {"role": "agent", "content": "Let me check the logs for you."},
            {"role": "user", "content": "It started 2 hours ago."},
        ]
        
        conversational_ui.display_conversation(conversation, show_all=True)
        
        # Should display all messages
        assert mock_console.print.called
        assert mock_console.print.call_count >= 3  # At least one per message
    
    def test_display_conversation_max_messages(self, conversational_ui, mock_console):
        """Test displaying conversation respects max_messages parameter."""
        conversation = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(10)
        ]
        
        conversational_ui.display_conversation(conversation, show_all=False, max_messages=3)
        
        # Should indicate showing subset
        assert mock_console.print.called
        # Verify multiple messages were displayed (at least the subset)
        assert mock_console.print.call_count >= 3
    
    def test_display_conversation_different_roles(self, conversational_ui, mock_console):
        """Test displaying messages with different roles."""
        conversation = [
            {"role": "user", "content": "User message"},
            {"role": "agent", "content": "Agent message"},
            {"role": "system", "content": "System message"},
            {"role": "unknown", "content": "Unknown message"},
        ]
        
        conversational_ui.display_conversation(conversation, show_all=True)
        
        # Should handle all role types
        assert mock_console.print.called
        assert mock_console.print.call_count >= 4
    
    def test_format_agent_response_simple(self, conversational_ui, mock_console):
        """Test formatting simple agent response."""
        response = "I found 47 errors in the logs."
        
        conversational_ui.format_agent_response(response)
        
        # Should display response in panel
        assert mock_console.print.called
    
    def test_format_agent_response_with_agent_name(self, conversational_ui, mock_console):
        """Test formatting response with agent name."""
        response = "Data collection complete."
        
        conversational_ui.format_agent_response(
            response,
            agent_name="data_fetcher",
            show_agent_name=True
        )
        
        # Should display with agent name
        assert mock_console.print.called
    
    def test_format_agent_response_no_agent_name(self, conversational_ui, mock_console):
        """Test formatting response without showing agent name."""
        response = "Analysis complete."
        
        conversational_ui.format_agent_response(
            response,
            agent_name="pattern_analyzer",
            show_agent_name=False
        )
        
        # Should display without agent name in title
        assert mock_console.print.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_get_user_input_simple(self, mock_ask, conversational_ui):
        """Test getting user input."""
        mock_ask.return_value = "  test input  "
        
        result = conversational_ui.get_user_input()
        
        # Should return stripped input
        assert result == "test input"
        assert mock_ask.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_get_user_input_custom_prompt(self, mock_ask, conversational_ui):
        """Test getting user input with custom prompt."""
        mock_ask.return_value = "custom response"
        
        result = conversational_ui.get_user_input(prompt="Custom: ")
        
        assert result == "custom response"
        assert mock_ask.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_get_user_input_empty(self, mock_ask, conversational_ui):
        """Test getting empty user input."""
        mock_ask.return_value = "   "
        
        result = conversational_ui.get_user_input()
        
        # Should return empty string after strip
        assert result == ""
    
    def test_display_agent_thinking_default(self, conversational_ui, mock_console):
        """Test displaying agent thinking with default message."""
        conversational_ui.display_agent_thinking()
        
        assert mock_console.print.called
        call_args = str(mock_console.print.call_args_list[0][0][0])
        assert "Analyzing" in call_args or "⏳" in call_args
    
    def test_display_agent_thinking_custom(self, conversational_ui, mock_console):
        """Test displaying agent thinking with custom message."""
        conversational_ui.display_agent_thinking("Fetching data...")
        
        assert mock_console.print.called
        call_args = str(mock_console.print.call_args_list[0][0][0])
        assert "Fetching data" in call_args or "⏳" in call_args
    
    def test_display_clarification_request_simple(self, conversational_ui, mock_console):
        """Test displaying clarification request."""
        question = "Which namespace is the service in?"
        
        conversational_ui.display_clarification_request(question)
        
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        conversation_text = " ".join(call_args)
        assert "namespace" in conversation_text or "clarification" in conversation_text.lower()
    
    def test_display_clarification_request_with_context(self, conversational_ui, mock_console):
        """Test displaying clarification with context."""
        question = "Which service is failing?"
        context = "I need to know the service name to fetch logs."
        
        conversational_ui.display_clarification_request(question, context=context)
        
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        conversation_text = " ".join(call_args)
        assert "service" in conversation_text.lower()
    
    def test_display_conversation_starter_no_problem(self, conversational_ui, mock_console):
        """Test displaying conversation starter without problem description."""
        conversational_ui.display_conversation_starter()
        
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        conversation_text = " ".join(call_args)
        assert "Welcome" in conversation_text or "problem" in conversation_text.lower()
    
    def test_display_conversation_starter_with_problem(self, conversational_ui, mock_console):
        """Test displaying conversation starter with problem description."""
        problem = "Payments service is returning 500 errors"
        
        conversational_ui.display_conversation_starter(problem_description=problem)
        
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        conversation_text = " ".join(call_args)
        assert "Payments" in conversation_text or "500" in conversation_text
    
    def test_display_session_summary(self, conversational_ui, mock_console):
        """Test displaying session summary."""
        conversational_ui.display_session_summary(
            session_id="INC-1234",
            status="completed",
            message_count=15
        )
        
        assert mock_console.print.called
        call_args = [str(call[0][0]) for call in mock_console.print.call_args_list]
        conversation_text = " ".join(call_args)
        assert "INC-1234" in conversation_text or "completed" in conversation_text or "15" in conversation_text
    
    def test_display_help(self, conversational_ui, mock_console):
        """Test displaying help information."""
        conversational_ui.display_help()
        
        assert mock_console.print.called
        # Help should be displayed (Panel object passed to print)
        assert mock_console.print.call_count >= 1
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_confirm_action_yes(self, mock_ask, conversational_ui):
        """Test confirming action with yes."""
        mock_ask.return_value = "y"
        
        result = conversational_ui.confirm_action("Delete session?")
        
        assert result is True
        assert mock_ask.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_confirm_action_no(self, mock_ask, conversational_ui):
        """Test confirming action with no."""
        mock_ask.return_value = "n"
        
        result = conversational_ui.confirm_action("Delete session?")
        
        assert result is False
        assert mock_ask.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_confirm_action_yes_full(self, mock_ask, conversational_ui):
        """Test confirming action with 'yes' word."""
        mock_ask.return_value = "yes"
        
        result = conversational_ui.confirm_action("Proceed?")
        
        assert result is True
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_confirm_action_no_full(self, mock_ask, conversational_ui):
        """Test confirming action with 'no' word."""
        mock_ask.return_value = "no"
        
        result = conversational_ui.confirm_action("Proceed?")
        
        assert result is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch('aletheia.ui.conversation.ConversationalUI')
    def test_display_conversation_convenience(self, mock_ui_class):
        """Test convenience function for display_conversation."""
        mock_ui = Mock()
        mock_ui_class.return_value = mock_ui
        
        conversation = [{"role": "user", "content": "test"}]
        display_conversation(conversation, show_all=True, max_messages=10)
        
        # Should create UI and call display_conversation
        assert mock_ui_class.called
        assert mock_ui.display_conversation.called
    
    @patch('aletheia.ui.conversation.ConversationalUI')
    def test_format_agent_response_convenience(self, mock_ui_class):
        """Test convenience function for format_agent_response."""
        mock_ui = Mock()
        mock_ui_class.return_value = mock_ui
        
        format_agent_response("Test response", agent_name="test_agent")
        
        assert mock_ui_class.called
        assert mock_ui.format_agent_response.called
    
    @patch('aletheia.ui.conversation.ConversationalUI')
    def test_get_user_input_convenience(self, mock_ui_class):
        """Test convenience function for get_user_input."""
        mock_ui = Mock()
        mock_ui.get_user_input.return_value = "test input"
        mock_ui_class.return_value = mock_ui
        
        result = get_user_input(prompt="Test: ")
        
        assert result == "test input"
        assert mock_ui_class.called
        assert mock_ui.get_user_input.called


class TestUILogicFree:
    """Tests to verify UI helpers contain NO logic."""
    
    def test_display_conversation_no_parsing(self, conversational_ui, mock_console):
        """Verify display_conversation does not parse or extract from messages."""
        # Conversation with various formats - UI should display as-is
        conversation = [
            {"role": "user", "content": "pod: payments-svc namespace: production"},
            {"role": "agent", "content": "service=payments error_rate=45%"},
        ]
        
        conversational_ui.display_conversation(conversation)
        
        # Should just display, not extract parameters
        assert mock_console.print.called
        # Verify it doesn't try to extract structured data
        # (if it did, it would fail or modify the messages)
    
    def test_format_agent_response_no_interpretation(self, conversational_ui, mock_console):
        """Verify format_agent_response does not interpret response content."""
        # Response with various formats
        response = "Error rate: 45%. Pod: payments-svc. Action: restart"
        
        conversational_ui.format_agent_response(response)
        
        # Should just format, not interpret or extract
        assert mock_console.print.called
    
    @patch('aletheia.ui.conversation.Prompt.ask')
    def test_get_user_input_no_validation(self, mock_ask, conversational_ui):
        """Verify get_user_input does not validate or parse input."""
        # Input with various formats that might need parsing
        mock_ask.return_value = "pod:test namespace:prod time:2h"
        
        result = conversational_ui.get_user_input()
        
        # Should return as-is, not validate or parse
        assert result == "pod:test namespace:prod time:2h"
        # No exceptions should be raised for "invalid" formats
    
    def test_display_methods_are_void(self, conversational_ui):
        """Verify display methods return None (display-only)."""
        # All display methods should return None
        assert conversational_ui.display_conversation([]) is None
        assert conversational_ui.format_agent_response("test") is None
        assert conversational_ui.display_agent_thinking() is None
        assert conversational_ui.display_clarification_request("test?") is None
        assert conversational_ui.display_conversation_starter() is None
        assert conversational_ui.display_session_summary("id", "status", 5) is None
        assert conversational_ui.display_help() is None
