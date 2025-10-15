"""Unit tests for diagnosis output and action handling."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from aletheia.ui.diagnosis import (
    DiagnosisFormatter,
    DiagnosisActionHandler,
    display_diagnosis,
    export_diagnosis_to_markdown,
    handle_diagnosis_actions
)
from aletheia.ui.output import OutputFormatter


@pytest.fixture
def sample_diagnosis():
    """Sample diagnosis data for testing."""
    return {
        "root_cause": {
            "type": "nil_pointer_dereference",
            "confidence": 0.86,
            "description": "The IsEnabled function dereferences f.Enabled without checking if f is nil."
        },
        "timeline_correlation": {
            "deployment": "payments-svc v1.19 rollout at 08:04",
            "first_error": "08:05:14 (70 seconds after deployment)",
            "alignment": "Temporal alignment supports hypothesis"
        },
        "evidence": [
            "45 instances of nil pointer errors",
            "All errors in charge.go:112",
            "Errors started immediately after deployment"
        ],
        "recommended_actions": [
            {
                "priority": "immediate",
                "action": "Rollback payments-svc to v1.18",
                "rationale": "Stop ongoing customer impact"
            },
            {
                "priority": "high",
                "action": "Apply nil-safe patch to IsEnabled",
                "rationale": "Fix the root cause",
                "patch": "func IsEnabled(f *Feature) bool {\n    return f != nil && f.Enabled != nil && *f.Enabled\n}"
            },
            {
                "priority": "medium",
                "action": "Add unit test for nil Feature handling"
            },
            {
                "priority": "low",
                "action": "Review all callers of featurekit.Get() for nil checks"
            }
        ]
    }


@pytest.fixture
def minimal_diagnosis():
    """Minimal diagnosis data for testing."""
    return {
        "root_cause": {
            "type": "unknown",
            "confidence": 0.5,
            "description": "Unable to determine root cause"
        },
        "recommended_actions": []
    }


@pytest.fixture
def mock_console():
    """Mock Rich console."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def diagnosis_formatter(mock_console):
    """DiagnosisFormatter with mock console."""
    output = OutputFormatter(console=mock_console)
    return DiagnosisFormatter(output_formatter=output)


@pytest.fixture
def temp_session_dir(tmp_path):
    """Temporary session directory."""
    session_dir = tmp_path / "test_session"
    session_dir.mkdir()
    return session_dir


class TestDiagnosisFormatter:
    """Tests for DiagnosisFormatter class."""

    def test_initialization(self):
        """Test formatter initialization."""
        formatter = DiagnosisFormatter()
        assert formatter.output is not None
        assert formatter.console is not None

    def test_initialization_with_custom_formatter(self, mock_console):
        """Test initialization with custom formatter."""
        output = OutputFormatter(console=mock_console)
        formatter = DiagnosisFormatter(output_formatter=output)
        assert formatter.output == output
        assert formatter.console == mock_console

    def test_display_diagnosis_full(self, diagnosis_formatter, sample_diagnosis):
        """Test displaying full diagnosis."""
        diagnosis_formatter.display_diagnosis(sample_diagnosis, show_action_menu=False)

        # Verify console.print was called with expected content
        console = diagnosis_formatter.console
        assert console.print.called

        # Check for key elements in output
        calls_str = " ".join([str(call) for call in console.print.call_args_list])
        assert "ROOT CAUSE ANALYSIS" in calls_str
        assert "86%" in calls_str  # Confidence
        assert "nil_pointer_dereference" in calls_str
        assert "IMMEDIATE" in calls_str  # Priority

    def test_display_diagnosis_minimal(self, diagnosis_formatter, minimal_diagnosis):
        """Test displaying minimal diagnosis."""
        diagnosis_formatter.display_diagnosis(minimal_diagnosis, show_action_menu=False)

        console = diagnosis_formatter.console
        assert console.print.called

        calls_str = " ".join([str(call) for call in console.print.call_args_list])
        assert "50%" in calls_str  # Lower confidence
        assert "unknown" in calls_str

    def test_display_diagnosis_empty(self, diagnosis_formatter):
        """Test displaying empty diagnosis."""
        diagnosis_formatter.display_diagnosis({}, show_action_menu=False)

        console = diagnosis_formatter.console
        # Should call print_error
        assert console.print.called

    def test_display_diagnosis_with_action_menu(self, diagnosis_formatter, sample_diagnosis):
        """Test displaying diagnosis with action menu."""
        diagnosis_formatter.display_diagnosis(sample_diagnosis, show_action_menu=True)

        console = diagnosis_formatter.console
        calls_str = " ".join([str(call) for call in console.print.call_args_list])
        assert "What would you like to do?" in calls_str

    def test_display_diagnosis_with_patch(self, diagnosis_formatter, sample_diagnosis):
        """Test displaying diagnosis with code patch."""
        diagnosis_formatter.display_diagnosis(sample_diagnosis, show_action_menu=False)

        console = diagnosis_formatter.console
        assert console.print.called
        # Patch should be displayed

    def test_get_confidence_color(self, diagnosis_formatter):
        """Test confidence color mapping."""
        assert diagnosis_formatter._get_confidence_color(0.9) == "green"
        assert diagnosis_formatter._get_confidence_color(0.7) == "yellow"
        assert diagnosis_formatter._get_confidence_color(0.5) == "red"
        assert diagnosis_formatter._get_confidence_color(0.3) == "red"

    def test_get_priority_color(self, diagnosis_formatter):
        """Test priority color mapping."""
        assert diagnosis_formatter._get_priority_color("IMMEDIATE") == "bold red"
        assert diagnosis_formatter._get_priority_color("HIGH") == "yellow"
        assert diagnosis_formatter._get_priority_color("MEDIUM") == "blue"
        assert diagnosis_formatter._get_priority_color("LOW") == "white"
        assert diagnosis_formatter._get_priority_color("unknown") == "white"

    def test_detect_language_from_patch(self, diagnosis_formatter):
        """Test language detection from patch."""
        go_patch = "func IsEnabled() bool { return true }"
        assert diagnosis_formatter._detect_language_from_patch(go_patch) == "go"

        python_patch = "def is_enabled(): return True"
        assert diagnosis_formatter._detect_language_from_patch(python_patch) == "python"

        js_patch = "function isEnabled() { return true; }"
        assert diagnosis_formatter._detect_language_from_patch(js_patch) == "javascript"

        java_patch = "public class Feature { private boolean enabled; }"
        assert diagnosis_formatter._detect_language_from_patch(java_patch) == "java"

        unknown_patch = "some random text"
        assert diagnosis_formatter._detect_language_from_patch(unknown_patch) == "text"

    def test_export_to_markdown_full(self, diagnosis_formatter, sample_diagnosis, tmp_path):
        """Test exporting full diagnosis to markdown."""
        output_path = tmp_path / "diagnosis.md"

        diagnosis_formatter.export_to_markdown(
            sample_diagnosis,
            output_path,
            include_metadata=True
        )

        # Verify file was created
        assert output_path.exists()

        # Verify content
        content = output_path.read_text()
        assert "# Root Cause Analysis Report" in content
        assert "**Generated**:" in content
        assert "## Root Cause" in content
        assert "nil_pointer_dereference" in content
        assert "## Timeline Correlation" in content
        assert "## Supporting Evidence" in content
        assert "## Recommended Actions" in content
        assert "### IMMEDIATE Priority" in content
        assert "### HIGH Priority" in content
        assert "```go" in content  # Patch should be included

    def test_export_to_markdown_minimal(self, diagnosis_formatter, minimal_diagnosis, tmp_path):
        """Test exporting minimal diagnosis to markdown."""
        output_path = tmp_path / "minimal.md"

        diagnosis_formatter.export_to_markdown(
            minimal_diagnosis,
            output_path,
            include_metadata=False
        )

        assert output_path.exists()
        content = output_path.read_text()
        assert "# Root Cause Analysis Report" in content
        assert "**Generated**:" not in content  # No metadata
        assert "unknown" in content

    def test_export_to_markdown_creates_parent_dirs(self, diagnosis_formatter, sample_diagnosis, tmp_path):
        """Test that export creates parent directories."""
        output_path = tmp_path / "subdir" / "nested" / "diagnosis.md"

        diagnosis_formatter.export_to_markdown(
            sample_diagnosis,
            output_path,
            include_metadata=True
        )

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_export_to_markdown_empty_diagnosis(self, diagnosis_formatter, tmp_path):
        """Test exporting empty diagnosis raises error."""
        output_path = tmp_path / "empty.md"

        with pytest.raises(ValueError, match="No diagnosis data to export"):
            diagnosis_formatter.export_to_markdown({}, output_path)

    def test_export_to_markdown_invalid_path(self, diagnosis_formatter, sample_diagnosis):
        """Test export with invalid path."""
        # Try to write to a directory that can't be created
        output_path = Path("/invalid/path/diagnosis.md")

        with pytest.raises(IOError):
            diagnosis_formatter.export_to_markdown(sample_diagnosis, output_path)

    def test_export_to_markdown_priority_grouping(self, diagnosis_formatter, tmp_path):
        """Test that actions are properly grouped by priority."""
        diagnosis = {
            "root_cause": {
                "type": "test",
                "confidence": 0.8,
                "description": "Test diagnosis"
            },
            "recommended_actions": [
                {"priority": "low", "action": "Low priority action"},
                {"priority": "immediate", "action": "Immediate action"},
                {"priority": "medium", "action": "Medium action"},
                {"priority": "high", "action": "High priority action"},
            ]
        }

        output_path = tmp_path / "priority_test.md"
        diagnosis_formatter.export_to_markdown(diagnosis, output_path)

        content = output_path.read_text()

        # Verify priority sections appear in order
        immediate_pos = content.find("### IMMEDIATE Priority")
        high_pos = content.find("### HIGH Priority")
        medium_pos = content.find("### MEDIUM Priority")
        low_pos = content.find("### LOW Priority")

        assert immediate_pos < high_pos < medium_pos < low_pos


class TestDiagnosisActionHandler:
    """Tests for DiagnosisActionHandler class."""

    def test_initialization(self, sample_diagnosis, temp_session_dir, mock_console):
        """Test handler initialization."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        assert handler.diagnosis == sample_diagnosis
        assert handler.session_dir == temp_session_dir
        assert handler.console == mock_console

    def test_handle_action_invalid(self, sample_diagnosis, temp_session_dir, mock_console):
        """Test handling invalid action choice."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.handle_action(99)
        assert result is True  # Should continue session

    def test_show_proposed_patch(self, sample_diagnosis, temp_session_dir, mock_console):
        """Test showing proposed patch."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.show_proposed_patch()

        assert result is True  # Should continue session
        assert mock_console.print.called

        # Verify patch was shown
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "PROPOSED PATCHES" in calls_str

    def test_show_proposed_patch_no_patches(self, minimal_diagnosis, temp_session_dir, mock_console):
        """Test showing patches when none available."""
        handler = DiagnosisActionHandler(minimal_diagnosis, temp_session_dir, mock_console)
        result = handler.show_proposed_patch()

        assert result is True
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "No patches available" in calls_str

    @patch('subprocess.run')
    @patch.dict('os.environ', {'EDITOR': 'vim'})
    def test_open_in_editor_success(self, mock_run, sample_diagnosis, temp_session_dir, mock_console):
        """Test opening diagnosis in editor."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.open_in_editor()

        assert result is True  # Should continue session

        # Verify markdown file was created
        temp_file = temp_session_dir / "diagnosis.md"
        assert temp_file.exists()

        # Verify subprocess.run was called with editor
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == 'vim'
        assert str(temp_file) in args[1]

    @patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'vim'))
    @patch.dict('os.environ', {'EDITOR': 'vim'})
    def test_open_in_editor_failure(self, mock_run, sample_diagnosis, temp_session_dir, mock_console):
        """Test editor failure handling."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.open_in_editor()

        assert result is True  # Should still continue
        # Error message should be printed
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "Failed to open editor" in calls_str

    @patch('subprocess.run', side_effect=FileNotFoundError())
    @patch.dict('os.environ', {'EDITOR': 'nonexistent'})
    def test_open_in_editor_not_found(self, mock_run, sample_diagnosis, temp_session_dir, mock_console):
        """Test editor not found handling."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.open_in_editor()

        assert result is True
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "not found" in calls_str

    @patch('aletheia.ui.input.InputHandler.get_text')
    def test_save_to_file_success(self, mock_get_text, sample_diagnosis, temp_session_dir, mock_console):
        """Test saving diagnosis to file."""
        mock_get_text.return_value = "test_diagnosis.md"

        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.save_to_file()

        assert result is True

        # Verify file was created
        saved_file = temp_session_dir / "test_diagnosis.md"
        assert saved_file.exists()

        # Verify success message
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "Saved to" in calls_str

    @patch('aletheia.ui.input.InputHandler.get_text')
    def test_save_to_file_absolute_path(self, mock_get_text, sample_diagnosis, temp_session_dir, tmp_path, mock_console):
        """Test saving with absolute path."""
        output_path = tmp_path / "absolute_diagnosis.md"
        mock_get_text.return_value = str(output_path)

        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.save_to_file()

        assert result is True
        assert output_path.exists()

    @patch('aletheia.ui.input.InputHandler.get_text')
    def test_save_to_file_cancelled(self, mock_get_text, sample_diagnosis, temp_session_dir, mock_console):
        """Test cancelling save operation."""
        mock_get_text.return_value = ""

        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.save_to_file()

        assert result is True
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "cancelled" in calls_str

    @patch('aletheia.ui.confirmation.ConfirmationManager.confirm')
    def test_end_session_confirmed(self, mock_confirm, sample_diagnosis, temp_session_dir, mock_console):
        """Test ending session with confirmation."""
        mock_confirm.return_value = True

        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.end_session()

        assert result is False  # Should end session
        calls_str = " ".join([str(call) for call in mock_console.print.call_args_list])
        assert "Session ended" in calls_str

    @patch('aletheia.ui.confirmation.ConfirmationManager.confirm')
    def test_end_session_cancelled(self, mock_confirm, sample_diagnosis, temp_session_dir, mock_console):
        """Test cancelling end session."""
        mock_confirm.return_value = False

        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)
        result = handler.end_session()

        assert result is True  # Should continue session

    def test_handle_action_routing(self, sample_diagnosis, temp_session_dir, mock_console):
        """Test that handle_action routes to correct methods."""
        handler = DiagnosisActionHandler(sample_diagnosis, temp_session_dir, mock_console)

        # Patch the individual methods
        with patch.object(handler, 'show_proposed_patch', return_value=True) as mock_patch, \
             patch.object(handler, 'open_in_editor', return_value=True) as mock_editor, \
             patch.object(handler, 'save_to_file', return_value=True) as mock_save, \
             patch.object(handler, 'end_session', return_value=False) as mock_end:

            handler.handle_action(1)
            mock_patch.assert_called_once()

            handler.handle_action(2)
            mock_editor.assert_called_once()

            handler.handle_action(3)
            mock_save.assert_called_once()

            handler.handle_action(4)
            mock_end.assert_called_once()


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_display_diagnosis(self, sample_diagnosis, mock_console):
        """Test display_diagnosis convenience function."""
        display_diagnosis(sample_diagnosis, console=mock_console, show_action_menu=False)
        assert mock_console.print.called

    def test_export_diagnosis_to_markdown(self, sample_diagnosis, tmp_path):
        """Test export_diagnosis_to_markdown convenience function."""
        output_path = tmp_path / "convenience_test.md"
        export_diagnosis_to_markdown(sample_diagnosis, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "Root Cause Analysis" in content

    @patch('aletheia.ui.menu.Menu.show_simple')
    def test_handle_diagnosis_actions(self, mock_show_simple, sample_diagnosis, temp_session_dir, mock_console):
        """Test handle_diagnosis_actions convenience function."""
        # Simulate choosing "End session"
        mock_show_simple.return_value = "End session"

        with patch('aletheia.ui.confirmation.ConfirmationManager.confirm', return_value=True):
            handle_diagnosis_actions(sample_diagnosis, temp_session_dir, mock_console)

        # Should have prompted for action
        mock_show_simple.assert_called()


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_diagnosis_with_missing_fields(self, diagnosis_formatter, mock_console):
        """Test handling diagnosis with missing fields."""
        incomplete = {
            "root_cause": {
                # Missing confidence
                "description": "Test"
            }
            # Missing recommended_actions
        }

        # Should not raise error
        diagnosis_formatter.display_diagnosis(incomplete, show_action_menu=False)
        assert mock_console.print.called

    def test_diagnosis_with_unknown_priority(self, diagnosis_formatter, tmp_path):
        """Test handling unknown priority level."""
        diagnosis = {
            "root_cause": {"type": "test", "confidence": 0.8, "description": "Test"},
            "recommended_actions": [
                {"priority": "CRITICAL", "action": "Do something"}  # Unknown priority
            ]
        }

        output_path = tmp_path / "unknown_priority.md"
        diagnosis_formatter.export_to_markdown(diagnosis, output_path)

        content = output_path.read_text()
        # Should default to LOW priority
        assert "Do something" in content

    def test_empty_recommended_actions(self, diagnosis_formatter, tmp_path):
        """Test diagnosis with empty actions list."""
        diagnosis = {
            "root_cause": {"type": "test", "confidence": 0.8, "description": "Test"},
            "recommended_actions": []
        }

        output_path = tmp_path / "no_actions.md"
        diagnosis_formatter.export_to_markdown(diagnosis, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        # Should still create valid markdown
        assert "# Root Cause Analysis Report" in content

    def test_multiline_description(self, diagnosis_formatter, tmp_path):
        """Test handling multiline descriptions."""
        diagnosis = {
            "root_cause": {
                "type": "complex_issue",
                "confidence": 0.75,
                "description": "This is a multiline\ndescription that spans\nmultiple lines."
            },
            "recommended_actions": []
        }

        output_path = tmp_path / "multiline.md"
        diagnosis_formatter.export_to_markdown(diagnosis, output_path)

        content = output_path.read_text()
        assert "multiline" in content
        assert "multiple lines" in content

    def test_special_characters_in_diagnosis(self, diagnosis_formatter, tmp_path):
        """Test handling special characters."""
        diagnosis = {
            "root_cause": {
                "type": "test",
                "confidence": 0.8,
                "description": "Contains special chars: <>&\"'"
            },
            "recommended_actions": [
                {"priority": "high", "action": "Fix the <problem> & verify"}
            ]
        }

        output_path = tmp_path / "special_chars.md"
        diagnosis_formatter.export_to_markdown(diagnosis, output_path)

        content = output_path.read_text()
        # Special characters should be preserved
        assert "<problem>" in content
        assert "&" in content
