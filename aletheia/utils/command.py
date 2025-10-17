"""Command execution utilities with verbose logging support.

This module provides utilities for executing external commands (kubectl, curl, git, etc.)
with optional verbose output for debugging.
"""

import subprocess
import os
import time
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.syntax import Syntax

from aletheia.utils.logging import (
    is_trace_enabled,
    log_command,
    log_command_result,
)


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
    cmd: List[str],
    capture_output: bool = True,
    text: bool = True,
    check: bool = True,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    **kwargs
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
    # Log to trace file if enabled
    cmd_str = " ".join(cmd)
    if is_trace_enabled():
        log_command(cmd_str, cwd=cwd)
    
    if _VERBOSE_COMMANDS:
        # Print command being executed
        _console.print(f"\n[bold cyan]→ Executing command:[/bold cyan]")
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
        **kwargs
    )
    duration = time.time() - start_time
    
    if _VERBOSE_COMMANDS:
        # Print results
        _console.print(f"  [dim]Exit code: {result.returncode}[/dim]")
        
        if result.stdout:
            _console.print("[bold green]  stdout:[/bold green]")
            # Truncate very long output
            stdout_lines = result.stdout.split('\n')
            if len(stdout_lines) > 50:
                for line in stdout_lines[:25]:
                    _console.print(f"    {line}")
                _console.print(f"    [dim]... ({len(stdout_lines) - 50} lines omitted) ...[/dim]")
                for line in stdout_lines[-25:]:
                    _console.print(f"    {line}")
            else:
                for line in stdout_lines:
                    _console.print(f"    {line}")
        
        if result.stderr:
            _console.print("[bold red]  stderr:[/bold red]")
            stderr_lines = result.stderr.split('\n')
            if len(stderr_lines) > 50:
                for line in stderr_lines[:25]:
                    _console.print(f"    {line}")
                _console.print(f"    [dim]... ({len(stderr_lines) - 50} lines omitted) ...[/dim]")
                for line in stderr_lines[-25:]:
                    _console.print(f"    {line}")
            else:
                for line in stderr_lines:
                    _console.print(f"    {line}")
        
        _console.print()  # Blank line after command output
    
    # Log result to trace file
    if is_trace_enabled():
        log_command_result(
            cmd_str,
            result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=duration
        )
    
    # Now check for errors if requested
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr
        )
    
    return result
