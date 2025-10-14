"""Prometheus metrics fetcher for time-series data and alerting.

This module provides a fetcher implementation for collecting metrics from Prometheus
servers using the HTTP API. It supports PromQL queries, time window filtering,
adaptive metric resolution, and automatic retry logic for transient failures.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from aletheia.fetchers.base import (
    BaseFetcher,
    FetchResult,
    ConnectionError,
    QueryError,
    AuthenticationError,
)
from aletheia.utils.retry import retry_with_backoff


# PromQL query templates for common use cases
PROMQL_TEMPLATES = {
    "error_rate": 'rate({metric_name}{{service="{service}",status=~"5.."}}[{window}])',
    "latency_p95": 'histogram_quantile(0.95, rate({metric_name}_bucket{{service="{service}"}}[{window}]))',
    "latency_p99": 'histogram_quantile(0.99, rate({metric_name}_bucket{{service="{service}"}}[{window}]))',
    "request_rate": 'rate({metric_name}{{service="{service}"}}[{window}])',
    "cpu_usage": 'rate(container_cpu_usage_seconds_total{{pod=~"{pod_pattern}"}}[{window}])',
    "memory_usage": 'container_memory_working_set_bytes{{pod=~"{pod_pattern}"}}',
}


class PrometheusFetcher(BaseFetcher):
    """Fetcher for Prometheus metrics via HTTP API.

    Supports PromQL query execution, template-based query construction,
    and adaptive metric resolution based on time window size.

    Configuration:
        endpoint: Prometheus server URL (required)
        credentials: Optional authentication credentials
            - type: "env" | "basic" | "bearer"
            - username_env: Environment variable for username (if type="env")
            - password_env: Environment variable for password (if type="env")
            - username: Username for basic auth (if type="basic")
            - password: Password for basic auth (if type="basic")
            - token: Bearer token (if type="bearer")
    """

    def validate_config(self) -> None:
        """Validate Prometheus configuration.

        Raises:
            ValueError: If required configuration is missing
        """
        if "endpoint" not in self.config:
            raise ValueError("Prometheus endpoint is required in config")

        # Validate endpoint format
        endpoint = self.config["endpoint"]
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("Prometheus endpoint must start with http:// or https://")

    def test_connection(self) -> bool:
        """Test connectivity to Prometheus server.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            url = f"{self.config['endpoint']}/api/v1/query"
            headers = self._get_headers()

            # Simple query to test connection
            response = requests.get(
                url,
                params={"query": "up"},
                headers=headers,
                timeout=10
            )

            if response.status_code == 401:
                raise AuthenticationError("Authentication failed: Invalid credentials")

            response.raise_for_status()

            data = response.json()
            if data.get("status") != "success":
                raise ConnectionError(f"Prometheus query failed: {data.get('error', 'Unknown error')}")

            return True

        except requests.exceptions.Timeout:
            raise ConnectionError("Connection to Prometheus timed out")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to Prometheus: {str(e)}")

    def get_capabilities(self) -> Dict[str, Any]:
        """Report fetcher capabilities.

        Returns:
            Dictionary describing fetcher capabilities
        """
        return {
            "supports_time_window": True,
            "supports_streaming": False,
            "max_sample_size": 11000,  # Prometheus default max samples
            "data_types": ["metrics"],
            "query_language": "PromQL",
            "templates": list(PROMQL_TEMPLATES.keys())
        }

    @retry_with_backoff(retries=3, delays=(1, 2, 4))
    def fetch(
        self,
        time_window: Optional[Tuple[datetime, datetime]] = None,
        **kwargs: Any
    ) -> FetchResult:
        """Fetch metrics from Prometheus.

        Args:
            time_window: Optional tuple of (start_time, end_time) for range queries
            **kwargs: Additional parameters:
                - query: PromQL query string (required if template not specified)
                - template: Template name from PROMQL_TEMPLATES (alternative to query)
                - template_params: Parameters for template substitution (dict)
                - step: Query resolution step (default: adaptive based on time window)
                - timeout: Query timeout in seconds (default: 30)

        Returns:
            FetchResult with metrics, summary, and metadata

        Raises:
            ConnectionError: If HTTP request fails
            QueryError: If PromQL query is invalid or execution fails
            ValueError: If neither query nor template is specified
        """
        # Get query or build from template
        query = kwargs.get("query")
        template = kwargs.get("template")

        if not query and not template:
            raise ValueError("Either 'query' or 'template' must be specified")

        if template:
            if template not in PROMQL_TEMPLATES:
                raise QueryError(f"Unknown template: {template}. Available: {list(PROMQL_TEMPLATES.keys())}")
            query = self._build_query_from_template(template, kwargs.get("template_params", {}))

        # Determine time window
        if time_window is None:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=2)
            time_window = (start_time, end_time)
        else:
            start_time, end_time = time_window

        # Determine step (resolution)
        step = kwargs.get("step")
        if step is None:
            step = self._calculate_adaptive_step(start_time, end_time)

        # Execute query
        timeout = kwargs.get("timeout", 30)
        metrics_data = self._execute_range_query(query, start_time, end_time, step, timeout)

        # Generate summary
        summary = self._generate_summary(metrics_data, query)

        return FetchResult(
            source="prometheus",
            data=metrics_data,
            summary=summary,
            count=sum(len(metric.get("values", [])) for metric in metrics_data),
            time_range=(start_time, end_time),
            metadata={
                "endpoint": self.config["endpoint"],
                "query": query,
                "step": step,
                "template": template,
            }
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers including authentication.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {"Accept": "application/json"}

        credentials = self.config.get("credentials", {})
        cred_type = credentials.get("type", "none")

        if cred_type == "env":
            # Load from environment variables
            username_env = credentials.get("username_env", "PROMETHEUS_USERNAME")
            password_env = credentials.get("password_env", "PROMETHEUS_PASSWORD")

            username = os.getenv(username_env)
            password = os.getenv(password_env)

            if username and password:
                import base64
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {auth_string}"

        elif cred_type == "basic":
            # Use credentials from config
            username = credentials.get("username")
            password = credentials.get("password")

            if username and password:
                import base64
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {auth_string}"

        elif cred_type == "bearer":
            # Use bearer token
            token = credentials.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    def _build_query_from_template(
        self,
        template_name: str,
        params: Dict[str, str]
    ) -> str:
        """Build PromQL query from template with parameter substitution.

        Args:
            template_name: Name of template from PROMQL_TEMPLATES
            params: Parameters for template substitution

        Returns:
            Formatted PromQL query string

        Raises:
            QueryError: If required template parameters are missing
        """
        template = PROMQL_TEMPLATES[template_name]

        try:
            return template.format(**params)
        except KeyError as e:
            missing_param = str(e).strip("'")
            raise QueryError(
                f"Missing required parameter '{missing_param}' for template '{template_name}'"
            )

    def _calculate_adaptive_step(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Calculate adaptive query resolution based on time window.

        Strategy:
        - < 1 hour: 15s resolution
        - < 6 hours: 1m resolution
        - < 24 hours: 5m resolution
        - < 7 days: 30m resolution
        - >= 7 days: 1h resolution

        Args:
            start_time: Query start time
            end_time: Query end time

        Returns:
            Step string in Prometheus format (e.g., "1m", "5m", "1h")
        """
        duration = end_time - start_time

        if duration < timedelta(hours=1):
            return "15s"
        elif duration < timedelta(hours=6):
            return "1m"
        elif duration < timedelta(hours=24):
            return "5m"
        elif duration < timedelta(days=7):
            return "30m"
        else:
            return "1h"

    def _execute_range_query(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
        timeout: int
    ) -> List[Dict[str, Any]]:
        """Execute Prometheus range query.

        Args:
            query: PromQL query string
            start_time: Query start time
            end_time: Query end time
            step: Query resolution step
            timeout: Request timeout in seconds

        Returns:
            List of metric time series with labels and values

        Raises:
            ConnectionError: If HTTP request fails
            QueryError: If PromQL query is invalid or execution fails
        """
        url = f"{self.config['endpoint']}/api/v1/query_range"
        headers = self._get_headers()

        params = {
            "query": query,
            "start": start_time.timestamp(),
            "end": end_time.timestamp(),
            "step": step,
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout
            )

            if response.status_code == 401:
                raise AuthenticationError("Authentication failed: Invalid credentials")

            if response.status_code == 400:
                # Bad request - likely invalid query
                error_data = response.json()
                error_msg = error_data.get("error", "Invalid query")
                raise QueryError(f"Invalid PromQL query: {error_msg}")

            response.raise_for_status()

            data = response.json()

            if data.get("status") != "success":
                error_msg = data.get("error", "Unknown error")
                raise QueryError(f"Prometheus query failed: {error_msg}")

            result = data.get("data", {}).get("result", [])
            return result

        except requests.exceptions.Timeout:
            raise ConnectionError(f"Prometheus query timed out after {timeout}s")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to query Prometheus: {str(e)}")

    def _generate_summary(
        self,
        metrics_data: List[Dict[str, Any]],
        query: str
    ) -> str:
        """Generate human-readable summary of metric data.

        Args:
            metrics_data: List of metric time series
            query: The PromQL query that was executed

        Returns:
            Human-readable summary string
        """
        if not metrics_data:
            return f"No data returned for query: {query}"

        num_series = len(metrics_data)
        total_points = sum(len(metric.get("values", [])) for metric in metrics_data)

        # Extract metric names from series
        metric_names = set()
        for series in metrics_data:
            metric = series.get("metric", {})
            # Try to get __name__ label, otherwise use first non-internal label
            name = metric.get("__name__", "")
            if not name:
                for key, value in metric.items():
                    if not key.startswith("__"):
                        name = value
                        break
            if name:
                metric_names.add(name)

        # Try to detect spikes or anomalies
        anomaly_info = self._detect_anomalies(metrics_data)

        summary_parts = [
            f"{num_series} time series, {total_points} data points"
        ]

        if metric_names:
            summary_parts.append(f"metrics: {', '.join(sorted(metric_names))}")

        if anomaly_info:
            summary_parts.append(anomaly_info)

        return "; ".join(summary_parts)

    def _detect_anomalies(
        self,
        metrics_data: List[Dict[str, Any]]
    ) -> str:
        """Detect anomalies in metric data (spikes, drops).

        Args:
            metrics_data: List of metric time series

        Returns:
            String describing anomalies, or empty string if none detected
        """
        anomalies = []

        for series in metrics_data:
            values = series.get("values", [])
            if len(values) < 2:
                continue

            # Extract numeric values (second element of each [timestamp, value] pair)
            try:
                numeric_values = [float(v[1]) for v in values if v[1] != "NaN"]
            except (ValueError, IndexError):
                continue

            if not numeric_values:
                continue

            # Calculate basic statistics
            avg_value = sum(numeric_values) / len(numeric_values)
            min_value = min(numeric_values)
            max_value = max(numeric_values)

            # Detect spike (value > 3x average)
            if max_value > avg_value * 3 and avg_value > 0:
                anomalies.append(f"spike detected: {max_value:.2f} (avg: {avg_value:.2f})")

            # Detect drop (value < 1/3 average)
            if min_value < avg_value / 3 and avg_value > 0:
                anomalies.append(f"drop detected: {min_value:.2f} (avg: {avg_value:.2f})")

        if anomalies:
            return "anomalies: " + ", ".join(anomalies[:3])  # Limit to 3 anomalies

        return ""

    def __repr__(self) -> str:
        """String representation of PrometheusFetcher."""
        endpoint = self.config.get("endpoint", "unknown")
        return f"PrometheusFetcher(endpoint='{endpoint}')"
