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

    @patch('aletheia.ui.input.getpass')
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
