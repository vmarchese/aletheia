"""Unit tests for input utilities."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime, timedelta
from aletheia.ui.input import (
    InputValidator,
    InputHandler,
    TimeWindowParser,
    create_input_handler
)


class TestInputValidator:
    """Tests for InputValidator class."""

    def test_validate_service_name_valid(self):
        """Test validation of valid service names."""
        validator = InputValidator()

        assert validator.validate_service_name("payments-svc")
        assert validator.validate_service_name("auth_service")
        assert validator.validate_service_name("api-gateway-v2")
        assert validator.validate_service_name("service123")

    def test_validate_service_name_invalid(self):
        """Test validation of invalid service names."""
        validator = InputValidator()

        assert not validator.validate_service_name("")
        assert not validator.validate_service_name("service with spaces")
        assert not validator.validate_service_name("service@domain")
        assert not validator.validate_service_name("service/path")

    def test_validate_time_window_valid(self):
        """Test validation of valid time windows."""
        validator = InputValidator()

        assert validator.validate_time_window("2h")
        assert validator.validate_time_window("30m")
        assert validator.validate_time_window("1d")
        assert validator.validate_time_window("24H")  # Case insensitive

    def test_validate_time_window_invalid(self):
        """Test validation of invalid time windows."""
        validator = InputValidator()

        assert not validator.validate_time_window("")
        assert not validator.validate_time_window("2hours")
        assert not validator.validate_time_window("30")
        assert not validator.validate_time_window("1w")  # Week not supported

    def test_validate_path_valid(self):
        """Test validation of valid paths."""
        validator = InputValidator()

        assert validator.validate_path("/tmp")
        assert validator.validate_path("~/test")
        assert validator.validate_path("/absolute/path")

    def test_validate_path_must_exist(self, tmp_path):
        """Test validation of paths that must exist."""
        validator = InputValidator()

        # Create a temporary file
        test_file = tmp_path / "test.txt"
        test_file.touch()

        assert validator.validate_path(str(test_file), must_exist=True)
        assert not validator.validate_path(str(tmp_path / "nonexistent"), must_exist=True)

    def test_validate_git_repository(self, tmp_path):
        """Test validation of git repositories."""
        validator = InputValidator()

        # Create fake git directory
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        assert validator.validate_git_repository(str(tmp_path))
        assert not validator.validate_git_repository(str(tmp_path / "nonexistent"))

    def test_validate_url_valid(self):
        """Test validation of valid URLs."""
        validator = InputValidator()

        assert validator.validate_url("http://example.com")
        assert validator.validate_url("https://example.com")
        assert validator.validate_url("https://api.example.com:8080/path")
        assert validator.validate_url("http://localhost:3000")

    def test_validate_url_invalid(self):
        """Test validation of invalid URLs."""
        validator = InputValidator()

        assert not validator.validate_url("")
        assert not validator.validate_url("not a url")
        assert not validator.validate_url("ftp://example.com")
        assert not validator.validate_url("example.com")

    def test_validate_port_valid(self):
        """Test validation of valid port numbers."""
        validator = InputValidator()

        assert validator.validate_port("80")
        assert validator.validate_port("443")
        assert validator.validate_port("8080")
        assert validator.validate_port("1")
        assert validator.validate_port("65535")

    def test_validate_port_invalid(self):
        """Test validation of invalid port numbers."""
        validator = InputValidator()

        assert not validator.validate_port("0")
        assert not validator.validate_port("65536")
        assert not validator.validate_port("-1")
        assert not validator.validate_port("abc")
        assert not validator.validate_port("")

    def test_validate_namespace_valid(self):
        """Test validation of valid Kubernetes namespaces."""
        validator = InputValidator()

        assert validator.validate_namespace("default")
        assert validator.validate_namespace("kube-system")
        assert validator.validate_namespace("my-namespace")
        assert validator.validate_namespace("ns-123")

    def test_validate_namespace_invalid(self):
        """Test validation of invalid Kubernetes namespaces."""
        validator = InputValidator()

        assert not validator.validate_namespace("")
        assert not validator.validate_namespace("UPPERCASE")
        assert not validator.validate_namespace("name_space")
        assert not validator.validate_namespace("-start-hyphen")
        assert not validator.validate_namespace("end-hyphen-")
        assert not validator.validate_namespace("a" * 64)  # Too long


class TestInputHandler:
    """Tests for InputHandler class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_console):
        """Create InputHandler with mock console."""
        return InputHandler(mock_console)

    def test_input_handler_creation(self):
        """Test InputHandler initialization."""
        handler = InputHandler()
        assert handler.console is not None
        assert isinstance(handler.validator, InputValidator)

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_text_simple(self, mock_ask, handler):
        """Test getting simple text input."""
        mock_ask.return_value = "test input"

        result = handler.get_text("Enter something")

        assert result == "test input"
        mock_ask.assert_called_once()

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_text_with_default(self, mock_ask, handler):
        """Test getting text input with default."""
        mock_ask.return_value = "default value"

        result = handler.get_text("Enter something", default="default value")

        assert result == "default value"

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_text_with_validation(self, mock_ask, handler):
        """Test getting text input with validation."""
        mock_ask.side_effect = ["invalid", "valid"]

        def validator(value):
            return value == "valid"

        result = handler.get_text(
            "Enter something",
            validator=validator,
            error_message="Must be 'valid'"
        )

        assert result == "valid"
        assert mock_ask.call_count == 2

    @patch('getpass.getpass')
    def test_get_password(self, mock_getpass, handler):
        """Test getting password input."""
        mock_getpass.return_value = "secret123"

        result = handler.get_password()

        assert result == "secret123"
        mock_getpass.assert_called_once()

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_service_name(self, mock_ask, handler):
        """Test getting validated service name."""
        mock_ask.return_value = "payments-svc"

        result = handler.get_service_name()

        assert result == "payments-svc"

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_time_window(self, mock_ask, handler):
        """Test getting validated time window."""
        mock_ask.return_value = "2h"

        result = handler.get_time_window()

        assert result == "2h"

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_path(self, mock_ask, handler, tmp_path):
        """Test getting validated path."""
        test_path = tmp_path / "test"
        test_path.mkdir()
        mock_ask.return_value = str(test_path)

        result = handler.get_path(must_exist=True)

        assert result == test_path

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_repository_path(self, mock_ask, handler, tmp_path):
        """Test getting validated repository path."""
        # Create fake git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        mock_ask.return_value = str(tmp_path)

        result = handler.get_repository_path()

        assert result == tmp_path

    @patch('builtins.input')
    def test_get_multiline_text(self, mock_input, handler):
        """Test getting multiline text input."""
        mock_input.side_effect = ["line 1", "line 2", "line 3", "END"]

        result = handler.get_multiline_text("Enter text")

        assert result == "line 1\nline 2\nline 3"

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_url(self, mock_ask, handler):
        """Test getting validated URL."""
        mock_ask.return_value = "https://example.com"

        result = handler.get_url()

        assert result == "https://example.com"

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_port(self, mock_ask, handler):
        """Test getting validated port number."""
        mock_ask.return_value = "8080"

        result = handler.get_port()

        assert result == 8080
        assert isinstance(result, int)

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_namespace(self, mock_ask, handler):
        """Test getting validated namespace."""
        mock_ask.return_value = "my-namespace"

        result = handler.get_namespace()

        assert result == "my-namespace"

    @patch('builtins.input')
    def test_confirm_yes(self, mock_input, handler):
        """Test confirmation with yes response."""
        mock_input.return_value = "y"

        result = handler.confirm("Are you sure?")

        assert result is True

    @patch('builtins.input')
    def test_confirm_no(self, mock_input, handler):
        """Test confirmation with no response."""
        mock_input.return_value = "n"

        result = handler.confirm("Are you sure?")

        assert result is False

    @patch('builtins.input')
    def test_confirm_default(self, mock_input, handler):
        """Test confirmation with default response."""
        mock_input.return_value = ""

        result = handler.confirm("Are you sure?", default=True)

        assert result is True

    @patch('builtins.input')
    def test_confirm_keyboard_interrupt(self, mock_input, handler):
        """Test confirmation keyboard interrupt."""
        mock_input.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            handler.confirm("Are you sure?")


class TestTimeWindowParser:
    """Tests for TimeWindowParser class."""

    def test_parse_minutes(self):
        """Test parsing minute time windows."""
        start, end = TimeWindowParser.parse("30m")

        delta = end - start
        assert abs(delta.total_seconds() - 1800) < 1  # 30 minutes

    def test_parse_hours(self):
        """Test parsing hour time windows."""
        start, end = TimeWindowParser.parse("2h")

        delta = end - start
        assert abs(delta.total_seconds() - 7200) < 1  # 2 hours

    def test_parse_days(self):
        """Test parsing day time windows."""
        start, end = TimeWindowParser.parse("1d")

        delta = end - start
        assert abs(delta.total_seconds() - 86400) < 1  # 1 day

    def test_parse_case_insensitive(self):
        """Test case insensitive parsing."""
        start1, end1 = TimeWindowParser.parse("2h")
        start2, end2 = TimeWindowParser.parse("2H")

        delta1 = end1 - start1
        delta2 = end2 - start2
        assert abs(delta1.total_seconds() - delta2.total_seconds()) < 1

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError):
            TimeWindowParser.parse("invalid")

        with pytest.raises(ValueError):
            TimeWindowParser.parse("2w")

    def test_to_seconds(self):
        """Test converting time window to seconds."""
        assert TimeWindowParser.to_seconds("30m") == 1800
        assert TimeWindowParser.to_seconds("2h") == 7200
        assert TimeWindowParser.to_seconds("1d") == 86400

    def test_parse_returns_recent_time(self):
        """Test that parse returns recent times."""
        start, end = TimeWindowParser.parse("1h")

        now = datetime.now()
        # End should be very close to now
        assert abs((end - now).total_seconds()) < 2

        # Start should be about 1 hour ago
        expected_start = now - timedelta(hours=1)
        assert abs((start - expected_start).total_seconds()) < 2


def test_create_input_handler_factory():
    """Test create_input_handler factory function."""
    handler = create_input_handler()
    assert isinstance(handler, InputHandler)
    assert handler.console is not None


class TestInputEdgeCases:
    """Tests for input edge cases and robustness."""

    def test_validate_service_name_edge_cases(self):
        """Test service name validation with edge cases."""
        validator = InputValidator()

        # Very long name
        assert validator.validate_service_name("a" * 253)

        # Single character
        assert validator.validate_service_name("a")

        # All hyphens and underscores
        assert validator.validate_service_name("_-_-_")

    def test_validate_path_with_tilde(self, tmp_path):
        """Test path validation with tilde expansion."""
        validator = InputValidator()

        # Test tilde path (always valid as syntax)
        assert validator.validate_path("~/test")

    def test_validate_path_relative(self, tmp_path):
        """Test validation of relative paths."""
        validator = InputValidator()
        
        # Create a test file in current directory
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            # Now relative paths from here should work
            assert validator.validate_path("./test")
            assert validator.validate_path("test.txt")
        finally:
            os.chdir(old_cwd)

    def test_validate_git_repository_not_exists(self):
        """Test git repository validation with non-existent path."""
        validator = InputValidator()

        assert not validator.validate_git_repository("/nonexistent/path")

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_text_keyboard_interrupt(self, mock_ask, tmp_path):
        """Test keyboard interrupt during text input."""
        mock_ask.side_effect = KeyboardInterrupt()

        handler = InputHandler()
        with pytest.raises(KeyboardInterrupt):
            handler.get_text("Test prompt")

    @patch('builtins.input')
    def test_get_multiline_keyboard_interrupt(self, mock_input, tmp_path):
        """Test keyboard interrupt during multiline input."""
        mock_input.side_effect = KeyboardInterrupt()

        handler = InputHandler()
        with pytest.raises(KeyboardInterrupt):
            handler.get_multiline_text("Test prompt")

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_text_empty_with_validator(self, mock_ask):
        """Test empty input with validator."""
        mock_ask.side_effect = ["", "valid"]

        def not_empty(value):
            return bool(value.strip())

        handler = InputHandler()
        result = handler.get_text(
            "Enter something",
            validator=not_empty,
            error_message="Cannot be empty"
        )

        assert result == "valid"
        assert mock_ask.call_count == 2

    def test_time_window_parser_large_values(self):
        """Test parsing large time window values."""
        start, end = TimeWindowParser.parse("999h")
        delta = end - start
        assert abs(delta.total_seconds() - (999 * 3600)) < 1

        start, end = TimeWindowParser.parse("365d")
        delta = end - start
        assert abs(delta.total_seconds() - (365 * 86400)) < 1

    def test_time_window_to_seconds_edge_cases(self):
        """Test converting edge case time windows to seconds."""
        assert TimeWindowParser.to_seconds("1m") == 60
        assert TimeWindowParser.to_seconds("1h") == 3600
        assert TimeWindowParser.to_seconds("1d") == 86400

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_service_name_retry_on_invalid(self, mock_ask):
        """Test service name input retry on invalid input."""
        mock_ask.side_effect = ["invalid name", "valid-name"]

        handler = InputHandler()
        result = handler.get_service_name()

        assert result == "valid-name"
        assert mock_ask.call_count == 2

    @patch('aletheia.ui.input.Prompt.ask')
    def test_get_time_window_retry_on_invalid(self, mock_ask):
        """Test time window input retry on invalid input."""
        mock_ask.side_effect = ["invalid", "2h"]

        handler = InputHandler()
        result = handler.get_time_window()

        assert result == "2h"
        assert mock_ask.call_count == 2

    @patch('builtins.input')
    def test_get_multiline_text_empty_lines(self, mock_input):
        """Test multiline input with empty lines."""
        mock_input.side_effect = ["line 1", "", "line 3", "END"]

        handler = InputHandler()
        result = handler.get_multiline_text("Enter text")

        assert result == "line 1\n\nline 3"

    @patch('builtins.input')
    def test_get_multiline_text_custom_marker(self, mock_input):
        """Test multiline input with custom end marker."""
        mock_input.side_effect = ["line 1", "line 2", "STOP"]

        handler = InputHandler()
        result = handler.get_multiline_text("Enter text", end_marker="STOP")

        assert result == "line 1\nline 2"
