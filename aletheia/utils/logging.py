"""Logging configuration for Aletheia using structlog."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import structlog

_logging_configured = False

# Module-level state for session file logging
_session_file_handler: logging.FileHandler | None = None
_original_log_level: int = logging.INFO

_SHARED_PROCESSORS: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.StackInfoRenderer(),
    structlog.dev.set_exc_info,
    structlog.processors.TimeStamper(fmt="iso"),
]


def setup_logging(level: str | None = None, session_dir: Path | None = None) -> None:
    """Configure structlog for the entire application.

    Bridges stdlib logging so all existing logging.getLogger() loggers
    also go through structlog processors.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
               Falls back to ALETHEIA_LOG_LEVEL env var, then INFO.
        session_dir: Optional session directory. When provided, adds a
                     file handler writing to {session_dir}/aletheia_trace.log.
    """
    global _logging_configured

    log_level_str = (level or os.environ.get("ALETHEIA_LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)

    renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Bridge stdlib logging through structlog
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if session_dir is not None:
        session_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            session_dir / "aletheia_trace.log", mode="a", encoding="utf-8"
        )
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        level=numeric_level,
        handlers=handlers,
        force=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=_SHARED_PROCESSORS,
    )
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    # Silence noisy third-party HTTP loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("agent_framework").setLevel(logging.WARNING)

    _logging_configured = True


def enable_session_file_logging(session_dir: Path) -> None:
    """Enable DEBUG-level file logging for a verbose session.

    Call this after setup_logging() when a session is created or resumed
    in verbose mode. Switches structlog to route through stdlib logging
    so that per-handler level filtering applies:
    - The trace file captures all DEBUG messages (structlog + stdlib)
    - The console continues showing only the previous log level

    Args:
        session_dir: Session directory path.
    """
    global _session_file_handler, _original_log_level

    session_dir.mkdir(parents=True, exist_ok=True)
    trace_file = session_dir / "aletheia_trace.log"

    # Save current level for restoration
    _original_log_level = logging.root.level

    # Switch structlog to route through stdlib logging instead of
    # PrintLoggerFactory (stderr). This way handler-level filtering
    # controls what goes to console vs file.
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Lower root logger to DEBUG so messages reach file handler
    logging.root.setLevel(logging.DEBUG)

    # Pin existing console handlers to the previous level and set formatter
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
        foreign_pre_chain=_SHARED_PROCESSORS,
    )
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(_original_log_level)
            handler.setFormatter(console_formatter)

    # Add file handler at DEBUG level
    file_handler = logging.FileHandler(trace_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
            foreign_pre_chain=_SHARED_PROCESSORS,
        )
    )
    logging.root.addHandler(file_handler)
    _session_file_handler = file_handler


def disable_session_file_logging() -> None:
    """Remove session file handler and restore previous logging levels.

    Restores structlog to use PrintLoggerFactory (direct stderr output).
    Safe to call when no session file logging is active (no-op).
    """
    global _session_file_handler

    if _session_file_handler is not None:
        logging.root.removeHandler(_session_file_handler)
        _session_file_handler.close()
        _session_file_handler = None

    # Restore root logger level
    logging.root.setLevel(_original_log_level)

    # Restore console handler levels (remove explicit level so they inherit)
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(logging.NOTSET)

    # Restore structlog to PrintLoggerFactory (direct stderr output)
    renderer = structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_original_log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
