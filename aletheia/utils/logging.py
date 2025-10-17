"""Trace logging for verbose mode (-vv).

This module provides comprehensive trace logging for Aletheia's verbose mode.
When enabled with -vv, it logs:
- All LLM prompts with metadata
- All external command executions with output
- Agent state transitions
- Function entry/exit points

Logs are written to: ~/.aletheia/sessions/{session_id}/aletheia_trace.log
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel


# Global state for trace logging
_TRACE_ENABLED = False
_TRACE_LOGGER: Optional[logging.Logger] = None
_TRACE_FILE_PATH: Optional[Path] = None
_console = Console(stderr=True)


def enable_trace_logging(session_dir: Path) -> None:
    """Enable trace logging to file.
    
    Args:
        session_dir: Session directory path for trace log file
    """
    global _TRACE_ENABLED, _TRACE_LOGGER, _TRACE_FILE_PATH
    
    _TRACE_ENABLED = True
    _TRACE_FILE_PATH = session_dir / "aletheia_trace.log"
    
    # Create logger
    _TRACE_LOGGER = logging.getLogger("aletheia.trace")
    _TRACE_LOGGER.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    _TRACE_LOGGER.handlers.clear()
    
    # Add file handler
    file_handler = logging.FileHandler(_TRACE_FILE_PATH, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Format: timestamp | level | message
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    _TRACE_LOGGER.addHandler(file_handler)
    
    # Log initialization
    _TRACE_LOGGER.info("=" * 80)
    _TRACE_LOGGER.info("Trace logging initialized")
    _TRACE_LOGGER.info(f"Session directory: {session_dir}")
    _TRACE_LOGGER.info("=" * 80)


def disable_trace_logging() -> None:
    """Disable trace logging."""
    global _TRACE_ENABLED, _TRACE_LOGGER, _TRACE_FILE_PATH
    
    if _TRACE_LOGGER:
        _TRACE_LOGGER.info("=" * 80)
        _TRACE_LOGGER.info("Trace logging disabled")
        _TRACE_LOGGER.info("=" * 80)
        for handler in _TRACE_LOGGER.handlers:
            handler.close()
        _TRACE_LOGGER.handlers.clear()
    
    _TRACE_ENABLED = False
    _TRACE_LOGGER = None
    _TRACE_FILE_PATH = None


def is_trace_enabled() -> bool:
    """Check if trace logging is enabled.
    
    Returns:
        True if trace logging is enabled
    """
    return _TRACE_ENABLED


def get_trace_file_path() -> Optional[Path]:
    """Get the trace log file path.
    
    Returns:
        Path to trace log file, or None if not enabled
    """
    return _TRACE_FILE_PATH


def log_prompt(
    agent_name: str,
    prompt: str,
    model: str,
    prompt_tokens: Optional[int] = None
) -> None:
    """Log an LLM prompt with metadata.
    
    Args:
        agent_name: Name of the agent making the call
        prompt: The prompt text
        model: Model being used
        prompt_tokens: Estimated token count (optional)
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    timestamp = datetime.now().isoformat()
    
    # Log to file with full details
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(f"LLM PROMPT | Agent: {agent_name} | Model: {model}")
    _TRACE_LOGGER.info(f"Timestamp: {timestamp}")
    if prompt_tokens:
        _TRACE_LOGGER.info(f"Estimated tokens: {prompt_tokens}")
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(prompt)
    _TRACE_LOGGER.info("-" * 80)
    
    # Log to console with syntax highlighting
    _console.print(f"\n[bold magenta]📝 LLM Prompt ({agent_name})[/bold magenta]")
    if prompt_tokens:
        _console.print(f"[dim]Model: {model} | Time: {timestamp} | Tokens: ~{prompt_tokens}[/dim]")
    else:
        _console.print(f"[dim]Model: {model} | Time: {timestamp}[/dim]")
    
    # Syntax highlight the prompt
    syntax = Syntax(prompt, "markdown", theme="monokai", line_numbers=False)
    panel = Panel(syntax, border_style="magenta")
    _console.print(panel)


def log_prompt_response(
    agent_name: str,
    response: str,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None
) -> None:
    """Log an LLM response with metadata.
    
    Args:
        agent_name: Name of the agent receiving the response
        response: The response text
        completion_tokens: Completion token count (optional)
        total_tokens: Total token count (optional)
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    timestamp = datetime.now().isoformat()
    
    # Log to file
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(f"LLM RESPONSE | Agent: {agent_name}")
    _TRACE_LOGGER.info(f"Timestamp: {timestamp}")
    if completion_tokens:
        _TRACE_LOGGER.info(f"Completion tokens: {completion_tokens}")
    if total_tokens:
        _TRACE_LOGGER.info(f"Total tokens: {total_tokens}")
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(response)
    _TRACE_LOGGER.info("-" * 80)
    
    # Log to console
    _console.print(f"\n[bold green]✅ LLM Response ({agent_name})[/bold green]")
    token_info = []
    if completion_tokens:
        token_info.append(f"Completion tokens: {completion_tokens}")
    if total_tokens:
        token_info.append(f"Total tokens: {total_tokens}")
    
    if token_info:
        _console.print(f"[dim]Time: {timestamp} | {' | '.join(token_info)}[/dim]")
    else:
        _console.print(f"[dim]Time: {timestamp}[/dim]")
    
    # Show truncated response in console
    if len(response) > 500:
        _console.print(f"{response[:500]}[dim]... (truncated, see trace log for full response)[/dim]\n")
    else:
        _console.print(f"{response}\n")


def log_command(
    command: str,
    cwd: Optional[str] = None,
    env_summary: Optional[str] = None
) -> None:
    """Log command execution start.
    
    Args:
        command: Command string
        cwd: Working directory
        env_summary: Summary of relevant environment variables
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    timestamp = datetime.now().isoformat()
    
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(f"COMMAND START | Timestamp: {timestamp}")
    _TRACE_LOGGER.info(f"Command: {command}")
    if cwd:
        _TRACE_LOGGER.info(f"Working directory: {cwd}")
    if env_summary:
        _TRACE_LOGGER.info(f"Environment: {env_summary}")
    _TRACE_LOGGER.info("-" * 80)


def log_command_result(
    command: str,
    exit_code: int,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    duration_seconds: Optional[float] = None
) -> None:
    """Log command execution result.
    
    Args:
        command: Command string
        exit_code: Command exit code
        stdout: Standard output
        stderr: Standard error
        duration_seconds: Execution duration
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    timestamp = datetime.now().isoformat()
    
    _TRACE_LOGGER.info("-" * 80)
    _TRACE_LOGGER.info(f"COMMAND END | Timestamp: {timestamp}")
    _TRACE_LOGGER.info(f"Command: {command}")
    _TRACE_LOGGER.info(f"Exit code: {exit_code}")
    if duration_seconds is not None:
        _TRACE_LOGGER.info(f"Duration: {duration_seconds:.3f}s")
    _TRACE_LOGGER.info("-" * 80)
    
    if stdout:
        _TRACE_LOGGER.info("STDOUT:")
        _TRACE_LOGGER.info(stdout)
    
    if stderr:
        _TRACE_LOGGER.info("STDERR:")
        _TRACE_LOGGER.info(stderr)
    
    _TRACE_LOGGER.info("-" * 80)


def log_agent_transition(
    from_agent: Optional[str],
    to_agent: str,
    reason: Optional[str] = None
) -> None:
    """Log agent-to-agent transition.
    
    Args:
        from_agent: Previous agent name (None if starting)
        to_agent: Next agent name
        reason: Reason for transition
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    timestamp = datetime.now().isoformat()
    
    _TRACE_LOGGER.info("=" * 80)
    if from_agent:
        _TRACE_LOGGER.info(f"AGENT TRANSITION | {from_agent} → {to_agent}")
    else:
        _TRACE_LOGGER.info(f"AGENT START | {to_agent}")
    _TRACE_LOGGER.info(f"Timestamp: {timestamp}")
    if reason:
        _TRACE_LOGGER.info(f"Reason: {reason}")
    _TRACE_LOGGER.info("=" * 80)
    
    # Console output
    if from_agent:
        _console.print(f"\n[bold blue]🔄 Agent Transition: {from_agent} → {to_agent}[/bold blue]")
    else:
        _console.print(f"\n[bold blue]🚀 Starting Agent: {to_agent}[/bold blue]")
    if reason:
        _console.print(f"[dim]Reason: {reason}[/dim]")
    _console.print()


def log_function_entry(
    function_name: str,
    args: Optional[Dict[str, Any]] = None
) -> None:
    """Log function entry for debugging.
    
    Args:
        function_name: Name of the function
        args: Function arguments (optional)
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    _TRACE_LOGGER.debug(f"→ ENTER {function_name}")
    if args:
        _TRACE_LOGGER.debug(f"  Args: {args}")


def log_function_exit(
    function_name: str,
    result: Optional[Any] = None
) -> None:
    """Log function exit for debugging.
    
    Args:
        function_name: Name of the function
        result: Return value (optional)
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    _TRACE_LOGGER.debug(f"← EXIT {function_name}")
    if result is not None:
        _TRACE_LOGGER.debug(f"  Result: {result}")


def log_info(message: str) -> None:
    """Log an informational message.
    
    Args:
        message: Message to log
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    _TRACE_LOGGER.info(message)


def log_warning(message: str) -> None:
    """Log a warning message.
    
    Args:
        message: Warning message
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    _TRACE_LOGGER.warning(message)


def log_error(message: str, exception: Optional[Exception] = None) -> None:
    """Log an error message.
    
    Args:
        message: Error message
        exception: Exception object (optional)
    """
    if not _TRACE_ENABLED or not _TRACE_LOGGER:
        return
    
    _TRACE_LOGGER.error(message)
    if exception:
        _TRACE_LOGGER.exception(exception)
