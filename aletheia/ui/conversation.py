"""
Conversational UI helpers for displaying and interacting with conversation-based investigations.

This module provides display and input functions for conversational mode.
ALL functions are display/input only - NO logic for parameter extraction or parsing.
"""

from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt


class ConversationalUI:
    """UI helpers for conversational mode interactions."""

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize conversational UI.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()

    def display_conversation(
        self,
        conversation_history: List[Dict[str, str]],
        show_all: bool = False,
        max_messages: int = 5
    ) -> None:
        """
        Display conversation history.

        This is a DISPLAY-ONLY function. It does not parse or extract any information
        from the conversation. It simply formats and shows the messages.

        Args:
            conversation_history: List of conversation messages with 'role' and 'content' keys
            show_all: If True, show all messages. If False, show only last max_messages
            max_messages: Maximum number of recent messages to show when show_all=False
        """
        if not conversation_history:
            self.console.print("[dim]No conversation history yet[/dim]")
            return

        # Determine which messages to display
        messages_to_show = conversation_history if show_all else conversation_history[-max_messages:]

        # Display header
        self.console.print("\n[bold cyan]Conversation History[/bold cyan]")
        if not show_all and len(conversation_history) > max_messages:
            self.console.print(f"[dim]Showing last {max_messages} of {len(conversation_history)} messages[/dim]")

        # Display each message
        for msg in messages_to_show:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Format based on role
            if role == "user":
                # User messages in green
                self.console.print(f"\n[bold green]You:[/bold green] {content}")
            elif role == "agent":
                # Agent messages in cyan
                self.console.print(f"\n[bold cyan]Aletheia:[/bold cyan] {content}")
            elif role == "system":
                # System messages in dim
                self.console.print(f"\n[dim]System: {content}[/dim]")
            else:
                # Unknown role
                self.console.print(f"\n[yellow]{role}:[/yellow] {content}")

        self.console.print()  # Add spacing

    def format_agent_response(
        self,
        response: str,
        agent_name: Optional[str] = None,
        show_agent_name: bool = False
    ) -> None:
        """
        Format and display an agent response.

        This is a DISPLAY-ONLY function. It does not interpret or process the response.
        It simply formats it nicely for the user to read.

        Args:
            response: Agent response text to display
            agent_name: Optional name of the agent (e.g., "data_fetcher")
            show_agent_name: If True, show which agent provided the response
        """
        # Create title based on whether we show agent name
        if show_agent_name and agent_name:
            # Convert agent_name to readable format (e.g., "data_fetcher" -> "Data Fetcher")
            readable_name = agent_name.replace("_", " ").title()
            title = f"Aletheia - {readable_name}"
        else:
            title = "Aletheia"

        # Display response in a panel for visual separation
        panel = Panel(
            Markdown(response),
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
        self.console.print(panel)

    def get_user_input(
        self,
        prompt: str = "You: ",
        multiline: bool = False
    ) -> str:
        """
        Get input from the user in conversational mode.

        This is an INPUT-ONLY function. It does not validate, parse, or extract
        any information from the user's input. It simply collects the text.

        Args:
            prompt: Prompt to show the user
            multiline: If True, allow multiline input (currently single-line only)

        Returns:
            User input as a string (NOT parsed or processed)
        """
        # Note: Rich Prompt doesn't support multiline easily, so we use single-line
        # for now. Could be enhanced with a proper multiline input widget.
        user_input = Prompt.ask(f"[bold green]{prompt}[/bold green]")
        return user_input.strip()

    def display_agent_thinking(self, message: str = "Analyzing...") -> None:
        """
        Display a message indicating the agent is thinking/processing.

        This is a DISPLAY-ONLY function. It shows a status message to the user.

        Args:
            message: Message to display (e.g., "Analyzing patterns...", "Fetching data...")
        """
        self.console.print(f"[dim]⏳ {message}[/dim]")

    def display_clarification_request(
        self,
        question: str,
        context: Optional[str] = None
    ) -> None:
        """
        Display a clarification question from the agent.

        This is a DISPLAY-ONLY function. It formats clarification requests nicely.

        Args:
            question: The clarification question to ask
            context: Optional context about why the question is being asked
        """
        self.console.print("\n[bold yellow]I need some clarification:[/bold yellow]")

        if context:
            self.console.print(f"[dim]{context}[/dim]")

        self.console.print(f"\n{question}\n")

    def display_conversation_starter(self, problem_description: Optional[str] = None) -> None:
        """
        Display the conversation starter message.

        This is a DISPLAY-ONLY function. It shows the initial prompt to start conversation.

        Args:
            problem_description: Optional problem description if already provided
        """
        self.console.print("\n[bold cyan]Welcome to Aletheia Conversational Mode[/bold cyan]\n")

        if problem_description:
            self.console.print(f"[dim]Problem: {problem_description}[/dim]\n")
            self.console.print("I'll help you investigate this issue. Feel free to ask questions or provide more information.")
        else:
            self.console.print("Tell me about the problem you're investigating.")
            self.console.print("You can describe symptoms, mention specific services, or ask questions.")

        self.console.print("\n[dim]Type 'help' for available commands, or 'exit' to end the session.[/dim]\n")

    def display_session_summary(
        self,
        session_id: str,
        status: str,
        message_count: int
    ) -> None:
        """
        Display a summary of the conversation session.

        This is a DISPLAY-ONLY function. It shows session statistics.

        Args:
            session_id: Session identifier
            status: Session status (e.g., "completed", "in_progress")
            message_count: Number of messages in the conversation
        """
        self.console.print("\n[bold cyan]Session Summary[/bold cyan]")
        self.console.print(f"Session ID: {session_id}")
        self.console.print(f"Status: {status}")
        self.console.print(f"Messages: {message_count}")

    def display_help(self) -> None:
        """
        Display help information for conversational mode.

        This is a DISPLAY-ONLY function. It shows available commands and tips.
        """
        help_text = """
# Conversational Mode Help

## What You Can Do:

- **Describe your problem**: Tell me what's happening in your own words
- **Ask questions**: "What errors do you see?", "When did this start?"
- **Provide information**: Share service names, time windows, error messages
- **Request actions**: "Show me the logs", "Check the metrics", "Look at the code"

## Available Commands:

- `help` - Show this help message
- `history` - Show full conversation history
- `status` - Show current investigation status
- `exit` or `quit` - End the session

## Tips:

- Be specific about services, namespaces, and time frames
- Mention error messages or symptoms you're seeing
- I'll ask clarifying questions if I need more information
- You can change direction at any time by asking new questions

## Example Conversations:

**You:** "Why is the payments service failing?"
**Aletheia:** "I'll investigate payments service. Which namespace is it running in?"
**You:** "Production namespace"
**Aletheia:** "Fetching logs from payments-svc in production..."

**You:** "Show me error rate for user-api in the last hour"
**Aletheia:** "Querying metrics for user-api error rate..."
        """

        self.console.print(Panel(
            Markdown(help_text),
            title="[bold cyan]Help[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        ))

    def confirm_action(self, action: str) -> bool:
        """
        Ask user to confirm an action.

        This is an INPUT-ONLY function. It gets a yes/no response.

        Args:
            action: Description of the action to confirm

        Returns:
            True if user confirms, False otherwise
        """
        response = Prompt.ask(
            f"[yellow]{action}[/yellow] [dim](y/n)[/dim]",
            choices=["y", "n", "yes", "no"],
            default="y"
        )
        return response.lower() in ["y", "yes"]


# Convenience functions for quick access

def display_conversation(
    conversation_history: List[Dict[str, str]],
    console: Optional[Console] = None,
    show_all: bool = False,
    max_messages: int = 5
) -> None:
    """
    Convenience function to display conversation history.

    Args:
        conversation_history: List of messages with 'role' and 'content'
        console: Optional Rich console
        show_all: Show all messages or just recent ones
        max_messages: Maximum recent messages to show
    """
    ui = ConversationalUI(console)
    ui.display_conversation(conversation_history, show_all, max_messages)


def format_agent_response(
    response: str,
    console: Optional[Console] = None,
    agent_name: Optional[str] = None,
    show_agent_name: bool = False
) -> None:
    """
    Convenience function to format agent response.

    Args:
        response: Agent response text
        console: Optional Rich console
        agent_name: Optional agent name
        show_agent_name: Show which agent responded
    """
    ui = ConversationalUI(console)
    ui.format_agent_response(response, agent_name, show_agent_name)


def get_user_input(
    prompt: str = "You: ",
    console: Optional[Console] = None,
    multiline: bool = False
) -> str:
    """
    Convenience function to get user input.

    Args:
        prompt: Prompt to show user
        console: Optional Rich console
        multiline: Allow multiline input (not yet implemented)

    Returns:
        User input string
    """
    ui = ConversationalUI(console)
    return ui.get_user_input(prompt, multiline)
