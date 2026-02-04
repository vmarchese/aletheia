"""Logging configuration for Aletheia using structlog."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import structlog

_logging_configured = False


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

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
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
        foreign_pre_chain=shared_processors,
    )
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)

    _logging_configured = True


def enable_session_file_logging(session_dir: Path) -> None:
    """Add a file handler for session trace logging.

    Call this after setup_logging() when a session is created or resumed
    in verbose mode. Appends logs to {session_dir}/aletheia_trace.log.

    Args:
        session_dir: Session directory path.
    """
    session_dir.mkdir(parents=True, exist_ok=True)
    trace_file = session_dir / "aletheia_trace.log"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    file_handler = logging.FileHandler(trace_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
            foreign_pre_chain=shared_processors,
        )
    )
    logging.root.addHandler(file_handler)
