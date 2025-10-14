"""
Menu system for guided mode interaction.

Provides numbered menu choices with validation and default values.
"""

from __future__ import annotations
from typing import List, Optional, TypeVar, Callable, Generic
from rich.console import Console
from rich.prompt import Prompt, IntPrompt

T = TypeVar('T')


class MenuItem:
    """Represents a single menu item."""

    def __init__(self, label: str, value: T, description: Optional[str] = None):
        """
        Initialize a menu item.

        Args:
            label: Display text for the menu item
            value: Value returned when this item is selected
            description: Optional detailed description
        """
        self.label = label
        self.value = value
        self.description = description


class Menu:
    """Menu display and selection handler."""

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize menu handler.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()

    def show(
        self,
        prompt: str,
        items: List[MenuItem[T]],
        default: Optional[int] = None,
        allow_back: bool = False
    ) -> T:
        """
        Display a numbered menu and get user selection.

        Args:
            prompt: Question or instruction to display
            items: List of menu items to choose from
            default: Default selection index (1-based)
            allow_back: Allow "back" or "0" to return None

        Returns:
            Selected item value

        Raises:
            ValueError: If menu is empty or selection is invalid
        """
        if not items:
            raise ValueError("Menu must have at least one item")

        # Display prompt
        self.console.print(f"\n[bold cyan][Aletheia][/bold cyan] {prompt}")

        # Display menu items
        for idx, item in enumerate(items, start=1):
            if item.description:
                self.console.print(f"{idx}. {item.label} - [dim]{item.description}[/dim]")
            else:
                self.console.print(f"{idx}. {item.label}")

        if allow_back:
            self.console.print("0. Back")

        # Get user input
        default_str = str(default) if default else None
        while True:
            try:
                choice_str = Prompt.ask(
                    "\n[bold cyan]>[/bold cyan]",
                    default=default_str,
                    show_default=bool(default_str)
                )

                choice = int(choice_str)

                # Check for "back"
                if allow_back and choice == 0:
                    return None

                # Validate range
                if 1 <= choice <= len(items):
                    return items[choice - 1].value
                else:
                    self.console.print(
                        f"[red]Please enter a number between 1 and {len(items)}[/red]"
                    )
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled[/yellow]")
                raise

    def show_simple(
        self,
        prompt: str,
        choices: List[str],
        default: Optional[int] = None
    ) -> str:
        """
        Display a simple menu with string choices.

        Args:
            prompt: Question or instruction to display
            choices: List of string choices
            default: Default selection index (1-based)

        Returns:
            Selected choice string
        """
        items = [MenuItem(label=choice, value=choice) for choice in choices]
        return self.show(prompt, items, default)

    def show_multiselect(
        self,
        prompt: str,
        items: List[MenuItem[T]],
        defaults: Optional[List[int]] = None
    ) -> List[T]:
        """
        Display a menu allowing multiple selections.

        Args:
            prompt: Question or instruction to display
            items: List of menu items to choose from
            defaults: Default selection indices (1-based)

        Returns:
            List of selected item values
        """
        if not items:
            raise ValueError("Menu must have at least one item")

        # Display prompt
        self.console.print(f"\n[bold cyan][Aletheia][/bold cyan] {prompt}")
        self.console.print("[dim]Enter comma-separated numbers (e.g., 1,3,4) or 'all'[/dim]")

        # Display menu items with checkmarks for defaults
        default_set = set(defaults or [])
        for idx, item in enumerate(items, start=1):
            marker = "[x]" if idx in default_set else "[ ]"
            if item.description:
                self.console.print(f"{marker} {idx}. {item.label} - [dim]{item.description}[/dim]")
            else:
                self.console.print(f"{marker} {idx}. {item.label}")

        # Get user input
        default_str = ",".join(map(str, defaults)) if defaults else None
        while True:
            try:
                choice_str = Prompt.ask(
                    "\n[bold cyan]>[/bold cyan]",
                    default=default_str,
                    show_default=bool(default_str)
                )

                # Handle "all" selection
                if choice_str.lower() == "all":
                    return [item.value for item in items]

                # Parse comma-separated choices
                choices = [int(c.strip()) for c in choice_str.split(",")]

                # Validate all choices
                invalid = [c for c in choices if c < 1 or c > len(items)]
                if invalid:
                    self.console.print(
                        f"[red]Invalid choices: {invalid}. Please enter numbers between 1 and {len(items)}[/red]"
                    )
                    continue

                # Return selected values
                return [items[c - 1].value for c in choices]

            except ValueError:
                self.console.print("[red]Please enter valid numbers separated by commas[/red]")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled[/yellow]")
                raise


def create_menu(console: Optional[Console] = None) -> Menu:
    """
    Factory function to create a Menu instance.

    Args:
        console: Optional Rich console instance

    Returns:
        Menu instance
    """
    return Menu(console)
