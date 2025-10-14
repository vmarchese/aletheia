"""Data summarization utilities for logs and metrics.

This module provides comprehensive summarization capabilities for observability data
collected by fetchers. It generates concise, informative summaries that highlight
key patterns, anomalies, and actionable insights.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter
import re


class LogSummarizer:
    """Summarizer for log data with pattern detection and clustering."""

    def __init__(self):
        """Initialize log summarizer."""
        pass

    def summarize(
        self,
        logs: List[Dict[str, Any]],
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive summary of log data.

        Args:
            logs: List of log entries (dicts with level, message, timestamp, etc.)
            time_range: Optional tuple of (start_time, end_time) for context

        Returns:
            Dictionary containing:
                - count: Total number of logs
                - time_range: Tuple of (start, end) timestamps
                - level_counts: Dict mapping level to count
                - error_clusters: List of error patterns with counts
                - top_errors: List of top N error patterns
                - summary: Human-readable summary string
        """
        if not logs:
            return {
                "count": 0,
                "time_range": time_range or (None, None),
                "level_counts": {},
                "error_clusters": {},
                "top_errors": [],
                "summary": "No logs found"
            }

        # Count logs by level
        level_counts = self._count_by_level(logs)

        # Extract error patterns
        error_logs = [
            log for log in logs
            if log.get("level", "").upper() in ["ERROR", "FATAL", "CRITICAL"]
        ]
        error_clusters = self._cluster_errors(error_logs)

        # Get top error patterns
        top_errors = self._get_top_errors(error_clusters, n=3)

        # Extract time range from logs if not provided
        if not time_range:
            time_range = self._extract_time_range(logs)

        # Generate human-readable summary
        summary = self._generate_text_summary(
            len(logs),
            level_counts,
            top_errors
        )

        return {
            "count": len(logs),
            "time_range": time_range,
            "level_counts": level_counts,
            "error_clusters": error_clusters,
            "top_errors": top_errors,
            "summary": summary
        }

    def _count_by_level(self, logs: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count logs by level.

        Args:
            logs: List of log entries

        Returns:
            Dictionary mapping level to count
        """
        level_counts: Dict[str, int] = {}
        for log in logs:
            level = log.get("level", "INFO").upper()
            level_counts[level] = level_counts.get(level, 0) + 1
        return level_counts

    def _cluster_errors(self, error_logs: List[Dict[str, Any]]) -> Dict[str, int]:
        """Cluster similar error messages together.

        Strategy:
        1. Extract error pattern from message (first meaningful part)
        2. Normalize whitespace and common variables
        3. Count occurrences of each pattern

        Args:
            error_logs: List of error-level log entries

        Returns:
            Dictionary mapping error pattern to count
        """
        if not error_logs:
            return {}

        patterns: Dict[str, int] = {}

        for log in error_logs:
            message = log.get("message", "")
            if not message:
                continue

            # Extract pattern (normalize to remove variable parts)
            pattern = self._extract_error_pattern(message)

            if pattern:
                patterns[pattern] = patterns.get(pattern, 0) + 1

        return patterns

    def _extract_error_pattern(self, message: str) -> str:
        """Extract error pattern from message.

        Strategy:
        1. Take first part before colon (common error format)
        2. Normalize numbers, IDs, paths to reduce variability
        3. Limit to reasonable length

        Args:
            message: Error message string

        Returns:
            Normalized error pattern
        """
        # Take first part before colon or limit to 80 chars
        if ":" in message[:100]:
            pattern = message[:100].split(":", 1)[0].strip()
        else:
            pattern = message[:80].strip()

        # Normalize common variable patterns
        # Replace UUIDs
        pattern = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '<UUID>',
            pattern,
            flags=re.IGNORECASE
        )

        # Replace hex values (before other numbers)
        pattern = re.sub(r'0x[0-9a-f]+', '<HEX>', pattern, flags=re.IGNORECASE)

        # Replace file paths
        pattern = re.sub(r'/[\w/.-]+\.\w+', '<PATH>', pattern)

        # Replace sequences of digits (including short numbers like "at line 42")
        pattern = re.sub(r'\b\d+\b', '<NUM>', pattern)

        # Normalize whitespace
        pattern = ' '.join(pattern.split())

        return pattern

    def _get_top_errors(
        self,
        error_clusters: Dict[str, int],
        n: int = 3
    ) -> List[Tuple[str, int]]:
        """Get top N error patterns by frequency.

        Args:
            error_clusters: Dictionary of pattern to count
            n: Number of top errors to return

        Returns:
            List of (pattern, count) tuples, sorted by count descending
        """
        sorted_errors = sorted(
            error_clusters.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_errors[:n]

    def _extract_time_range(
        self,
        logs: List[Dict[str, Any]]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extract time range from log timestamps.

        Args:
            logs: List of log entries

        Returns:
            Tuple of (earliest_time, latest_time), or (None, None) if no timestamps
        """
        timestamps = []

        for log in logs:
            # Try multiple common timestamp field names
            ts_str = (
                log.get("timestamp") or
                log.get("time") or
                log.get("ts") or
                log.get("@timestamp")
            )

            if ts_str:
                try:
                    # Try parsing ISO format
                    if isinstance(ts_str, str):
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        timestamps.append(ts)
                    elif isinstance(ts_str, datetime):
                        timestamps.append(ts_str)
                except (ValueError, AttributeError):
                    pass

        if timestamps:
            return (min(timestamps), max(timestamps))

        return (None, None)

    def _generate_text_summary(
        self,
        total_count: int,
        level_counts: Dict[str, int],
        top_errors: List[Tuple[str, int]]
    ) -> str:
        """Generate human-readable text summary.

        Args:
            total_count: Total number of logs
            level_counts: Dictionary of level to count
            top_errors: List of (pattern, count) tuples

        Returns:
            Summary string
        """
        parts = [f"{total_count} logs"]

        # Add level breakdown
        if level_counts:
            level_parts = [
                f"{count} {level}"
                for level, count in sorted(level_counts.items())
            ]
            parts.append(f"({', '.join(level_parts)})")

        # Add top error pattern
        if top_errors:
            top_pattern, top_count = top_errors[0]
            parts.append(f"top error: '{top_pattern}' ({top_count}x)")

        return ", ".join(parts)


class MetricSummarizer:
    """Summarizer for metric data with anomaly detection and trend analysis."""

    def __init__(self, spike_threshold: float = 3.0, drop_threshold: float = 0.33):
        """Initialize metric summarizer.

        Args:
            spike_threshold: Multiplier for spike detection (value > avg * threshold)
            drop_threshold: Multiplier for drop detection (value < avg * threshold)
        """
        self.spike_threshold = spike_threshold
        self.drop_threshold = drop_threshold

    def summarize(
        self,
        metrics_data: List[Dict[str, Any]],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive summary of metric data.

        Args:
            metrics_data: List of metric time series from Prometheus
                Format: [{"metric": {...}, "values": [[timestamp, value], ...]}]
            query: Optional PromQL query for context

        Returns:
            Dictionary containing:
                - num_series: Number of time series
                - total_points: Total number of data points
                - metric_names: Set of metric names found
                - anomalies: List of detected anomalies
                - rate_of_change: Average rate of change across series
                - summary: Human-readable summary string
        """
        if not metrics_data:
            return {
                "num_series": 0,
                "total_points": 0,
                "metric_names": set(),
                "anomalies": [],
                "rate_of_change": None,
                "summary": f"No data{' for query: ' + query if query else ''}"
            }

        num_series = len(metrics_data)
        total_points = sum(len(series.get("values", [])) for series in metrics_data)

        # Extract metric names
        metric_names = self._extract_metric_names(metrics_data)

        # Detect anomalies
        anomalies = self._detect_anomalies(metrics_data)

        # Calculate rate of change
        rate_of_change = self._calculate_rate_of_change(metrics_data)

        # Generate human-readable summary
        summary = self._generate_text_summary(
            num_series,
            total_points,
            metric_names,
            anomalies
        )

        return {
            "num_series": num_series,
            "total_points": total_points,
            "metric_names": metric_names,
            "anomalies": anomalies,
            "rate_of_change": rate_of_change,
            "summary": summary
        }

    def _extract_metric_names(
        self,
        metrics_data: List[Dict[str, Any]]
    ) -> set:
        """Extract metric names from time series data.

        Args:
            metrics_data: List of metric time series

        Returns:
            Set of metric names
        """
        metric_names = set()

        for series in metrics_data:
            metric = series.get("metric", {})
            # Try to get __name__ label (primary metric name)
            name = metric.get("__name__", "")

            # If no __name__, try to get first non-internal label
            if not name:
                for key, value in metric.items():
                    if not key.startswith("__"):
                        name = value
                        break

            if name:
                metric_names.add(name)

        return metric_names

    def _detect_anomalies(
        self,
        metrics_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in metric data (spikes, drops, trends).

        Strategy:
        1. Calculate average value for each series
        2. Detect spikes (value > avg * spike_threshold)
        3. Detect drops (value < avg * drop_threshold)
        4. Return top anomalies by severity

        Args:
            metrics_data: List of metric time series

        Returns:
            List of anomaly dictionaries with type, value, and metric info
        """
        anomalies = []

        for series in metrics_data:
            values = series.get("values", [])
            metric = series.get("metric", {})

            if len(values) < 2:
                continue

            # Extract numeric values (second element of [timestamp, value] pairs)
            try:
                numeric_values = [
                    float(v[1]) for v in values
                    if v[1] not in ["NaN", "Inf", "-Inf"]
                ]
            except (ValueError, IndexError, TypeError):
                continue

            if not numeric_values:
                continue

            # Calculate statistics
            avg_value = sum(numeric_values) / len(numeric_values)
            max_value = max(numeric_values)
            min_value = min(numeric_values)

            # Detect spikes (value significantly above average)
            # Only detect if average is meaningful (not zero/near-zero)
            if avg_value > 0.01:  # Avoid false positives on near-zero averages
                if max_value > avg_value * self.spike_threshold:
                    anomalies.append({
                        "type": "spike",
                        "value": max_value,
                        "average": avg_value,
                        "ratio": max_value / avg_value if avg_value > 0 else float('inf'),
                        "metric": metric.get("__name__", str(metric))
                    })

            # Detect drops (value significantly below average)
            if (
                min_value < avg_value * self.drop_threshold and
                avg_value > 0 and
                min_value >= 0
            ):
                anomalies.append({
                    "type": "drop",
                    "value": min_value,
                    "average": avg_value,
                    "ratio": min_value / avg_value if avg_value > 0 else 0,
                    "metric": metric.get("__name__", str(metric))
                })

        # Sort by severity (distance from average)
        anomalies.sort(
            key=lambda a: abs(a["value"] - a["average"]),
            reverse=True
        )

        return anomalies[:5]  # Return top 5 anomalies

    def _calculate_rate_of_change(
        self,
        metrics_data: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate average rate of change across all series.

        Args:
            metrics_data: List of metric time series

        Returns:
            Average rate of change, or None if cannot calculate
        """
        rates = []

        for series in metrics_data:
            values = series.get("values", [])

            if len(values) < 2:
                continue

            try:
                # Get first and last values
                first_val = float(values[0][1])
                last_val = float(values[-1][1])

                # Get time range in seconds
                first_time = float(values[0][0])
                last_time = float(values[-1][0])
                time_diff = last_time - first_time

                if time_diff > 0 and first_val not in [float('inf'), float('-inf')]:
                    rate = (last_val - first_val) / time_diff
                    rates.append(rate)

            except (ValueError, IndexError, TypeError, ZeroDivisionError):
                continue

        if rates:
            return sum(rates) / len(rates)

        return None

    def _generate_text_summary(
        self,
        num_series: int,
        total_points: int,
        metric_names: set,
        anomalies: List[Dict[str, Any]]
    ) -> str:
        """Generate human-readable text summary.

        Args:
            num_series: Number of time series
            total_points: Total data points
            metric_names: Set of metric names
            anomalies: List of detected anomalies

        Returns:
            Summary string
        """
        parts = [
            f"{num_series} time series, {total_points} data points"
        ]

        if metric_names:
            parts.append(f"metrics: {', '.join(sorted(metric_names))}")

        if anomalies:
            # Describe top anomaly
            top = anomalies[0]
            if top["type"] == "spike":
                desc = f"spike detected: {top['value']:.2f} (avg: {top['average']:.2f})"
            else:  # drop
                desc = f"drop detected: {top['value']:.2f} (avg: {top['average']:.2f})"
            parts.append(f"anomalies: {desc}")

        return "; ".join(parts)
