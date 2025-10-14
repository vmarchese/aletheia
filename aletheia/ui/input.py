"""
Input utilities for gathering user information.

Provides text input, password input, time window parsing, and path validation.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime, timedelta
from rich.console import Console
from rich.prompt import Prompt


class InputValidator:
    """Validates user input."""

    @staticmethod
    def validate_service_name(name: str) -> bool:
        """
        Validate service name format.

        Args:
            name: Service name to validate

        Returns:
            True if valid, False otherwise
        """
        # Allow alphanumeric, hyphens, underscores
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, name)) and len(name) > 0

    @staticmethod
    def validate_time_window(window: str) -> bool:
        """
        Validate time window format (e.g., "2h", "30m", "1d").

        Args:
            window: Time window string

        Returns:
            True if valid, False otherwise
        """
        pattern = r'^\d+[mhd]$'
        return bool(re.match(pattern, window.lower()))

    @staticmethod
    def validate_path(path_str: str, must_exist: bool = False) -> bool:
        """
        Validate file or directory path.

        Args:
            path_str: Path string to validate
            must_exist: Whether the path must exist

        Returns:
            True if valid, False otherwise
        """
        try:
            path = Path(path_str).expanduser()
            if must_exist:
                return path.exists()
            # Check if parent directory exists for new files
            return path.parent.exists() or path.is_absolute()
        except (ValueError, OSError):
            return False

    @staticmethod
    def validate_git_repository(path_str: str) -> bool:
        """
        Validate that path is a git repository.

        Args:
            path_str: Path to validate

        Returns:
            True if valid git repository, False otherwise
        """
        try:
            path = Path(path_str).expanduser()
            git_dir = path / ".git"
            return git_dir.exists() and git_dir.is_dir()
        except (ValueError, OSError):
            return False


class InputHandler:
    """Handles user input with validation and formatting."""

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize input handler.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()
        self.validator = InputValidator()

    def get_text(
        self,
        prompt: str,
        default: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
        error_message: str = "Invalid input. Please try again."
    ) -> str:
        """
        Get validated text input from user.

        Args:
            prompt: Prompt message to display
            default: Default value
            validator: Optional validation function
            error_message: Error message for invalid input

        Returns:
            Validated user input
        """
        while True:
            try:
                value = Prompt.ask(
                    f"[bold cyan][Aletheia][/bold cyan] {prompt}",
                    default=default,
                    console=self.console
                )

                if validator and not validator(value):
                    self.console.print(f"[red]{error_message}[/red]")
                    continue

                return value

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled[/yellow]")
                raise

    def get_password(self, prompt: str = "Enter password") -> str:
        """
        Get password input (hidden).

        Args:
            prompt: Prompt message to display

        Returns:
            Password string
        """
        from getpass import getpass

        self.console.print(f"[bold cyan][Aletheia][/bold cyan] {prompt}:")
        return getpass()

    def get_service_name(
        self,
        prompt: str = "Enter service name",
        default: Optional[str] = None
    ) -> str:
        """
        Get validated service name.

        Args:
            prompt: Prompt message to display
            default: Default service name

        Returns:
            Validated service name
        """
        return self.get_text(
            prompt,
            default=default,
            validator=self.validator.validate_service_name,
            error_message="Invalid service name. Use only letters, numbers, hyphens, and underscores."
        )

    def get_time_window(
        self,
        prompt: str = "Enter time window (e.g., 2h, 30m, 1d)",
        default: str = "2h"
    ) -> str:
        """
        Get validated time window.

        Args:
            prompt: Prompt message to display
            default: Default time window

        Returns:
            Validated time window string
        """
        return self.get_text(
            prompt,
            default=default,
            validator=self.validator.validate_time_window,
            error_message="Invalid time window format. Use format like '2h', '30m', or '1d'."
        )

    def get_path(
        self,
        prompt: str = "Enter path",
        default: Optional[str] = None,
        must_exist: bool = False
    ) -> Path:
        """
        Get validated file or directory path.

        Args:
            prompt: Prompt message to display
            default: Default path
            must_exist: Whether path must exist

        Returns:
            Validated Path object
        """
        def validator(path_str: str) -> bool:
            return self.validator.validate_path(path_str, must_exist)

        error_msg = "Path does not exist." if must_exist else "Invalid path."

        path_str = self.get_text(
            prompt,
            default=default,
            validator=validator,
            error_message=error_msg
        )

        return Path(path_str).expanduser()

    def get_repository_path(
        self,
        prompt: str = "Enter repository path",
        default: Optional[str] = None
    ) -> Path:
        """
        Get validated git repository path.

        Args:
            prompt: Prompt message to display
            default: Default repository path

        Returns:
            Validated repository Path object
        """
        path_str = self.get_text(
            prompt,
            default=default,
            validator=self.validator.validate_git_repository,
            error_message="Not a valid git repository. Please provide a path to a git repository."
        )

        return Path(path_str).expanduser()

    def get_multiline_text(
        self,
        prompt: str,
        end_marker: str = "END"
    ) -> str:
        """
        Get multiline text input from user.

        Args:
            prompt: Prompt message to display
            end_marker: Marker to end input (e.g., "END", "EOF")

        Returns:
            Multiline text string
        """
        self.console.print(f"[bold cyan][Aletheia][/bold cyan] {prompt}")
        self.console.print(f"[dim](Type '{end_marker}' on a new line to finish)[/dim]")

        lines = []
        try:
            while True:
                line = input()
                if line.strip() == end_marker:
                    break
                lines.append(line)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Operation cancelled[/yellow]")
            raise

        return "\n".join(lines)


class TimeWindowParser:
    """Parses time window strings into datetime objects."""

    @staticmethod
    def parse(window: str) -> tuple[datetime, datetime]:
        """
        Parse time window string into start and end datetimes.

        Args:
            window: Time window string (e.g., "2h", "30m", "1d")

        Returns:
            Tuple of (start_datetime, end_datetime)

        Raises:
            ValueError: If window format is invalid
        """
        match = re.match(r'^(\d+)([mhd])$', window.lower())
        if not match:
            raise ValueError(f"Invalid time window format: {window}")

        amount = int(match.group(1))
        unit = match.group(2)

        # Calculate delta
        if unit == 'm':
            delta = timedelta(minutes=amount)
        elif unit == 'h':
            delta = timedelta(hours=amount)
        elif unit == 'd':
            delta = timedelta(days=amount)
        else:
            raise ValueError(f"Invalid time unit: {unit}")

        # Calculate start and end times
        end_time = datetime.now()
        start_time = end_time - delta

        return start_time, end_time

    @staticmethod
    def to_seconds(window: str) -> int:
        """
        Convert time window to seconds.

        Args:
            window: Time window string (e.g., "2h", "30m", "1d")

        Returns:
            Number of seconds

        Raises:
            ValueError: If window format is invalid
        """
        start_time, end_time = TimeWindowParser.parse(window)
        return int((end_time - start_time).total_seconds())


def create_input_handler(console: Optional[Console] = None) -> InputHandler:
    """
    Factory function to create an InputHandler instance.

    Args:
        console: Optional Rich console instance

    Returns:
        InputHandler instance
    """
    return InputHandler(console)
