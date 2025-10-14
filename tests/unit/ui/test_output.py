"""Unit tests for output formatting."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from aletheia.ui.output import OutputFormatter, create_output_formatter


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    @pytest.fixture
    def formatter(self, mock_console):
        """Create OutputFormatter with mock console."""
        return OutputFormatter(mock_console, verbose=False)

    @pytest.fixture
    def verbose_formatter(self, mock_console):
        """Create OutputFormatter in verbose mode."""
        return OutputFormatter(mock_console, verbose=True)

    def test_formatter_creation(self):
        """Test OutputFormatter initialization."""
        formatter = OutputFormatter()
        assert formatter.console is not None
        assert formatter.verbose is False

    def test_formatter_verbose_mode(self):
        """Test OutputFormatter in verbose mode."""
        formatter = OutputFormatter(verbose=True)
        assert formatter.verbose is True

    def test_print_header_level_1(self, formatter, mock_console):
        """Test printing level 1 header."""
        formatter.print_header("Test Header", level=1)

        # Should print 3 times: top border, text, bottom border
        assert mock_console.print.call_count == 3

    def test_print_header_level_2(self, formatter, mock_console):
        """Test printing level 2 header."""
        formatter.print_header("Test Header", level=2)

        # Should print 2 times: text and underline
        assert mock_console.print.call_count == 2

    def test_print_header_level_3(self, formatter, mock_console):
        """Test printing level 3 header."""
        formatter.print_header("Test Header", level=3)

        # Should print 1 time: text only
        assert mock_console.print.call_count == 1

    def test_print_status_success(self, formatter, mock_console):
        """Test printing success status."""
        formatter.print_status("Operation succeeded", status="success")
        mock_console.print.assert_called_once()

    def test_print_status_error(self, formatter, mock_console):
        """Test printing error status."""
        formatter.print_status("Operation failed", status="error")
        mock_console.print.assert_called_once()

    def test_print_status_warning(self, formatter, mock_console):
        """Test printing warning status."""
        formatter.print_status("Warning message", status="warning")
        mock_console.print.assert_called_once()

    def test_print_status_info(self, formatter, mock_console):
        """Test printing info status."""
        formatter.print_status("Info message", status="info")
        mock_console.print.assert_called_once()

    def test_print_status_progress(self, formatter, mock_console):
        """Test printing progress status."""
        formatter.print_status("In progress", status="progress")
        mock_console.print.assert_called_once()

    def test_print_agent_action_verbose(self, verbose_formatter, mock_console):
        """Test printing agent action in verbose mode."""
        verbose_formatter.print_agent_action("Data Fetcher", "Fetching logs")

        mock_console.print.assert_called_once()
        call_args = str(mock_console.print.call_args)
        assert "Data Fetcher" in call_args

    def test_print_agent_action_normal_skipped(self, formatter, mock_console):
        """Test that agent action is skipped in normal mode."""
        formatter.print_agent_action("Data Fetcher", "Fetching logs")

        # Should not print in normal mode
        assert not mock_console.print.called

    def test_print_error_simple(self, formatter, mock_console):
        """Test printing simple error."""
        formatter.print_error("Something went wrong")
        mock_console.print.assert_called()

    def test_print_error_with_details(self, formatter, mock_console):
        """Test printing error with details."""
        formatter.print_error("Something went wrong", details="Connection timeout")
        assert mock_console.print.call_count >= 2

    def test_print_error_with_recovery_options(self, formatter, mock_console):
        """Test printing error with recovery options."""
        formatter.print_error(
            "Something went wrong",
            recovery_options=["Retry", "Skip", "Abort"]
        )

        # Should print error, "What would you like to do?", and 3 options
        assert mock_console.print.call_count >= 5

    def test_print_warning(self, formatter, mock_console):
        """Test printing warning."""
        formatter.print_warning("Warning message")
        mock_console.print.assert_called()

    def test_print_warning_with_details(self, formatter, mock_console):
        """Test printing warning with details."""
        formatter.print_warning("Warning message", details="More info")
        assert mock_console.print.call_count >= 2

    def test_print_table(self, formatter, mock_console):
        """Test printing table."""
        formatter.print_table(
            "Test Table",
            ["Column 1", "Column 2"],
            [["Row 1 Col 1", "Row 1 Col 2"], ["Row 2 Col 1", "Row 2 Col 2"]]
        )

        mock_console.print.assert_called_once()

    def test_print_list(self, formatter, mock_console):
        """Test printing list."""
        formatter.print_list(["Item 1", "Item 2", "Item 3"])
        assert mock_console.print.call_count == 3

    def test_print_list_with_title(self, formatter, mock_console):
        """Test printing list with title."""
        formatter.print_list(["Item 1", "Item 2"], title="My List")

        # Should print title + 2 items
        assert mock_console.print.call_count == 3

    def test_print_list_custom_bullet(self, formatter, mock_console):
        """Test printing list with custom bullet."""
        formatter.print_list(["Item 1"], bullet="-")

        call_args = str(mock_console.print.call_args)
        assert "-" in call_args

    def test_print_code(self, formatter, mock_console):
        """Test printing syntax-highlighted code."""
        formatter.print_code("def test():\n    pass", language="python")
        mock_console.print.assert_called_once()

    def test_print_markdown(self, formatter, mock_console):
        """Test printing markdown."""
        formatter.print_markdown("# Header\n\nParagraph")
        mock_console.print.assert_called_once()

    def test_print_panel(self, formatter, mock_console):
        """Test printing panel."""
        formatter.print_panel("Content", title="Title")
        mock_console.print.assert_called_once()

    def test_print_diagnosis(self, formatter, mock_console):
        """Test printing formatted diagnosis."""
        formatter.print_diagnosis(
            root_cause="Test root cause",
            description="Test description",
            evidence=["Evidence 1", "Evidence 2"],
            actions=[
                {"priority": "immediate", "action": "Rollback"},
                {"priority": "high", "action": "Fix bug"}
            ],
            confidence=0.86
        )

        # Should print multiple times (header, sections, items)
        assert mock_console.print.call_count > 5

    def test_print_diagnosis_confidence_formatting(self, formatter, mock_console):
        """Test diagnosis confidence is formatted as percentage."""
        formatter.print_diagnosis(
            root_cause="Test",
            description="Test",
            evidence=[],
            actions=[],
            confidence=0.75
        )

        # Check that 75% appears in output
        printed_text = ""
        for call in mock_console.print.call_args_list:
            printed_text += str(call)

        assert "75%" in printed_text

    def test_progress_context(self, formatter, mock_console):
        """Test progress context manager."""
        with patch('aletheia.ui.output.Progress') as mock_progress_class:
            mock_progress = MagicMock()
            mock_progress_class.return_value.__enter__.return_value = mock_progress

            with formatter.progress_context("Testing"):
                pass

            mock_progress.add_task.assert_called_once()


def test_create_output_formatter_factory():
    """Test create_output_formatter factory function."""
    formatter = create_output_formatter()
    assert isinstance(formatter, OutputFormatter)
    assert formatter.verbose is False

    verbose_formatter = create_output_formatter(verbose=True)
    assert verbose_formatter.verbose is True
