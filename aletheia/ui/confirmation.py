"""
Confirmation prompt system with configurable verbosity levels.

Supports verbose, normal, and minimal confirmation modes.
"""

from __future__ import annotations
from typing import Literal, Optional
from rich.console import Console
from rich.prompt import Confirm


ConfirmationLevel = Literal["verbose", "normal", "minimal"]


class ConfirmationManager:
    """Manages confirmation prompts based on configured level."""

    def __init__(
        self,
        level: ConfirmationLevel = "normal",
        console: Optional[Console] = None
    ):
        """
        Initialize confirmation manager.

        Args:
            level: Confirmation level (verbose, normal, minimal)
            console: Rich console instance (creates new one if not provided)
        """
        self.level = level
        self.console = console or Console()

    def set_level(self, level: ConfirmationLevel) -> None:
        """
        Change confirmation level.

        Args:
            level: New confirmation level
        """
        self.level = level

    def confirm(
        self,
        message: str,
        category: Literal["data_fetch", "repository_access", "analysis", "destructive"] = "data_fetch",
        default: bool = True
    ) -> bool:
        """
        Show confirmation prompt based on level and category.

        Args:
            message: Confirmation message to display
            category: Operation category affecting when to confirm
            default: Default value (True for Y/n, False for y/N)

        Returns:
            True if confirmed, False otherwise

        Confirmation behavior by level:
        - verbose: Confirm everything
        - normal: Confirm data_fetch, repository_access, destructive
        - minimal: Confirm only destructive operations
        """
        # Determine if confirmation is needed
        should_confirm = self._should_confirm(category)

        if not should_confirm:
            # Auto-confirm based on default
            return default

        # Show confirmation prompt
        try:
            return Confirm.ask(
                f"[bold cyan][Aletheia][/bold cyan] {message}",
                default=default,
                console=self.console
            )
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Operation cancelled[/yellow]")
            return False

    def _should_confirm(self, category: str) -> bool:
        """
        Determine if confirmation is needed based on level and category.

        Args:
            category: Operation category

        Returns:
            True if confirmation should be shown
        """
        if self.level == "verbose":
            return True
        elif self.level == "normal":
            return category in ["data_fetch", "repository_access", "destructive"]
        elif self.level == "minimal":
            return category == "destructive"
        else:
            # Unknown level, default to normal behavior
            return category in ["data_fetch", "repository_access", "destructive"]

    def confirm_command(
        self,
        command: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Confirm before executing an external command (verbose mode only).

        Args:
            command: Command to be executed
            description: Optional description of what the command does

        Returns:
            True if confirmed, False otherwise
        """
        if self.level != "verbose":
            return True

        # Display command details
        self.console.print(f"\n[bold cyan][Aletheia][/bold cyan] About to execute:")
        self.console.print(f"  [yellow]{command}[/yellow]")
        if description:
            self.console.print(f"  [dim]{description}[/dim]")

        return self.confirm("Proceed?", category="data_fetch", default=True)

    def confirm_agent_transition(
        self,
        from_agent: str,
        to_agent: str
    ) -> bool:
        """
        Confirm before transitioning between agents (verbose mode only).

        Args:
            from_agent: Current agent name
            to_agent: Next agent name

        Returns:
            True if confirmed, False otherwise
        """
        if self.level != "verbose":
            return True

        message = f"Transition from [bold]{from_agent}[/bold] to [bold]{to_agent}[/bold]?"
        return self.confirm(message, category="analysis", default=True)

    def show_and_confirm(
        self,
        summary: str,
        details: Optional[str] = None,
        category: str = "data_fetch",
        default: bool = True
    ) -> bool:
        """
        Show information and request confirmation.

        Args:
            summary: Brief summary to always show
            details: Detailed information (shown in verbose mode only)
            category: Operation category
            default: Default confirmation value

        Returns:
            True if confirmed, False otherwise
        """
        # Always show summary
        self.console.print(f"\n[bold cyan][Aletheia][/bold cyan] {summary}")

        # Show details in verbose mode
        if self.level == "verbose" and details:
            self.console.print(f"[dim]{details}[/dim]")

        return self.confirm("Confirm?", category=category, default=default)


def create_confirmation_manager(
    level: ConfirmationLevel = "normal",
    console: Optional[Console] = None
) -> ConfirmationManager:
    """
    Factory function to create a ConfirmationManager instance.

    Args:
        level: Confirmation level
        console: Optional Rich console instance

    Returns:
        ConfirmationManager instance
    """
    return ConfirmationManager(level, console)
