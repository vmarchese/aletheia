"""
Utility functions and helpers.

Common utilities for retry logic, validation, command execution, and other shared functionality.
"""

from aletheia.utils.command import (
    is_verbose_commands,
    run_command,
    set_verbose_commands,
)
from aletheia.utils.logging import enable_session_file_logging, setup_logging
from aletheia.utils.session_persistence import (
    generate_timestamp,
    sanitize_filename,
    save_logs_to_session,
    save_metrics_to_session,
    save_traces_to_session,
)

__all__ = [
    "set_verbose_commands",
    "is_verbose_commands",
    "run_command",
    "setup_logging",
    "enable_session_file_logging",
    "save_logs_to_session",
    "save_metrics_to_session",
    "save_traces_to_session",
    "sanitize_filename",
    "generate_timestamp",
]
