"""
User interface components for Aletheia.

Provides menus, input handling, confirmations, and rich output formatting for conversational mode.
"""

from aletheia.ui.menu import Menu, MenuItem, create_menu
from aletheia.ui.input import (
    InputHandler,
    InputValidator,
    TimeWindowParser,
    create_input_handler
)
from aletheia.ui.confirmation import (
    ConfirmationManager,
    ConfirmationLevel,
    create_confirmation_manager
)
from aletheia.ui.output import OutputFormatter, create_output_formatter

__all__ = [
    # Menu system
    "Menu",
    "MenuItem",
    "create_menu",
    # Input handling
    "InputHandler",
    "InputValidator",
    "TimeWindowParser",
    "create_input_handler",
    # Confirmation system
    "ConfirmationManager",
    "ConfirmationLevel",
    "create_confirmation_manager",
    # Output formatting
    "OutputFormatter",
    "create_output_formatter",
]
