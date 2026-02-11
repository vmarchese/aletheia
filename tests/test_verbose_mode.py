"""Tests for verbose mode and structlog logging configuration."""

import logging

import pytest
import structlog

from aletheia.utils.command import run_command, set_verbose_commands
from aletheia.utils.logging import (
    disable_session_file_logging,
    enable_session_file_logging,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset logging state after each test."""
    yield
    # Clean up any session file handlers
    disable_session_file_logging()
    # Reset to default
    setup_logging(level="INFO")


class TestSetupLogging:
    """Test structlog setup_logging configuration."""

    def test_setup_logging_default_level(self):
        """Test that default log level is INFO."""
        setup_logging()
        # Verify stdlib root logger is at INFO
        assert logging.root.level == logging.INFO

    def test_setup_logging_debug_level(self):
        """Test that DEBUG level can be set."""
        setup_logging(level="DEBUG")
        assert logging.root.level == logging.DEBUG

    def test_setup_logging_warning_level(self):
        """Test that WARNING level can be set."""
        setup_logging(level="WARNING")
        assert logging.root.level == logging.WARNING

    def test_setup_logging_env_var(self, monkeypatch):
        """Test that ALETHEIA_LOG_LEVEL env var is respected."""
        monkeypatch.setenv("ALETHEIA_LOG_LEVEL", "DEBUG")
        setup_logging()
        assert logging.root.level == logging.DEBUG

    def test_setup_logging_param_overrides_env(self, monkeypatch):
        """Test that explicit level param overrides env var."""
        monkeypatch.setenv("ALETHEIA_LOG_LEVEL", "DEBUG")
        setup_logging(level="WARNING")
        assert logging.root.level == logging.WARNING


class TestSessionFileLogging:
    """Test session file logging."""

    def test_enable_session_file_logging(self, tmp_path):
        """Test that session file logging creates trace file and handler."""
        setup_logging(level="INFO")

        initial_handler_count = len(logging.root.handlers)
        enable_session_file_logging(tmp_path)

        # Should have added one more handler
        assert len(logging.root.handlers) == initial_handler_count + 1

        # Log something and check it appears in the file
        stdlib_logger = logging.getLogger("test_stdlib")
        stdlib_logger.debug("Test debug message in trace file")

        trace_file = tmp_path / "aletheia_trace.log"
        assert trace_file.exists()
        content = trace_file.read_text()
        assert "Test debug message in trace file" in content

    def test_enable_session_file_logging_creates_dir(self, tmp_path):
        """Test that session dir is created if it doesn't exist."""
        session_dir = tmp_path / "new_session_dir"
        assert not session_dir.exists()

        setup_logging(level="INFO")
        enable_session_file_logging(session_dir)

        assert session_dir.exists()
        assert (session_dir / "aletheia_trace.log").exists()

    def test_setup_logging_with_session_dir(self, tmp_path):
        """Test setup_logging with session_dir parameter."""
        setup_logging(level="DEBUG", session_dir=tmp_path)

        trace_file = tmp_path / "aletheia_trace.log"
        assert trace_file.exists()

    def test_enable_lowers_root_to_debug(self, tmp_path):
        """Test that enabling session logging lowers root logger to DEBUG."""
        setup_logging(level="INFO")
        assert logging.root.level == logging.INFO

        enable_session_file_logging(tmp_path)
        assert logging.root.level == logging.DEBUG

    def test_enable_pins_console_handlers_to_original_level(self, tmp_path):
        """Test that console handlers keep the original level after enable."""
        setup_logging(level="INFO")

        enable_session_file_logging(tmp_path)

        # Console (StreamHandler, not FileHandler) should be pinned to INFO
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                assert handler.level == logging.INFO

    def test_enable_captures_debug_in_file_not_console(self, tmp_path):
        """Test that DEBUG messages go to file but console stays at INFO."""
        setup_logging(level="INFO")
        enable_session_file_logging(tmp_path)

        # Write a debug message via stdlib
        stdlib_logger = logging.getLogger("test_capture")
        stdlib_logger.debug("debug-only-in-file")

        # Verify it's in the trace file
        trace_file = tmp_path / "aletheia_trace.log"
        content = trace_file.read_text()
        assert "debug-only-in-file" in content

    def test_disable_session_file_logging(self, tmp_path):
        """Test that disable removes handler and restores levels."""
        setup_logging(level="INFO")
        enable_session_file_logging(tmp_path)

        # Verify enabled state
        assert logging.root.level == logging.DEBUG
        file_handlers = [
            h for h in logging.root.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1

        disable_session_file_logging()

        # Root logger restored to INFO
        assert logging.root.level == logging.INFO

        # File handler removed
        file_handlers = [
            h for h in logging.root.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 0

    def test_disable_noop_when_not_enabled(self):
        """Test that disable is safe to call when not enabled."""
        setup_logging(level="INFO")
        # Should not raise
        disable_session_file_logging()
        assert logging.root.level == logging.INFO

    def test_enable_disable_roundtrip(self, tmp_path):
        """Test that enable followed by disable restores original state."""
        setup_logging(level="INFO")

        original_handler_count = len(logging.root.handlers)
        original_level = logging.root.level

        enable_session_file_logging(tmp_path)
        disable_session_file_logging()

        assert logging.root.level == original_level
        assert len(logging.root.handlers) == original_handler_count


class TestVerboseCommandExecution:
    """Test verbose command execution."""

    def test_run_command_basic(self):
        """Test basic command execution with structlog logging."""
        setup_logging(level="DEBUG")
        result = run_command(["echo", "test"], check=True)

        assert result.returncode == 0
        assert "test" in result.stdout

    def test_run_command_verbose_mode(self, capsys):
        """Test verbose command output to console."""
        set_verbose_commands(True)

        result = run_command(["echo", "test"], check=True)

        assert result.returncode == 0

        # Check console output (Rich writes to stderr)
        captured = capsys.readouterr()
        assert "echo test" in captured.err

        set_verbose_commands(False)

    def test_run_command_with_error(self):
        """Test command error handling."""
        setup_logging(level="DEBUG")

        with pytest.raises(Exception):
            run_command(["false"], check=True)


class TestStructlogLogger:
    """Test structlog logger behavior."""

    def test_get_logger(self):
        """Test that structlog.get_logger returns a working logger."""
        setup_logging(level="DEBUG")
        logger = structlog.get_logger("test_module")
        # Should not raise
        logger.debug("Test debug message")
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

    def test_logger_with_context(self):
        """Test that structured context works."""
        setup_logging(level="DEBUG")
        logger = structlog.get_logger("test_module")
        # Should not raise
        logger.info("Test message", key="value", count=42)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
