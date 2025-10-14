"""Unit tests for confirmation system."""

import pytest
from unittest.mock import Mock, patch
from aletheia.ui.confirmation import (
    ConfirmationManager,
    ConfirmationLevel,
    create_confirmation_manager
)


class TestConfirmationManager:
    """Tests for ConfirmationManager class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    @pytest.fixture
    def manager(self, mock_console):
        """Create ConfirmationManager with mock console."""
        return ConfirmationManager("normal", mock_console)

    def test_manager_creation(self):
        """Test ConfirmationManager initialization."""
        manager = ConfirmationManager()
        assert manager.level == "normal"
        assert manager.console is not None

    def test_manager_with_level(self):
        """Test ConfirmationManager with specified level."""
        manager = ConfirmationManager("verbose")
        assert manager.level == "verbose"

    def test_set_level(self, manager):
        """Test changing confirmation level."""
        manager.set_level("minimal")
        assert manager.level == "minimal"

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_verbose_mode(self, mock_ask, mock_console):
        """Test confirmation in verbose mode."""
        mock_ask.return_value = True
        manager = ConfirmationManager("verbose", mock_console)

        result = manager.confirm("Test message", category="analysis")

        assert result is True
        mock_ask.assert_called_once()

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_normal_mode_data_fetch(self, mock_ask, mock_console):
        """Test confirmation in normal mode for data fetch."""
        mock_ask.return_value = True
        manager = ConfirmationManager("normal", mock_console)

        result = manager.confirm("Test message", category="data_fetch")

        assert result is True
        mock_ask.assert_called_once()

    def test_confirm_normal_mode_analysis_skipped(self, mock_console):
        """Test that analysis confirmation is skipped in normal mode."""
        manager = ConfirmationManager("normal", mock_console)

        result = manager.confirm("Test message", category="analysis", default=True)

        # Should return default without prompting
        assert result is True

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_normal_mode_destructive(self, mock_ask, mock_console):
        """Test confirmation in normal mode for destructive operations."""
        mock_ask.return_value = False
        manager = ConfirmationManager("normal", mock_console)

        result = manager.confirm("Test message", category="destructive")

        assert result is False
        mock_ask.assert_called_once()

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_minimal_mode_destructive_only(self, mock_ask, mock_console):
        """Test that minimal mode only confirms destructive operations."""
        mock_ask.return_value = True
        manager = ConfirmationManager("minimal", mock_console)

        # Destructive should prompt
        result_destructive = manager.confirm("Test", category="destructive")
        assert result_destructive is True
        mock_ask.assert_called_once()

        # Data fetch should not prompt
        result_data = manager.confirm("Test", category="data_fetch", default=True)
        assert result_data is True
        # Still only one call (destructive)
        assert mock_ask.call_count == 1

    def test_confirm_with_default_false(self, mock_console):
        """Test confirmation with default=False."""
        manager = ConfirmationManager("minimal", mock_console)

        result = manager.confirm("Test", category="data_fetch", default=False)

        assert result is False

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_keyboard_interrupt(self, mock_ask, mock_console):
        """Test handling keyboard interrupt during confirmation."""
        mock_ask.side_effect = KeyboardInterrupt()
        manager = ConfirmationManager("verbose", mock_console)

        result = manager.confirm("Test message", category="data_fetch")

        assert result is False
        assert manager.console.print.called

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_command_verbose(self, mock_ask, mock_console):
        """Test command confirmation in verbose mode."""
        mock_ask.return_value = True
        manager = ConfirmationManager("verbose", mock_console)

        result = manager.confirm_command("kubectl logs pod", "Fetch logs")

        assert result is True
        assert mock_console.print.call_count >= 2  # Command and description

    def test_confirm_command_normal_skipped(self, mock_console):
        """Test that command confirmation is skipped in normal mode."""
        manager = ConfirmationManager("normal", mock_console)

        result = manager.confirm_command("kubectl logs pod")

        assert result is True
        # No prints should happen
        assert not mock_console.print.called

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_confirm_agent_transition_verbose(self, mock_ask, mock_console):
        """Test agent transition confirmation in verbose mode."""
        mock_ask.return_value = True
        manager = ConfirmationManager("verbose", mock_console)

        result = manager.confirm_agent_transition("Orchestrator", "Data Fetcher")

        assert result is True
        mock_ask.assert_called_once()

    def test_confirm_agent_transition_normal_skipped(self, mock_console):
        """Test that agent transition is skipped in normal mode."""
        manager = ConfirmationManager("normal", mock_console)

        result = manager.confirm_agent_transition("Orchestrator", "Data Fetcher")

        assert result is True

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_show_and_confirm(self, mock_ask, mock_console):
        """Test show_and_confirm method."""
        mock_ask.return_value = True
        manager = ConfirmationManager("normal", mock_console)

        result = manager.show_and_confirm(
            "Summary text",
            "Detailed info",
            category="data_fetch"
        )

        assert result is True
        assert mock_console.print.called

    @patch('aletheia.ui.confirmation.Confirm.ask')
    def test_show_and_confirm_verbose_shows_details(self, mock_ask, mock_console):
        """Test that details are shown in verbose mode."""
        mock_ask.return_value = True
        manager = ConfirmationManager("verbose", mock_console)

        result = manager.show_and_confirm(
            "Summary text",
            "Detailed info",
            category="analysis"
        )

        assert result is True
        # Should print both summary and details
        assert mock_console.print.call_count >= 2

    def test_should_confirm_verbose(self, mock_console):
        """Test _should_confirm logic for verbose mode."""
        manager = ConfirmationManager("verbose", mock_console)

        assert manager._should_confirm("data_fetch")
        assert manager._should_confirm("repository_access")
        assert manager._should_confirm("analysis")
        assert manager._should_confirm("destructive")

    def test_should_confirm_normal(self, mock_console):
        """Test _should_confirm logic for normal mode."""
        manager = ConfirmationManager("normal", mock_console)

        assert manager._should_confirm("data_fetch")
        assert manager._should_confirm("repository_access")
        assert not manager._should_confirm("analysis")
        assert manager._should_confirm("destructive")

    def test_should_confirm_minimal(self, mock_console):
        """Test _should_confirm logic for minimal mode."""
        manager = ConfirmationManager("minimal", mock_console)

        assert not manager._should_confirm("data_fetch")
        assert not manager._should_confirm("repository_access")
        assert not manager._should_confirm("analysis")
        assert manager._should_confirm("destructive")


def test_create_confirmation_manager_factory():
    """Test create_confirmation_manager factory function."""
    manager = create_confirmation_manager()
    assert isinstance(manager, ConfirmationManager)
    assert manager.level == "normal"

    manager_verbose = create_confirmation_manager("verbose")
    assert manager_verbose.level == "verbose"
