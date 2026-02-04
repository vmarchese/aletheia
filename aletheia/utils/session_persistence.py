"""Utilities for persisting data to session folders.

This module provides helper functions for saving logs, metrics, and traces
to the session's data directory with consistent naming and structure.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize a string for use in a filename.

    Args:
        name: The string to sanitize
        max_length: Maximum length of the sanitized string

    Returns:
        Sanitized filename-safe string
    """
    # Replace invalid characters with underscores
    sanitized = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    # Remove consecutive underscores
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    # Trim to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized or "unnamed"


def generate_timestamp() -> str:
    """Generate a timestamp string for filenames.

    Returns:
        ISO 8601 timestamp with colons replaced by hyphens (e.g., "2025-10-21T14-30-45")
    """
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def save_logs_to_session(
    session_data_dir: Path,
    logs: list[dict[str, Any]],
    metadata: dict[str, Any],
    source: str = "kubernetes",
    identifier: str | None = None,
) -> Path:
    """Save logs to the session's data/logs directory.

    Args:
        session_data_dir: Path to session's data directory (session.data_dir)
        logs: List of log entries to save
        metadata: Metadata about the logs (pod, namespace, time_range, etc.)
        source: Source of the logs (e.g., "kubernetes")
        identifier: Optional identifier for the log file (e.g., pod name)

    Returns:
        Path to the saved log file

    Raises:
        OSError: If file cannot be written
    """
    logs_dir = session_data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = generate_timestamp()
    if identifier:
        sanitized_id = sanitize_filename(identifier)
        filename = f"{source}_{sanitized_id}_{timestamp}.json"
    else:
        filename = f"{source}_{timestamp}.json"

    file_path = logs_dir / filename

    # Prepare data structure
    data = {
        "source": source,
        "metadata": {
            **metadata,
            "collected_at": datetime.now().isoformat(),
            "count": len(logs),
        },
        "data": logs,
    }

    # Write to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d log entries to %s", len(logs), file_path)
        return file_path
    except OSError as e:
        logger.error("Failed to save logs to %s: %s", file_path, e)
        raise


def save_metrics_to_session(
    session_data_dir: Path,
    metrics: list[dict[str, Any]],
    metadata: dict[str, Any],
    source: str = "prometheus",
    query: str | None = None,
) -> Path:
    """Save metrics to the session's data/metrics directory.

    Args:
        session_data_dir: Path to session's data directory (session.data_dir)
        metrics: List of metric data points to save
        metadata: Metadata about the metrics (query, time_range, etc.)
        source: Source of the metrics (e.g., "prometheus")
        query: Optional PromQL query string for filename generation

    Returns:
        Path to the saved metrics file

    Raises:
        OSError: If file cannot be written
    """
    metrics_dir = session_data_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = generate_timestamp()
    if query:
        # Use first 40 chars of sanitized query
        sanitized_query = sanitize_filename(query, max_length=40)
        filename = f"{source}_{sanitized_query}_{timestamp}.json"
    else:
        filename = f"{source}_{timestamp}.json"

    file_path = metrics_dir / filename

    # Prepare data structure
    data = {
        "source": source,
        "metadata": {
            **metadata,
            "collected_at": datetime.now().isoformat(),
            "count": len(metrics),
        },
        "data": metrics,
    }

    # Write to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d metric data points to %s", len(metrics), file_path)
        return file_path
    except OSError as e:
        logger.error("Failed to save metrics to %s: %s", file_path, e)
        raise


def save_traces_to_session(
    session_data_dir: Path,
    traces: list[dict[str, Any]],
    metadata: dict[str, Any],
    source: str = "jaeger",
    identifier: str | None = None,
) -> Path:
    """Save traces to the session's data/traces directory.

    Args:
        session_data_dir: Path to session's data directory (session.data_dir)
        traces: List of trace data to save
        metadata: Metadata about the traces
        source: Source of the traces (e.g., "jaeger")
        identifier: Optional identifier for the trace file

    Returns:
        Path to the saved traces file

    Raises:
        OSError: If file cannot be written
    """
    traces_dir = session_data_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = generate_timestamp()
    if identifier:
        sanitized_id = sanitize_filename(identifier)
        filename = f"{source}_{sanitized_id}_{timestamp}.json"
    else:
        filename = f"{source}_{timestamp}.json"

    file_path = traces_dir / filename

    # Prepare data structure
    data = {
        "source": source,
        "metadata": {
            **metadata,
            "collected_at": datetime.now().isoformat(),
            "count": len(traces),
        },
        "data": traces,
    }

    # Write to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d traces to %s", len(traces), file_path)
        return file_path
    except OSError as e:
        logger.error("Failed to save traces to %s: %s", file_path, e)
        raise
