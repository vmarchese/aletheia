"""
Utility functions and helpers.

Common utilities for retry logic, validation, command execution, and other shared functionality.
"""

from aletheia.utils.command import set_verbose_commands, is_verbose_commands, run_command
from aletheia.utils.logging import (
    enable_trace_logging,
    disable_trace_logging,
    is_trace_enabled,
    get_trace_file_path,
    log_prompt,
    log_prompt_response,
    log_agent_transition,
)

__all__ = [
    "set_verbose_commands",
    "is_verbose_commands",
    "run_command",
    "enable_trace_logging",
    "disable_trace_logging",
    "is_trace_enabled",
    "get_trace_file_path",
    "log_prompt",
    "log_prompt_response",
    "log_agent_transition",
]
