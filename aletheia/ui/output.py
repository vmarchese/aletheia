"""
Rich-based output formatting for terminal display.

Provides progress indicators, status symbols, headers, and tables.
"""

from __future__ import annotations
import time
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax


class OutputFormatter:
    """Formats output with Rich styling."""

    # Status indicators
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    PROGRESS = "⏳"

    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        """
        Initialize output formatter.

        Args:
            console: Rich console instance (creates new one if not provided)
            verbose: Enable verbose output (show agent names, etc.)
        """
        self.console = console or Console()
        self.verbose = verbose

    def print_header(self, text: str, level: int = 1) -> None:
        """
        Print a section header.

        Args:
            text: Header text
            level: Header level (1-3, affects styling)
        """
        if level == 1:
            self.console.print(f"\n[bold cyan]{'=' * 80}[/bold cyan]")
            self.console.print(f"[bold cyan]{text.upper()}[/bold cyan]")
            self.console.print(f"[bold cyan]{'=' * 80}[/bold cyan]\n")
        elif level == 2:
            self.console.print(f"\n[bold yellow]{text}[/bold yellow]")
            self.console.print(f"[yellow]{'-' * len(text)}[/yellow]\n")
        else:
            self.console.print(f"\n[bold]{text}[/bold]\n")

    def print_status(self, message: str, status: str = "info") -> None:
        """
        Print a status message with indicator.

        Args:
            message: Status message
            status: Status type (success, error, warning, info, progress)
        """
        icons = {
            "success": self.SUCCESS,
            "error": self.ERROR,
            "warning": self.WARNING,
            "info": self.INFO,
            "progress": self.PROGRESS
        }
        icon = icons.get(status, self.INFO)

        self.console.print(f"[bold cyan][Aletheia][/bold cyan] {icon} {message}")

    def print_agent_action(self, agent_name: str, action: str) -> None:
        """
        Print agent action (verbose mode only).

        Args:
            agent_name: Name of the agent
            action: Action being performed
        """
        if self.verbose:
            self.console.print(f"[bold cyan][Aletheia][/bold cyan] [dim][{agent_name}][/dim] {action}")

    def print_error(
        self,
        message: str,
        details: Optional[str] = None,
        recovery_options: Optional[List[str]] = None
    ) -> None:
        """
        Print an error message with optional details and recovery options.

        Args:
            message: Error message
            details: Optional detailed error information
            recovery_options: Optional list of recovery options
        """
        self.console.print(f"\n[bold red]{self.ERROR} {message}[/bold red]")

        if details:
            self.console.print(f"[red]Error: {details}[/red]")

        if recovery_options:
            self.console.print("\n[yellow]What would you like to do?[/yellow]")
            for idx, option in enumerate(recovery_options, start=1):
                self.console.print(f"{idx}. {option}")

    def print_warning(self, message: str, details: Optional[str] = None) -> None:
        """
        Print a warning message.

        Args:
            message: Warning message
            details: Optional detailed information
        """
        self.console.print(f"\n[bold yellow]{self.WARNING} {message}[/bold yellow]")
        if details:
            self.console.print(f"[yellow]{details}[/yellow]")

    def print_partial_success(
        self,
        success_message: str,
        failure_details: str,
        prompt: Optional[str] = None
    ) -> None:
        """
        Print a partial success warning with optional prompt.

        Args:
            success_message: Description of what succeeded
            failure_details: Description of what failed
            prompt: Optional prompt for user action
        """
        self.console.print(f"\n[bold yellow]{self.WARNING} {success_message}[/bold yellow]")
        self.console.print(f"[yellow]Note: {failure_details}[/yellow]")
        if prompt:
            self.console.print(f"[cyan]{prompt}[/cyan]")

    def print_operation_progress(
        self,
        operation: str,
        elapsed_seconds: Optional[int] = None,
        agent_name: Optional[str] = None
    ) -> None:
        """
        Print progress for a long-running operation with elapsed time.

        Args:
            operation: Description of the operation
            elapsed_seconds: Elapsed time in seconds
            agent_name: Optional agent name (shown in verbose mode)
        """
        prefix = "[bold cyan][Aletheia][/bold cyan]"

        if self.verbose and agent_name:
            prefix += f" [dim][{agent_name}][/dim]"

        message = f"{prefix} {operation}"

        if elapsed_seconds is not None:
            message += f" {self.PROGRESS} (elapsed: {elapsed_seconds}s)"
        else:
            message += f" {self.PROGRESS}"

        self.console.print(message)

    def print_table(
        self,
        title: str,
        columns: List[str],
        rows: List[List[Any]],
        show_header: bool = True
    ) -> None:
        """
        Print a formatted table.

        Args:
            title: Table title
            columns: Column headers
            rows: List of row data
            show_header: Whether to show column headers
        """
        table = Table(title=title, show_header=show_header)

        # Add columns
        for col in columns:
            table.add_column(col, style="cyan")

        # Add rows
        for row in rows:
            table.add_row(*[str(cell) for cell in row])

        self.console.print(table)

    def print_list(
        self,
        items: List[str],
        title: Optional[str] = None,
        bullet: str = "•"
    ) -> None:
        """
        Print a bulleted list.

        Args:
            items: List items
            title: Optional list title
            bullet: Bullet character
        """
        if title:
            self.console.print(f"\n[bold]{title}[/bold]")

        for item in items:
            self.console.print(f"{bullet} {item}")

    def print_code(
        self,
        code: str,
        language: str = "python",
        line_numbers: bool = True,
        highlight_lines: Optional[List[int]] = None
    ) -> None:
        """
        Print syntax-highlighted code.

        Args:
            code: Code to display
            language: Programming language for syntax highlighting
            line_numbers: Whether to show line numbers
            highlight_lines: Lines to highlight
        """
        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=line_numbers,
            highlight_lines=set(highlight_lines) if highlight_lines else None
        )
        self.console.print(syntax)

    def print_markdown(self, markdown_text: str) -> None:
        """
        Print formatted markdown.

        Args:
            markdown_text: Markdown text to display
        """
        md = Markdown(markdown_text)
        self.console.print(md)

    def print_panel(
        self,
        content: str,
        title: Optional[str] = None,
        border_style: str = "cyan"
    ) -> None:
        """
        Print content in a bordered panel.

        Args:
            content: Panel content
            title: Optional panel title
            border_style: Border color/style
        """
        panel = Panel(content, title=title, border_style=border_style)
        self.console.print(panel)

    @contextmanager
    def progress_context(
        self,
        description: str,
        show_elapsed: bool = True
    ):
        """
        Context manager for showing progress during long operations.

        Args:
            description: Description of the operation
            show_elapsed: Whether to show elapsed time

        Yields:
            Progress task for updating status
        """
        columns = [
            SpinnerColumn(),
            TextColumn("[bold cyan][Aletheia][/bold cyan]"),
            TextColumn("[progress.description]{task.description}"),
        ]

        if show_elapsed:
            columns.append(TimeElapsedColumn())

        with Progress(*columns, console=self.console) as progress:
            task = progress.add_task(description, total=None)
            yield task

    def print_action_menu(
        self,
        title: str,
        actions: List[str]
    ) -> None:
        """
        Print an action menu for user selection.

        Args:
            title: Menu title
            actions: List of action descriptions
        """
        self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        for idx, action in enumerate(actions, start=1):
            self.console.print(f"{idx}. {action}")

    def print_diagnosis(
        self,
        root_cause: str,
        description: str,
        evidence: List[str],
        actions: List[Dict[str, str]],
        confidence: float,
        show_action_menu: bool = False
    ) -> None:
        """
        Print formatted diagnosis output.

        Args:
            root_cause: Root cause summary
            description: Detailed description
            evidence: List of evidence items
            actions: List of recommended actions (dicts with 'priority' and 'action')
            confidence: Confidence score (0.0-1.0)
            show_action_menu: Whether to show action menu at the end
        """
        # Header
        self.print_header("ROOT CAUSE ANALYSIS", level=1)

        # Confidence
        confidence_pct = int(confidence * 100)
        self.console.print(f"[bold]Confidence:[/bold] {confidence_pct}%\n")

        # Root cause
        self.console.print("[bold]PROBABLE CAUSE:[/bold]")
        self.console.print(f"{root_cause}\n")

        # Description
        self.console.print("[bold]DESCRIPTION:[/bold]")
        self.console.print(f"{description}\n")

        # Evidence
        self.console.print("[bold]EVIDENCE:[/bold]")
        self.print_list(evidence, bullet="•")

        # Recommended actions
        self.console.print("\n[bold]RECOMMENDED ACTIONS:[/bold]")
        for action in actions:
            priority = action.get('priority', 'UNKNOWN').upper()
            action_text = action.get('action', '')

            # Color-code by priority
            if priority == "IMMEDIATE":
                color = "red"
            elif priority == "HIGH":
                color = "yellow"
            elif priority == "MEDIUM":
                color = "blue"
            else:
                color = "white"

            self.console.print(f"[{color}][{priority}][/{color}] {action_text}")

        # Optional action menu
        if show_action_menu:
            self.print_action_menu(
                "Choose an action:",
                [
                    "Show proposed patch",
                    "Open in $EDITOR",
                    "Save diagnosis to file",
                    "End session"
                ]
            )


def create_output_formatter(
    console: Optional[Console] = None,
    verbose: bool = False
) -> OutputFormatter:
    """
    Factory function to create an OutputFormatter instance.

    Args:
        console: Optional Rich console instance
        verbose: Enable verbose output

    Returns:
        OutputFormatter instance
    """
    return OutputFormatter(console, verbose)
