"""Conversational UI formatting utilities for Aletheia.

This module provides Rich-based formatting functions for chat messages
to create clear visual distinction between user and bot messages.
"""

from rich.panel import Panel
from rich.markdown import Markdown
from rich import box


def format_user_message(message: str, session_id: str) -> str:
    """Format user message with inline styling.

    Args:
        message: The user's input message
        session_id: Current session identifier

    Returns:
        Formatted string with Rich markup for user message
    """
    return f"[[bold yellow]{session_id}[/bold yellow]] [bold green]👤 YOU:[/bold green] {message}"


def format_bot_response_panel(content: str) -> Panel:
    """Format bot response in a Rich Panel with Markdown rendering.

    Args:
        content: The bot's response content (supports Markdown)
        streaming: Whether this is being displayed during streaming (affects border style)

    Returns:
        Rich Panel containing the formatted bot response
    """
    # Strip any trailing whitespace/newlines that might cause rendering issues
    clean_content = content.strip() if content else ""
    markdown_content = Markdown(clean_content) if clean_content else ""

    return Panel(
        markdown_content,
        title="🤖 Aletheia",
        title_align="left",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,  # Force panel to use full terminal width
    )


def format_system_message(message: str, message_type: str = "info") -> Panel:
    """Format system messages (errors, warnings, info).

    Args:
        message: The system message content
        message_type: Type of message ("info", "warning", "error")

    Returns:
        Rich Panel containing the formatted system message
    """
    styles = {
        "info": {"border_style": "blue", "title": "ℹ️ Info"},
        "warning": {"border_style": "yellow", "title": "⚠️ Warning"},
        "error": {"border_style": "red", "title": "❌ Error"},
    }

    style = styles.get(message_type, styles["info"])

    return Panel(
        message,
        title=style["title"],
        title_align="left",
        border_style=style["border_style"],
        box=box.ROUNDED,
        padding=(0, 1),
    )


def format_bot_response_header(session_id: str) -> str:
    """Format the bot response header (shown before streaming starts).

    Args:
        session_id: Current session identifier

    Returns:
        Formatted string with Rich markup for bot response header
    """
    return f"\n[[bold yellow]{session_id}[/bold yellow]] [bold cyan]🤖 Aletheia:[/bold cyan]"
