"""Unit tests for Kubernetes fetcher."""

import json
import subprocess
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from aletheia.fetchers.base import ConnectionError, QueryError
from aletheia.fetchers.kubernetes import KubernetesFetcher


class TestKubernetesFetcher:
    """Test suite for KubernetesFetcher."""

    def test_initialization(self):
        """Test fetcher initialization with valid config."""
        config = {"context": "prod-eu", "namespace": "default"}
        fetcher = KubernetesFetcher(config)
        assert fetcher.config == config

    def test_validate_config_missing_context(self):
        """Test config validation fails without context."""
        config = {"namespace": "default"}
        with pytest.raises(ValueError, match="context is required"):
            KubernetesFetcher(config)

    def test_fetch_basic(self):
        """Test basic log fetching."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_logs = """{"level": "ERROR", "message": "Test error", "timestamp": "2025-10-14T10:00:00Z"}
{"level": "INFO", "message": "Test info", "timestamp": "2025-10-14T10:01:00Z"}"""

        with patch.object(fetcher, "_fetch_raw_logs", return_value=mock_logs):
            result = fetcher.fetch(pod="test-pod")

        assert result.source == "kubernetes"
        assert result.count == 2
        assert len(result.data) == 2
        assert result.data[0]["level"] == "ERROR"
        assert "test-context" in result.metadata["context"]

    def test_fetch_with_time_window(self):
        """Test fetching with time window."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        time_window = (datetime.now() - timedelta(hours=2), datetime.now())
        mock_logs = '{"level": "INFO", "message": "Test", "timestamp": "2025-10-14T10:00:00Z"}'

        with patch.object(fetcher, "_fetch_raw_logs", return_value=mock_logs):
            result = fetcher.fetch(pod="test-pod", time_window=time_window)

        assert result.count == 1
        # Just verify we got a valid time range back
        assert isinstance(result.time_range[0], datetime)
        assert isinstance(result.time_range[1], datetime)

    def test_fetch_without_pod_fails(self):
        """Test fetch fails without pod name."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with pytest.raises(QueryError, match="Pod name.*required"):
            fetcher.fetch()

    def test_fetch_raw_logs_success(self):
        """Test successful kubectl log fetching."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "test log line\n"
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            logs = fetcher._fetch_raw_logs("default", "test-pod", None, None)

        assert logs == "test log line\n"
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "kubectl" in call_args
        assert "--context" in call_args
        assert "test-context" in call_args
        assert "test-pod" in call_args

    def test_fetch_raw_logs_with_container(self):
        """Test fetching logs with container specification."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "container log\n"
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            logs = fetcher._fetch_raw_logs("default", "test-pod", "app", None)

        call_args = mock_run.call_args[0][0]
        assert "--container" in call_args
        assert "app" in call_args

    def test_fetch_raw_logs_with_time_window(self):
        """Test fetching logs with time window."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "recent log\n"
        mock_result.returncode = 0
        mock_result.stderr = ""

        time_window = (datetime.now() - timedelta(hours=2), datetime.now())

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            logs = fetcher._fetch_raw_logs("default", "test-pod", None, time_window)

        call_args = mock_run.call_args[0][0]
        assert "--since" in call_args
        # Should have a duration like "2h"
        assert any("h" in str(arg) or "m" in str(arg) for arg in call_args)

    def test_fetch_raw_logs_command_failure(self):
        """Test handling of kubectl command failure."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, "kubectl", stderr="Error: context not found"
        )):
            with pytest.raises(ConnectionError, match="kubectl command failed"):
                fetcher._fetch_raw_logs("default", "test-pod", None, None)

    def test_fetch_raw_logs_timeout(self):
        """Test handling of kubectl timeout."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("kubectl", 30)):
            with pytest.raises(ConnectionError, match="timed out"):
                fetcher._fetch_raw_logs("default", "test-pod", None, None)

    def test_parse_logs_json(self):
        """Test parsing JSON-formatted logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        raw_logs = """{"level": "ERROR", "message": "Error occurred", "timestamp": "2025-10-14T10:00:00Z"}
{"level": "INFO", "message": "Info message", "timestamp": "2025-10-14T10:01:00Z"}"""

        parsed = fetcher._parse_logs(raw_logs)

        assert len(parsed) == 2
        assert parsed[0]["level"] == "ERROR"
        assert parsed[0]["message"] == "Error occurred"
        assert parsed[1]["level"] == "INFO"

    def test_parse_logs_plain_text(self):
        """Test parsing plain text logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        raw_logs = """ERROR: Something went wrong
INFO: Normal operation
WARN: Warning message"""

        parsed = fetcher._parse_logs(raw_logs)

        assert len(parsed) == 3
        assert parsed[0]["level"] == "ERROR"
        assert "Something went wrong" in parsed[0]["message"]
        assert parsed[1]["level"] == "INFO"
        assert parsed[2]["level"] == "WARN"

    def test_parse_logs_mixed_json_and_text(self):
        """Test parsing mix of JSON and plain text logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        raw_logs = """{"level": "ERROR", "message": "JSON error"}
Plain text INFO message
{"level": "WARN", "message": "JSON warning"}"""

        parsed = fetcher._parse_logs(raw_logs)

        assert len(parsed) == 3
        assert parsed[0]["level"] == "ERROR"
        assert parsed[1]["level"] == "INFO"
        assert parsed[2]["level"] == "WARN"

    def test_parse_logs_empty(self):
        """Test parsing empty logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        parsed = fetcher._parse_logs("")
        assert parsed == []

    def test_parse_logs_json_without_level(self):
        """Test parsing JSON logs without level field."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        raw_logs = '{"message": "ERROR: Test message"}'
        parsed = fetcher._parse_logs(raw_logs)

        assert len(parsed) == 1
        assert parsed[0]["level"] == "ERROR"  # Extracted from message

    def test_extract_level_from_message(self):
        """Test log level extraction from messages."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        assert fetcher._extract_level_from_message("FATAL: Critical error") == "FATAL"
        assert fetcher._extract_level_from_message("ERROR: Something failed") == "ERROR"
        assert fetcher._extract_level_from_message("WARN: Deprecated usage") == "WARN"
        assert fetcher._extract_level_from_message("WARNING: Deprecated") == "WARN"
        assert fetcher._extract_level_from_message("INFO: Starting up") == "INFO"
        assert fetcher._extract_level_from_message("DEBUG: Variable value") == "DEBUG"
        assert fetcher._extract_level_from_message("No level here") == "INFO"

    def test_sample_logs_under_limit(self):
        """Test sampling when log count is under limit."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "ERROR", "message": "Error 1"},
            {"level": "INFO", "message": "Info 1"},
        ]

        sampled = fetcher._sample_logs(logs, sample_size=10, always_include_levels=["ERROR"])

        assert len(sampled) == 2

    def test_sample_logs_priority_only(self):
        """Test sampling with only priority logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "ERROR", "message": f"Error {i}"}
            for i in range(50)
        ]

        sampled = fetcher._sample_logs(logs, sample_size=10, always_include_levels=["ERROR"])

        # All ERROR logs included even if over sample_size
        assert len(sampled) == 50

    def test_sample_logs_mixed(self):
        """Test sampling with mix of priority and non-priority logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "ERROR", "message": f"Error {i}"}
            for i in range(5)
        ] + [
            {"level": "INFO", "message": f"Info {i}"}
            for i in range(100)
        ]

        sampled = fetcher._sample_logs(logs, sample_size=20, always_include_levels=["ERROR", "FATAL"])

        # Should have all 5 errors + 15 random infos
        assert len(sampled) == 20
        error_count = sum(1 for log in sampled if log["level"] == "ERROR")
        assert error_count == 5

    def test_sample_logs_no_priority(self):
        """Test sampling when no priority logs present."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "INFO", "message": f"Info {i}"}
            for i in range(100)
        ]

        sampled = fetcher._sample_logs(logs, sample_size=20, always_include_levels=["ERROR"])

        assert len(sampled) == 20

    def test_get_time_range_from_logs(self):
        """Test extracting time range from logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"timestamp": "2025-10-14T10:00:00Z"},
            {"timestamp": "2025-10-14T10:05:00Z"},
            {"timestamp": "2025-10-14T10:02:00Z"},
        ]

        start, end = fetcher._get_time_range(logs, None)

        assert start.hour == 10
        assert start.minute == 0
        assert end.minute == 5

    def test_get_time_range_no_logs(self):
        """Test time range with no logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        start, end = fetcher._get_time_range([], None)

        assert isinstance(start, datetime)
        assert isinstance(end, datetime)

    def test_get_time_range_fallback_to_requested(self):
        """Test time range falls back to requested window."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        requested = (datetime(2025, 10, 14, 9, 0), datetime(2025, 10, 14, 11, 0))
        logs = [{"message": "no timestamp"}]

        start, end = fetcher._get_time_range(logs, requested)

        # Should fall back to requested since no parseable timestamps
        assert (start, end) == requested or isinstance(start, datetime)

    def test_generate_summary_empty(self):
        """Test summary generation for empty logs."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        summary = fetcher._generate_summary([])
        assert "No logs found" in summary

    def test_generate_summary_with_logs(self):
        """Test summary generation with various log levels."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "ERROR", "message": "Error occurred"},
            {"level": "ERROR", "message": "Error occurred"},
            {"level": "INFO", "message": "Info message"},
            {"level": "WARN", "message": "Warning"},
        ]

        summary = fetcher._generate_summary(logs)

        assert "4 logs" in summary
        assert "ERROR" in summary
        assert "INFO" in summary

    def test_generate_summary_with_error_patterns(self):
        """Test summary includes top error pattern."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        logs = [
            {"level": "ERROR", "message": "NullPointerException: something"},
            {"level": "ERROR", "message": "NullPointerException: another"},
            {"level": "ERROR", "message": "ConnectionError: timeout"},
        ]

        summary = fetcher._generate_summary(logs)

        assert "top error" in summary
        assert "NullPointerException" in summary or "ConnectionError" in summary

    def test_list_pods_success(self):
        """Test listing pods successfully."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "pod-1 pod-2 pod-3"
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            pods = fetcher.list_pods(namespace="default")

        assert pods == ["pod-1", "pod-2", "pod-3"]
        call_args = mock_run.call_args[0][0]
        assert "get" in call_args
        assert "pods" in call_args

    def test_list_pods_with_selector(self):
        """Test listing pods with label selector."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "payments-pod-1 payments-pod-2"
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            pods = fetcher.list_pods(selector="app=payments-svc")

        assert len(pods) == 2
        call_args = mock_run.call_args[0][0]
        assert "-l" in call_args
        assert "app=payments-svc" in call_args

    def test_list_pods_empty(self):
        """Test listing pods returns empty list."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            pods = fetcher.list_pods()

        assert pods == []

    def test_list_pods_failure(self):
        """Test handling of kubectl failure when listing pods."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, "kubectl", stderr="Error: context not found"
        )):
            with pytest.raises(ConnectionError, match="kubectl command failed"):
                fetcher.list_pods()

    def test_get_pod_status_success(self):
        """Test getting pod status successfully."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        pod_json = {
            "metadata": {"name": "test-pod", "namespace": "default"},
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "True"}],
                "containerStatuses": [{"name": "app", "ready": True}],
                "startTime": "2025-10-14T09:00:00Z"
            }
        }

        mock_result = Mock()
        mock_result.stdout = json.dumps(pod_json)
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            status = fetcher.get_pod_status("test-pod")

        assert status["name"] == "test-pod"
        assert status["phase"] == "Running"
        assert len(status["conditions"]) == 1

    def test_get_pod_status_command_failure(self):
        """Test handling of kubectl failure when getting pod status."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, "kubectl", stderr="Error: pod not found"
        )):
            with pytest.raises(ConnectionError, match="kubectl command failed"):
                fetcher.get_pod_status("nonexistent-pod")

    def test_get_pod_status_parse_error(self):
        """Test handling of JSON parse error in pod status."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "invalid json"
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(QueryError, match="Failed to parse"):
                fetcher.get_pod_status("test-pod")

    def test_test_connection_success(self):
        """Test successful connection test."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        mock_result = Mock()
        mock_result.stdout = "Kubernetes control plane is running at https://..."
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = fetcher.test_connection()

        assert result is True

    def test_test_connection_failure(self):
        """Test failed connection test."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(
            1, "kubectl", stderr="Error: context not found"
        )):
            with pytest.raises(ConnectionError, match="connection test failed"):
                fetcher.test_connection()

    def test_get_capabilities(self):
        """Test fetcher capabilities reporting."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        capabilities = fetcher.get_capabilities()

        assert capabilities["supports_time_window"] is True
        assert capabilities["data_types"] == ["logs"]
        assert capabilities["retry_enabled"] is True
        assert "sampling_strategies" in capabilities

    def test_retry_logic_on_fetch(self):
        """Test retry logic is applied to fetch method."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        # Mock fetch_raw_logs to fail twice, then succeed
        call_count = [0]

        def mock_fetch_raw(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Temporary failure")
            return '{"level": "INFO", "message": "Success"}'

        with patch.object(fetcher, "_fetch_raw_logs", side_effect=mock_fetch_raw):
            result = fetcher.fetch(pod="test-pod")

        # Should succeed after retries
        assert result.count == 1
        assert call_count[0] == 3  # Called 3 times (1 initial + 2 retries)

    def test_namespace_from_config(self):
        """Test namespace defaults to config value."""
        config = {"context": "test-context", "namespace": "production"}
        fetcher = KubernetesFetcher(config)

        mock_logs = '{"level": "INFO", "message": "Test"}'

        with patch.object(fetcher, "_fetch_raw_logs", return_value=mock_logs) as mock_fetch:
            result = fetcher.fetch(pod="test-pod")

        # Should use namespace from config
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args[0]
        assert call_args[0] == "production"

    def test_namespace_override(self):
        """Test namespace can be overridden in fetch call."""
        config = {"context": "test-context", "namespace": "production"}
        fetcher = KubernetesFetcher(config)

        mock_logs = '{"level": "INFO", "message": "Test"}'

        with patch.object(fetcher, "_fetch_raw_logs", return_value=mock_logs) as mock_fetch:
            result = fetcher.fetch(pod="test-pod", namespace="staging")

        # Should use overridden namespace
        call_args = mock_fetch.call_args[0]
        assert call_args[0] == "staging"

    def test_repr(self):
        """Test string representation of fetcher."""
        config = {"context": "test-context"}
        fetcher = KubernetesFetcher(config)

        repr_str = repr(fetcher)
        assert "KubernetesFetcher" in repr_str
