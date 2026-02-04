"""
Command completion support for Aletheia CLI using prompt_toolkit.

This module provides autocomplete functionality for slash commands,
including both built-in and custom commands.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

import structlog
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

from aletheia.commands import COMMANDS, get_custom_commands

if TYPE_CHECKING:
    from aletheia.config import Config

logger = structlog.get_logger(__name__)


class CommandCompleter(Completer):
    """
    Completer for Aletheia slash commands.

    Provides autocomplete suggestions when users type "/" in the CLI,
    showing both built-in commands and custom commands loaded from
    the commands directory.
    """

    def __init__(self, config: "Config") -> None:
        """
        Initialize the command completer.

        Args:
            config: Aletheia configuration object (needed to load custom commands)
        """
        self.config = config
        self._commands_cache: dict[str, str] | None = None

    def _get_all_commands(self) -> dict[str, str]:
        """
        Collect all available commands (built-in + custom).

        Returns:
            Dict mapping command name to description
        """
        if self._commands_cache is not None:
            return self._commands_cache

        all_commands: dict[str, str] = {}

        # Add built-in commands
        for name, cmd_obj in COMMANDS.items():
            all_commands[name] = cmd_obj.description

        # Add custom commands
        try:
            custom_cmds = get_custom_commands(self.config)
            for command_name, custom_cmd in custom_cmds.items():
                # Use the display name and description from frontmatter
                all_commands[command_name] = (
                    f"{custom_cmd.name}: {custom_cmd.description}"
                )
        except Exception as e:
            logger.warning(f"Failed to load custom commands for completion: {e}")

        # Cache the results
        self._commands_cache = all_commands
        logger.debug(f"Loaded {len(all_commands)} commands for completion")

        return all_commands

    def refresh_cache(self) -> None:
        """
        Refresh the command cache.

        Call this when custom commands may have changed.
        """
        self._commands_cache = None
        logger.debug("Command completion cache refreshed")

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """
        Generate completion suggestions for the current input.

        Args:
            document: Current document state from prompt_toolkit
            complete_event: Completion event (unused but required by interface)

        Yields:
            Completion objects for matching commands
        """
        text = document.text_before_cursor

        # Only provide completions if text starts with /
        if not text.startswith("/"):
            return

        # Extract the command part (everything after the /)
        command_part = text[1:].lower()

        # Get all available commands
        all_commands = self._get_all_commands()

        # Filter and yield matching commands
        for cmd_name, description in sorted(all_commands.items()):
            if cmd_name.lower().startswith(command_part):
                yield Completion(
                    text=cmd_name,
                    start_position=-len(command_part),
                    display=cmd_name,
                    display_meta=description,
                )
