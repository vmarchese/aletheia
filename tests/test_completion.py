"""
Tests for command completion functionality.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest
from prompt_toolkit.document import Document

from aletheia.commands import COMMANDS
from aletheia.completion import CommandCompleter
from aletheia.config import Config


@pytest.fixture
def mock_config() -> Config:
    """Create a mock config for testing."""
    with TemporaryDirectory() as temp_dir:
        config = Mock(spec=Config)
        config.commands_directory = temp_dir
        yield config


@pytest.fixture
def completer(mock_config: Config) -> CommandCompleter:
    """Create a CommandCompleter instance for testing."""
    return CommandCompleter(mock_config)


def test_completer_initialization(mock_config: Config) -> None:
    """Test that completer initializes correctly."""
    completer = CommandCompleter(mock_config)
    assert completer.config == mock_config
    assert completer._commands_cache is None


def test_get_all_commands_built_in_only(completer: CommandCompleter) -> None:
    """Test getting all commands when only built-in commands exist."""
    commands = completer._get_all_commands()

    # Check that built-in commands are present
    assert "help" in commands
    assert "version" in commands
    assert "info" in commands
    assert "cost" in commands

    # Verify descriptions
    assert commands["help"] == COMMANDS["help"].description
    assert commands["version"] == COMMANDS["version"].description


def test_get_all_commands_with_custom_commands(mock_config: Config) -> None:
    """Test getting all commands including custom commands."""
    # Create a custom command file
    commands_dir = Path(mock_config.commands_directory)
    custom_cmd_file = commands_dir / "test-command.md"
    custom_cmd_file.write_text(
        """---
name: Test Command
description: A test custom command
---
This is a test command for unit testing.
"""
    )

    completer = CommandCompleter(mock_config)
    commands = completer._get_all_commands()

    # Check built-in commands
    assert "help" in commands

    # Check custom command
    assert "test-command" in commands
    assert "Test Command" in commands["test-command"]
    assert "A test custom command" in commands["test-command"]


def test_commands_cache(completer: CommandCompleter) -> None:
    """Test that commands are cached after first retrieval."""
    # First call should populate cache
    commands1 = completer._get_all_commands()
    assert completer._commands_cache is not None

    # Second call should return cached version
    commands2 = completer._get_all_commands()
    assert commands1 is commands2  # Same object reference


def test_refresh_cache(completer: CommandCompleter) -> None:
    """Test cache refresh functionality."""
    # Populate cache
    completer._get_all_commands()
    assert completer._commands_cache is not None

    # Refresh cache
    completer.refresh_cache()
    assert completer._commands_cache is None


def test_completion_no_slash(completer: CommandCompleter) -> None:
    """Test that no completions are provided when input doesn't start with /."""
    document = Document("hello")
    completions = list(completer.get_completions(document, None))

    assert len(completions) == 0


def test_completion_with_slash_only(completer: CommandCompleter) -> None:
    """Test completions when only / is typed."""
    document = Document("/")
    completions = list(completer.get_completions(document, None))

    # Should return all commands
    assert len(completions) == len(COMMANDS)

    # Check that help command is present
    help_completions = [c for c in completions if c.text == "help"]
    assert len(help_completions) == 1
    assert help_completions[0].text == "help"


def test_completion_filtering(completer: CommandCompleter) -> None:
    """Test that completions are filtered based on typed text."""
    document = Document("/he")
    completions = list(completer.get_completions(document, None))

    # Should only return 'help' command
    assert len(completions) == 1
    assert completions[0].text == "help"


def test_completion_case_insensitive(completer: CommandCompleter) -> None:
    """Test that completion filtering is case-insensitive."""
    document = Document("/HE")
    completions = list(completer.get_completions(document, None))

    # Should still return 'help' command
    assert len(completions) == 1
    assert completions[0].text == "help"


def test_completion_no_match(completer: CommandCompleter) -> None:
    """Test that no completions are returned for non-matching input."""
    document = Document("/xyz")
    completions = list(completer.get_completions(document, None))

    assert len(completions) == 0


def test_completion_start_position(completer: CommandCompleter) -> None:
    """Test that completion start position is calculated correctly."""
    document = Document("/hel")
    completions = list(completer.get_completions(document, None))

    assert len(completions) == 1
    # Start position should be negative length of typed command part
    assert completions[0].start_position == -3  # Length of "hel"


def test_completion_with_custom_command(mock_config: Config) -> None:
    """Test completions include custom commands."""
    # Create a custom command
    commands_dir = Path(mock_config.commands_directory)
    custom_cmd_file = commands_dir / "analyze.md"
    custom_cmd_file.write_text(
        """---
name: Analyze
description: Analyze system logs
---
Perform deep analysis of system logs.
"""
    )

    completer = CommandCompleter(mock_config)
    document = Document("/an")
    completions = list(completer.get_completions(document, None))

    # Should include the custom 'analyze' command
    analyze_completions = [c for c in completions if c.text == "analyze"]
    assert len(analyze_completions) == 1
    # The display_meta should contain the custom command description
    assert analyze_completions[0].display_meta is not None


def test_completion_sorted_alphabetically(completer: CommandCompleter) -> None:
    """Test that completions are returned in alphabetical order."""
    document = Document("/")
    completions = list(completer.get_completions(document, None))

    command_names = [c.text for c in completions]
    assert command_names == sorted(command_names)


def test_completion_with_malformed_custom_command(mock_config: Config) -> None:
    """Test that malformed custom commands don't break completion."""
    # Create a malformed custom command file
    commands_dir = Path(mock_config.commands_directory)
    bad_cmd_file = commands_dir / "bad.md"
    bad_cmd_file.write_text("Just some text without frontmatter")

    completer = CommandCompleter(mock_config)

    # Should still work and return built-in commands
    document = Document("/he")
    completions = list(completer.get_completions(document, None))

    assert len(completions) >= 1  # At least 'help' should be present
