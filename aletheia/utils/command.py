"""Command execution utilities with verbose logging support.

This module provides utilities for executing external commands (kubectl, curl, git, etc.)
with optional verbose output for debugging.
"""

import shlex
import subprocess
import time

import structlog
from rich.console import Console

logger = structlog.get_logger(__name__)


# Global flag for verbose command output
_VERBOSE_COMMANDS = False
_console = Console(stderr=True)


def set_verbose_commands(enabled: bool) -> None:
    """Enable or disable verbose command output.

    Args:
        enabled: True to enable verbose output for all external commands
    """
    global _VERBOSE_COMMANDS
    _VERBOSE_COMMANDS = enabled


def is_verbose_commands() -> bool:
    """Check if verbose command output is enabled.

    Returns:
        True if verbose output is enabled
    """
    return _VERBOSE_COMMANDS


def run_command(
    cmd: list[str],
    capture_output: bool = True,
    text: bool = True,
    check: bool = True,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run an external command with optional verbose output.

    This is a wrapper around subprocess.run that logs command execution
    when verbose mode is enabled.

    Args:
        cmd: Command and arguments as list
        capture_output: Whether to capture stdout/stderr
        text: Whether to return output as text (vs bytes)
        check: Whether to raise exception on non-zero exit
        timeout: Command timeout in seconds
        cwd: Working directory for command
        env: Environment variables
        **kwargs: Additional arguments passed to subprocess.run

    Returns:
        CompletedProcess instance with command results

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
        subprocess.TimeoutExpired: If command times out
    """
    # Log command execution
    cmd_str = " ".join(cmd)
    logger.debug(f"Executing command: {cmd_str}", cwd=cwd)

    if _VERBOSE_COMMANDS:
        # Print command being executed
        _console.print("\n[bold cyan]→ Executing command:[/bold cyan]")
        _console.print(f"  [dim]{cmd_str}[/dim]")

        if cwd:
            _console.print(f"  [dim]Working directory: {cwd}[/dim]")

    # Execute command with timing
    start_time = time.time()
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=text,
        check=False,  # We'll handle check ourselves
        timeout=timeout,
        cwd=cwd,
        env=env,
        **kwargs,
    )
    duration = time.time() - start_time

    if _VERBOSE_COMMANDS:
        # Print results
        _console.print(f"  [dim]Exit code: {result.returncode}[/dim]")

        if result.stdout:
            _console.print("[bold green]  stdout:[/bold green]")
            # Truncate very long output
            stdout_lines = result.stdout.split("\n")
            if len(stdout_lines) > 50:
                for line in stdout_lines[:25]:
                    _console.print(f"    {line}")
                _console.print(
                    f"    [dim]... ({len(stdout_lines) - 50} lines omitted) ...[/dim]"
                )
                for line in stdout_lines[-25:]:
                    _console.print(f"    {line}")
            else:
                for line in stdout_lines:
                    _console.print(f"    {line}")

        if result.stderr:
            _console.print("[bold red]  stderr:[/bold red]")
            stderr_lines = result.stderr.split("\n")
            if len(stderr_lines) > 50:
                for line in stderr_lines[:25]:
                    _console.print(f"    {line}")
                _console.print(
                    f"    [dim]... ({len(stderr_lines) - 50} lines omitted) ...[/dim]"
                )
                for line in stderr_lines[-25:]:
                    _console.print(f"    {line}")
            else:
                for line in stderr_lines:
                    _console.print(f"    {line}")

        _console.print()  # Blank line after command output

    # Log command result
    logger.debug(
        f"Command completed: {cmd_str}",
        returncode=result.returncode,
        duration_seconds=round(duration, 3),
    )

    # Now check for errors if requested
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )

    return result


def sanitize_command(command: list) -> list:
    """Sanitize command by redacting sensitive information.

    Args:
        command: Command list to sanitize

    Returns:
        Sanitized command list
    """
    sanitized = []
    for part in command:
        sanitized.append(shlex.quote(part))

    return sanitized
