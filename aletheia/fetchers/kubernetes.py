"""Kubernetes data fetcher for pod logs, events, and resource status."""

import json
import logging
import random
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aletheia.utils import run_command
from aletheia.fetchers.base import BaseFetcher, FetchResult, ConnectionError, QueryError
from aletheia.utils.retry import retry_with_backoff
from aletheia.config import Config
from aletheia.utils.logging import log_debug


class KubernetesFetcher(BaseFetcher):
    """Fetcher for Kubernetes logs via kubectl.

    Delegates authentication to ~/.kube/config and supports context/namespace
    selection. Implements intelligent log sampling strategy:
    - Captures all ERROR and FATAL level logs
    - Random samples other levels to reach target count
    """

    def __init__(self, config: Config):
        """Initialize the Kubernetes fetcher.

        Args:
            config: Configuration dictionary for the fetcher
        """
        super().__init__(config)


    @retry_with_backoff(retries=3, delays=(1, 2, 4))
    def fetch(
        self,
        pod: str,
        namespace: str,
        container: Optional[str] = None,
        time_window: Optional[Tuple[datetime, datetime]] = None,
        **kwargs: Any
    ) -> FetchResult:
        """Fetch logs from Kubernetes pods.

        Args:
            time_window: Optional tuple of (start_time, end_time) for filtering logs
            Additional parameters:
            - namespace: Kubernetes namespace (default from config or "default")
            - pod: Pod name or selector (default: None - all pods)
            - container: Container name (default: None - all containers)

        Returns:
            FetchResult with logs, summary, and metadata

        Raises:
            ConnectionError: If kubectl command fails
            QueryError: If log parsing fails
        """
        log_debug(f"KubernetesDataFetcher::fetch::Starting fetch with time_window={time_window}, kwargs={kwargs}")

        # Set default time window to 2 hours if not provided
        if time_window is None:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=2)
            time_window = (start_time, end_time)
            log_debug(f"KubernetesDataFetcher::fetch::Using default 2-hour time window: {time_window}")

        # Fetch raw logs
        raw_logs = self._fetch_raw_logs(namespace, pod, container, time_window)

        # Parse logs
        parsed_logs = self._parse_logs(raw_logs)

        # Apply sampling strategy
        sampled_logs = self._sample_logs(parsed_logs, sample_size, always_include_levels)

        # Determine actual time range
        actual_time_range = self._get_time_range(sampled_logs, time_window)

        # Generate summary
        summary = self._generate_summary(sampled_logs)

        return FetchResult(
            source="kubernetes",
            data=sampled_logs,
            summary=summary,
            count=len(sampled_logs),
            time_range=actual_time_range,
            metadata={
                "context": self.config["context"],
                "namespace": namespace,
                "pod": pod,
                "container": container,
                "sample_size": sample_size,
                "always_include_levels": always_include_levels
            }
        )

    def _fetch_raw_logs(
        self,
        namespace: str,
        pod: Optional[str],
        container: Optional[str],
        time_window: Optional[Tuple[datetime, datetime]]
    ) -> str:
        """Fetch raw logs from kubectl.

        Args:
            namespace: Kubernetes namespace
            pod: Pod name or selector
            container: Container name
            time_window: Optional time window for log filtering

        Returns:
            Raw log output as string

        Raises:
            ConnectionError: If kubectl command fails
        """
        log_debug(f"KubernetesDataFetcher::_fetch_raw_logs::Starting _fetch_raw_logs for namespace={namespace}, pod={pod}, container={container}, time_window={time_window}")
        cmd = [
            "kubectl",
            "--context", self.config["context"],
            "--namespace", namespace,
            "logs"
        ]

        if pod:
            cmd.append(pod)
        else:
            raise QueryError("Pod name or selector is required for log fetching")

        if container:
            cmd.extend(["--container", container])

        # Add time window if specified
        if time_window:
            since = time_window[0]
            # kubectl doesn't support absolute timestamps, calculate duration
            now = datetime.now()
            duration = now - since
            # Convert to kubectl duration format (e.g., "2h", "30m")
            if duration.days > 0:
                cmd.extend(["--since", f"{duration.days * 24}h"])
            elif duration.seconds >= 3600:
                cmd.extend(["--since", f"{duration.seconds // 3600}h"])
            elif duration.seconds >= 60:
                cmd.extend(["--since", f"{duration.seconds // 60}m"])
            else:
                cmd.extend(["--since", f"{duration.seconds}s"])

        try:
            result = run_command(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise ConnectionError(
                f"kubectl command failed: {e.stderr}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ConnectionError(
                "kubectl command timed out after 30 seconds"
            ) from e

    def _parse_logs(self, raw_logs: str) -> List[Dict[str, Any]]:
        """Parse raw log output into structured format.

        Args:
            raw_logs: Raw log string from kubectl

        Returns:
            List of parsed log entries as dictionaries

        Raises:
            QueryError: If log parsing fails
        """
        log_debug(f"KubernetesDataFetcher::_parse_logs::Starting _parse_logs with {len(raw_logs)} characters of raw logs")
        parsed = []

        for line in raw_logs.strip().split("\n"):
            if not line.strip():
                continue

            # Try to parse as JSON first (common in structured logging)
            try:
                log_entry = json.loads(line)
                # Ensure we have level and message fields
                if "level" not in log_entry:
                    log_entry["level"] = self._extract_level_from_message(
                        log_entry.get("message", line)
                    )
                parsed.append(log_entry)
            except json.JSONDecodeError:
                # Fall back to plain text parsing
                level = self._extract_level_from_message(line)
                parsed.append({
                    "message": line,
                    "level": level,
                    "timestamp": datetime.now().isoformat()
                })

        return parsed

    def _extract_level_from_message(self, message: str) -> str:
        """Extract log level from message text.

        Args:
            message: Log message string

        Returns:
            Extracted log level or "INFO" as default
        """
        log_debug(f"KubernetesDataFetcher::_extract_level_from_message::Starting _extract_level_from_message for message: {message[:50]}...")
        message_upper = message.upper()

        # Check for common log level indicators
        for level in ["FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"]:
            if level in message_upper:
                # Normalize to standard levels
                if level == "WARNING":
                    return "WARN"
                return level

        return "INFO"

    def _sample_logs(
        self,
        logs: List[Dict[str, Any]],
        sample_size: int,
        always_include_levels: List[str]
    ) -> List[Dict[str, Any]]:
        """Apply intelligent sampling strategy to logs.

        Strategy:
        1. Include all logs with levels in always_include_levels
        2. Randomly sample remaining logs to reach sample_size

        Args:
            logs: List of parsed log entries
            sample_size: Target number of logs to return
            always_include_levels: Log levels to always include

        Returns:
            Sampled list of log entries
        """
        log_debug(f"KubernetesDataFetcher::_sample_logs::Starting _sample_logs with {len(logs)} logs, sample_size={sample_size}, always_include_levels={always_include_levels}")
        if len(logs) <= sample_size:
            return logs

        # Separate priority logs from others
        priority_logs = [
            log for log in logs
            if log.get("level", "INFO").upper() in always_include_levels
        ]
        other_logs = [
            log for log in logs
            if log.get("level", "INFO").upper() not in always_include_levels
        ]

        # If priority logs exceed sample size, return all priority logs
        if len(priority_logs) >= sample_size:
            return priority_logs

        # Calculate how many other logs we can include
        remaining_slots = sample_size - len(priority_logs)

        # Random sample from other logs
        if remaining_slots > 0 and other_logs:
            sampled_others = random.sample(
                other_logs,
                min(remaining_slots, len(other_logs))
            )
        else:
            sampled_others = []

        return priority_logs + sampled_others

    def _get_time_range(
        self,
        logs: List[Dict[str, Any]],
        requested_window: Optional[Tuple[datetime, datetime]]
    ) -> Tuple[datetime, datetime]:
        """Determine actual time range of fetched logs.

        Args:
            logs: List of log entries
            requested_window: Originally requested time window

        Returns:
            Tuple of (start_time, end_time) for actual log range
        """
        log_debug(f"KubernetesDataFetcher::_get_time_range::Starting _get_time_range with {len(logs)} logs, requested_window={requested_window}")
        if not logs:
            # No logs, return requested window or current time
            if requested_window:
                return requested_window
            now = datetime.now()
            return (now, now)

        # Try to extract timestamps from logs
        timestamps = []
        for log in logs:
            ts_str = log.get("timestamp") or log.get("time") or log.get("ts")
            if ts_str:
                try:
                    # Try parsing ISO format
                    timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
                except (ValueError, AttributeError):
                    pass

        if timestamps:
            return (min(timestamps), max(timestamps))

        # Fall back to requested window or current time
        if requested_window:
            return requested_window
        now = datetime.now()
        return (now, now)

    def _generate_summary(self, logs: List[Dict[str, Any]]) -> str:
        """Generate human-readable summary of logs.

        Args:
            logs: List of log entries

        Returns:
            Summary string
        """
        log_debug(f"KubernetesDataFetcher::_generate_summary::Starting _generate_summary with {len(logs)} logs")
        if not logs:
            return "No logs found"

        # Count logs by level
        level_counts: Dict[str, int] = {}
        for log in logs:
            level = log.get("level", "INFO").upper()
            level_counts[level] = level_counts.get(level, 0) + 1

        # Find most common error patterns (if any errors)
        error_logs = [log for log in logs if log.get("level", "").upper() in ["ERROR", "FATAL"]]
        error_patterns: Dict[str, int] = {}

        if error_logs:
            for log in error_logs[:50]:  # Sample first 50 errors
                message = log.get("message", "")
                # Extract error pattern (first 50 chars or up to first colon)
                pattern = message[:50].split(":")[0] if ":" in message[:50] else message[:50]
                error_patterns[pattern] = error_patterns.get(pattern, 0) + 1

        # Build summary
        parts = [f"{len(logs)} logs"]

        # Add level breakdown
        level_parts = [f"{count} {level}" for level, count in sorted(level_counts.items())]
        if level_parts:
            parts.append(f"({', '.join(level_parts)})")

        # Add top error pattern
        if error_patterns:
            top_error = max(error_patterns.items(), key=lambda x: x[1])
            parts.append(f", top error: '{top_error[0]}' ({top_error[1]}x)")

        return " ".join(parts)

    def list_pods(self, namespace: Optional[str] = None, selector: Optional[str] = None) -> List[str]:
        """List pods in Kubernetes cluster.

        Args:
            namespace: Kubernetes namespace (default from config or "default")
            selector: Label selector (e.g., "app=payments-svc")

        Returns:
            List of pod names

        Raises:
            ConnectionError: If kubectl command fails
        """
        log_debug(f"KubernetesDataFetcher::list_pods::Starting list_pods with namespace={namespace}, selector={selector}")
        namespace = namespace or self.config.get("namespace", "default")

        cmd = [
            "kubectl",
            "--context", self.config["context"],
            "--namespace", namespace,
            "get", "pods",
            "-o", "jsonpath={.items[*].metadata.name}"
        ]

        if selector:
            cmd.extend(["-l", selector])

        try:
            result = run_command(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            pods = result.stdout.strip().split()
            return [p for p in pods if p]  # Filter empty strings
        except subprocess.CalledProcessError as e:
            raise ConnectionError(
                f"kubectl command failed: {e.stderr}"
            ) from e

    def get_pod_status(self, pod: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get status information for a pod.

        Args:
            pod: Pod name
            namespace: Kubernetes namespace (default from config or "default")

        Returns:
            Dictionary with pod status information

        Raises:
            ConnectionError: If kubectl command fails
        """
        log_debug(f"KubernetesDataFetcher::get_pod_status::Starting get_pod_status for pod={pod}, namespace={namespace}")
        namespace = namespace or self.config.get("namespace", "default")

        cmd = [
            "kubectl",
            "--context", self.config["context"],
            "--namespace", namespace,
            "get", "pod", pod,
            "-o", "json"
        ]

        try:
            result = run_command(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            pod_info = json.loads(result.stdout)

            # Extract relevant status information
            status = pod_info.get("status", {})
            return {
                "name": pod_info["metadata"]["name"],
                "namespace": pod_info["metadata"]["namespace"],
                "phase": status.get("phase"),
                "conditions": status.get("conditions", []),
                "container_statuses": status.get("containerStatuses", []),
                "start_time": status.get("startTime")
            }
        except subprocess.CalledProcessError as e:
            raise ConnectionError(
                f"kubectl command failed: {e.stderr}"
            ) from e
        except (json.JSONDecodeError, KeyError) as e:
            raise QueryError(
                f"Failed to parse pod status: {str(e)}"
            ) from e

    def test_connection(self) -> bool:
        """Test connection to Kubernetes cluster.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection test fails
        """
        log_debug("KubernetesDataFetcher::test_connection::Starting test_connection")
        cmd = [
            "kubectl",
            "--context", self.config["context"],
            "cluster-info"
        ]

        try:
            result = run_command(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            return "Kubernetes" in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise ConnectionError(
                f"Kubernetes connection test failed: {getattr(e, 'stderr', str(e))}"
            ) from e

    def get_capabilities(self) -> Dict[str, Any]:
        """Get fetcher capabilities.

        Returns:
            Dictionary describing fetcher capabilities
        """
        log_debug("KubernetesDataFetcher::get_capabilities::Starting get_capabilities")
        return {
            "supports_time_window": True,
            "supports_streaming": False,
            "max_sample_size": 10000,
            "data_types": ["logs"],
            "sampling_strategies": ["level-based", "random"],
            "retry_enabled": True,
            "default_retries": 3
        }
