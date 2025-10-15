"""
Diagnosis output and action handling for terminal display.

Provides functions for displaying diagnosis results, exporting to markdown,
and handling user actions on the diagnosis.
"""

from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

from aletheia.ui.output import OutputFormatter
from aletheia.ui.menu import Menu


class DiagnosisFormatter:
    """Formats diagnosis output for terminal display and export."""

    def __init__(self, output_formatter: Optional[OutputFormatter] = None):
        """
        Initialize diagnosis formatter.

        Args:
            output_formatter: Optional OutputFormatter instance
        """
        self.output = output_formatter or OutputFormatter()
        self.console = self.output.console

    def display_diagnosis(
        self,
        diagnosis: Dict[str, Any],
        show_action_menu: bool = True
    ) -> None:
        """
        Display diagnosis in terminal with rich formatting.

        Args:
            diagnosis: Diagnosis data from FINAL_DIAGNOSIS section
            show_action_menu: Whether to show action menu
        """
        if not diagnosis:
            self.output.print_error("No diagnosis available")
            return

        # Extract diagnosis components
        root_cause = diagnosis.get("root_cause", {})
        timeline_correlation = diagnosis.get("timeline_correlation", {})
        recommended_actions = diagnosis.get("recommended_actions", [])
        evidence = diagnosis.get("evidence", [])

        # Header
        self.output.print_header("ROOT CAUSE ANALYSIS", level=1)

        # Confidence
        confidence = root_cause.get("confidence", 0.0)
        confidence_pct = int(confidence * 100)
        confidence_color = self._get_confidence_color(confidence)
        self.console.print(
            f"[bold]Confidence:[/bold] [{confidence_color}]{confidence_pct}%[/{confidence_color}]\n"
        )

        # Root cause type and description
        cause_type = root_cause.get("type", "Unknown")
        description = root_cause.get("description", "No description available")

        self.console.print(f"[bold]ROOT CAUSE TYPE:[/bold] {cause_type}\n")
        self.console.print(f"[bold]DESCRIPTION:[/bold]")
        self.console.print(f"{description}\n")

        # Timeline correlation (if available)
        if timeline_correlation:
            self.console.print("[bold]TIMELINE CORRELATION:[/bold]")
            if "deployment" in timeline_correlation:
                self.console.print(f"  • Deployment: {timeline_correlation['deployment']}")
            if "first_error" in timeline_correlation:
                self.console.print(f"  • First Error: {timeline_correlation['first_error']}")
            if "alignment" in timeline_correlation:
                self.console.print(f"  • {timeline_correlation['alignment']}")
            self.console.print()

        # Evidence (if available)
        if evidence:
            self.console.print("[bold]SUPPORTING EVIDENCE:[/bold]")
            for item in evidence:
                self.console.print(f"  • {item}")
            self.console.print()

        # Recommended actions
        if recommended_actions:
            self.console.print("[bold]RECOMMENDED ACTIONS:[/bold]")
            for action in recommended_actions:
                priority = action.get("priority", "unknown").upper()
                action_text = action.get("action", "")
                rationale = action.get("rationale", "")
                patch = action.get("patch", "")

                # Color-code by priority
                priority_color = self._get_priority_color(priority)

                self.console.print(
                    f"[{priority_color}][{priority}][/{priority_color}] {action_text}"
                )

                if rationale:
                    self.console.print(f"  [dim]Rationale: {rationale}[/dim]")

                if patch:
                    self.console.print("  [dim]Proposed patch:[/dim]")
                    # Extract language from context if possible
                    language = self._detect_language_from_patch(patch)
                    syntax = Syntax(
                        patch.strip(),
                        language,
                        theme="monokai",
                        line_numbers=False
                    )
                    self.console.print(syntax)

            self.console.print()

        # Action menu
        if show_action_menu:
            self._show_action_menu(diagnosis)

    def export_to_markdown(
        self,
        diagnosis: Dict[str, Any],
        output_path: Path,
        include_metadata: bool = True
    ) -> None:
        """
        Export diagnosis to markdown file.

        Args:
            diagnosis: Diagnosis data from FINAL_DIAGNOSIS section
            output_path: Path to save markdown file
            include_metadata: Whether to include generation metadata

        Raises:
            IOError: If file cannot be written
        """
        if not diagnosis:
            raise ValueError("No diagnosis data to export")

        # Build markdown content
        lines = []

        # Title and metadata
        lines.append("# Root Cause Analysis Report")
        lines.append("")

        if include_metadata:
            lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"**Tool**: Aletheia AI-Powered Incident Analysis")
            lines.append("")

        # Extract diagnosis components
        root_cause = diagnosis.get("root_cause", {})
        timeline_correlation = diagnosis.get("timeline_correlation", {})
        recommended_actions = diagnosis.get("recommended_actions", [])
        evidence = diagnosis.get("evidence", [])

        # Confidence
        confidence = root_cause.get("confidence", 0.0)
        confidence_pct = int(confidence * 100)
        lines.append(f"**Confidence**: {confidence_pct}%")
        lines.append("")

        # Root cause
        lines.append("## Root Cause")
        lines.append("")
        cause_type = root_cause.get("type", "Unknown")
        lines.append(f"**Type**: `{cause_type}`")
        lines.append("")
        description = root_cause.get("description", "No description available")
        lines.append(description)
        lines.append("")

        # Timeline correlation
        if timeline_correlation:
            lines.append("## Timeline Correlation")
            lines.append("")
            if "deployment" in timeline_correlation:
                lines.append(f"- **Deployment**: {timeline_correlation['deployment']}")
            if "first_error" in timeline_correlation:
                lines.append(f"- **First Error**: {timeline_correlation['first_error']}")
            if "alignment" in timeline_correlation:
                lines.append(f"- **Alignment**: {timeline_correlation['alignment']}")
            lines.append("")

        # Evidence
        if evidence:
            lines.append("## Supporting Evidence")
            lines.append("")
            for item in evidence:
                lines.append(f"- {item}")
            lines.append("")

        # Recommended actions
        if recommended_actions:
            lines.append("## Recommended Actions")
            lines.append("")

            # Group by priority
            priority_groups = {
                "IMMEDIATE": [],
                "HIGH": [],
                "MEDIUM": [],
                "LOW": []
            }

            for action in recommended_actions:
                priority = action.get("priority", "LOW").upper()
                if priority not in priority_groups:
                    priority = "LOW"
                priority_groups[priority].append(action)

            # Output each priority group
            for priority in ["IMMEDIATE", "HIGH", "MEDIUM", "LOW"]:
                actions = priority_groups[priority]
                if not actions:
                    continue

                lines.append(f"### {priority} Priority")
                lines.append("")

                for action in actions:
                    action_text = action.get("action", "")
                    rationale = action.get("rationale", "")
                    patch = action.get("patch", "")

                    lines.append(f"**Action**: {action_text}")
                    lines.append("")

                    if rationale:
                        lines.append(f"**Rationale**: {rationale}")
                        lines.append("")

                    if patch:
                        lines.append("**Proposed Patch**:")
                        lines.append("")
                        language = self._detect_language_from_patch(patch)
                        lines.append(f"```{language}")
                        lines.append(patch.strip())
                        lines.append("```")
                        lines.append("")

        # Write to file
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n".join(lines), encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to write diagnosis to {output_path}: {e}")

    def _show_action_menu(self, diagnosis: Dict[str, Any]) -> None:
        """Show action menu for diagnosis."""
        self.output.print_action_menu(
            "What would you like to do?",
            [
                "Show proposed patch",
                "Open in $EDITOR",
                "Save diagnosis to file",
                "End session"
            ]
        )

    def _get_confidence_color(self, confidence: float) -> str:
        """Get color for confidence score."""
        if confidence >= 0.8:
            return "green"
        elif confidence >= 0.6:
            return "yellow"
        else:
            return "red"

    def _get_priority_color(self, priority: str) -> str:
        """Get color for priority level."""
        priority = priority.upper()
        if priority == "IMMEDIATE":
            return "bold red"
        elif priority == "HIGH":
            return "yellow"
        elif priority == "MEDIUM":
            return "blue"
        else:
            return "white"

    def _detect_language_from_patch(self, patch: str) -> str:
        """Detect programming language from patch content."""
        # Simple heuristics based on syntax
        if "func " in patch and "return" in patch:
            return "go"
        elif "def " in patch and ":" in patch:
            return "python"
        elif "function" in patch or "const " in patch or "let " in patch:
            return "javascript"
        elif "public " in patch or "private " in patch or "class " in patch:
            return "java"
        else:
            return "text"


class DiagnosisActionHandler:
    """Handles user actions on diagnosis results."""

    def __init__(
        self,
        diagnosis: Dict[str, Any],
        session_dir: Path,
        console: Optional[Console] = None
    ):
        """
        Initialize action handler.

        Args:
            diagnosis: Diagnosis data
            session_dir: Session directory path
            console: Optional Rich console
        """
        self.diagnosis = diagnosis
        self.session_dir = Path(session_dir)
        self.console = console or Console()
        self.formatter = DiagnosisFormatter(OutputFormatter(console))

    def handle_action(self, action_choice: int) -> bool:
        """
        Handle user action choice.

        Args:
            action_choice: Action number (1-4)

        Returns:
            True if session should continue, False if should end
        """
        if action_choice == 1:
            return self.show_proposed_patch()
        elif action_choice == 2:
            return self.open_in_editor()
        elif action_choice == 3:
            return self.save_to_file()
        elif action_choice == 4:
            return self.end_session()
        else:
            self.console.print("[red]Invalid action choice[/red]")
            return True

    def show_proposed_patch(self) -> bool:
        """Show proposed patch in detail."""
        self.console.print("\n[bold cyan]PROPOSED PATCHES[/bold cyan]\n")

        recommended_actions = self.diagnosis.get("recommended_actions", [])
        patches_found = False

        for idx, action in enumerate(recommended_actions, start=1):
            patch = action.get("patch", "")
            if patch:
                patches_found = True
                action_text = action.get("action", "")
                self.console.print(f"[bold]{idx}. {action_text}[/bold]")

                language = self.formatter._detect_language_from_patch(patch)
                syntax = Syntax(
                    patch.strip(),
                    language,
                    theme="monokai",
                    line_numbers=True
                )
                self.console.print(syntax)
                self.console.print()

        if not patches_found:
            self.console.print("[yellow]No patches available in diagnosis[/yellow]")

        return True  # Continue session

    def open_in_editor(self) -> bool:
        """Open diagnosis in user's $EDITOR."""
        # Export to temp file first
        temp_file = self.session_dir / "diagnosis.md"

        try:
            self.formatter.export_to_markdown(
                self.diagnosis,
                temp_file,
                include_metadata=True
            )

            # Get editor from environment
            editor = os.environ.get("EDITOR", "vi")

            # Open in editor
            try:
                subprocess.run([editor, str(temp_file)], check=True)
                self.console.print(f"[green]✓[/green] Opened in {editor}")
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Failed to open editor: {e}[/red]")
            except FileNotFoundError:
                self.console.print(
                    f"[red]Editor '{editor}' not found. Set $EDITOR environment variable.[/red]"
                )

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

        return True  # Continue session

    def save_to_file(self) -> bool:
        """Save diagnosis to file."""
        # Prompt for filename
        from aletheia.ui.input import InputHandler

        default_filename = f"diagnosis-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        input_handler = InputHandler(console=self.console)
        filename = input_handler.get_text(
            "Enter filename",
            default=default_filename
        )

        if not filename:
            self.console.print("[yellow]Save cancelled[/yellow]")
            return True

        # Determine output path
        if "/" in filename or "\\" in filename:
            output_path = Path(filename)
        else:
            output_path = self.session_dir / filename

        # Export
        try:
            self.formatter.export_to_markdown(
                self.diagnosis,
                output_path,
                include_metadata=True
            )
            self.console.print(f"[green]✓[/green] Saved to {output_path}")
        except Exception as e:
            self.console.print(f"[red]Error saving file: {e}[/red]")

        return True  # Continue session

    def end_session(self) -> bool:
        """End the session."""
        from aletheia.ui.confirmation import ConfirmationManager

        confirmation_mgr = ConfirmationManager(level="normal", console=self.console)
        if confirmation_mgr.confirm("Are you sure you want to end the session?", category="destructive"):
            self.console.print("[cyan]Session ended[/cyan]")
            return False  # End session
        else:
            return True  # Continue session


def display_diagnosis(
    diagnosis: Dict[str, Any],
    console: Optional[Console] = None,
    show_action_menu: bool = True
) -> None:
    """
    Display diagnosis in terminal (convenience function).

    Args:
        diagnosis: Diagnosis data from FINAL_DIAGNOSIS section
        console: Optional Rich console
        show_action_menu: Whether to show action menu
    """
    formatter = DiagnosisFormatter(OutputFormatter(console))
    formatter.display_diagnosis(diagnosis, show_action_menu)


def export_diagnosis_to_markdown(
    diagnosis: Dict[str, Any],
    output_path: Path,
    include_metadata: bool = True
) -> None:
    """
    Export diagnosis to markdown file (convenience function).

    Args:
        diagnosis: Diagnosis data from FINAL_DIAGNOSIS section
        output_path: Path to save markdown file
        include_metadata: Whether to include generation metadata
    """
    formatter = DiagnosisFormatter()
    formatter.export_to_markdown(diagnosis, output_path, include_metadata)


def handle_diagnosis_actions(
    diagnosis: Dict[str, Any],
    session_dir: Path,
    console: Optional[Console] = None
) -> None:
    """
    Interactive action handler for diagnosis (convenience function).

    Args:
        diagnosis: Diagnosis data
        session_dir: Session directory path
        console: Optional Rich console
    """
    handler = DiagnosisActionHandler(diagnosis, session_dir, console)
    menu = Menu(console)

    while True:
        choice = menu.show_simple(
            "Choose an action",
            [
                "Show proposed patch",
                "Open in $EDITOR",
                "Save diagnosis to file",
                "End session"
            ]
        )

        # Map choice string to action number
        action_map = {
            "Show proposed patch": 1,
            "Open in $EDITOR": 2,
            "Save diagnosis to file": 3,
            "End session": 4
        }

        action_num = action_map.get(choice, 4)
        should_continue = handler.handle_action(action_num)
        if not should_continue:
            break
