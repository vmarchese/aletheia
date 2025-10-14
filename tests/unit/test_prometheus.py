"""Unit tests for Prometheus fetcher."""

import base64
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from aletheia.fetchers.prometheus import PrometheusFetcher, PROMQL_TEMPLATES
from aletheia.fetchers.base import (
    FetchResult,
    ConnectionError,
    QueryError,
    AuthenticationError
)


# Test fixtures


@pytest.fixture
def valid_config():
    """Valid Prometheus configuration."""
    return {
        "endpoint": "https://prometheus.example.com"
    }


@pytest.fixture
def config_with_env_auth():
    """Configuration with environment-based authentication."""
    return {
        "endpoint": "https://prometheus.example.com",
        "credentials": {
            "type": "env",
            "username_env": "PROMETHEUS_USERNAME",
            "password_env": "PROMETHEUS_PASSWORD"
        }
    }


@pytest.fixture
def config_with_basic_auth():
    """Configuration with basic authentication."""
    return {
        "endpoint": "https://prometheus.example.com",
        "credentials": {
            "type": "basic",
            "username": "admin",
            "password": "secret"
        }
    }


@pytest.fixture
def config_with_bearer_auth():
    """Configuration with bearer token authentication."""
    return {
        "endpoint": "https://prometheus.example.com",
        "credentials": {
            "type": "bearer",
            "token": "abc123token"
        }
    }


@pytest.fixture
def mock_prometheus_response():
    """Mock successful Prometheus API response."""
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "__name__": "http_requests_total",
                        "service": "payments-svc",
                        "status": "500"
                    },
                    "values": [
                        [1697200000, "0.5"],
                        [1697200060, "1.2"],
                        [1697200120, "3.8"],
                        [1697200180, "0.9"]
                    ]
                },
                {
                    "metric": {
                        "__name__": "http_requests_total",
                        "service": "payments-svc",
                        "status": "503"
                    },
                    "values": [
                        [1697200000, "0.1"],
                        [1697200060, "0.2"],
                        [1697200120, "0.3"],
                        [1697200180, "0.1"]
                    ]
                }
            ]
        }
    }


# Initialization and Configuration Tests


def test_initialization_with_valid_config(valid_config):
    """Test initialization with valid configuration."""
    fetcher = PrometheusFetcher(valid_config)
    assert fetcher.config == valid_config


def test_validate_config_missing_endpoint():
    """Test validation fails with missing endpoint."""
    config = {}
    with pytest.raises(ValueError, match="endpoint is required"):
        PrometheusFetcher(config)


def test_validate_config_invalid_endpoint():
    """Test validation fails with invalid endpoint format."""
    config = {"endpoint": "prometheus.example.com"}  # Missing protocol
    with pytest.raises(ValueError, match="must start with http"):
        PrometheusFetcher(config)


def test_validate_config_with_http():
    """Test validation passes with http endpoint."""
    config = {"endpoint": "http://localhost:9090"}
    fetcher = PrometheusFetcher(config)
    assert fetcher.config == config


def test_validate_config_with_https():
    """Test validation passes with https endpoint."""
    config = {"endpoint": "https://prometheus.example.com"}
    fetcher = PrometheusFetcher(config)
    assert fetcher.config == config


# Connection Tests


@patch("aletheia.fetchers.prometheus.requests.get")
def test_test_connection_success(mock_get, valid_config):
    """Test successful connection test."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": {}}
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    assert fetcher.test_connection() is True

    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args.kwargs["params"]["query"] == "up"


@patch("aletheia.fetchers.prometheus.requests.get")
def test_test_connection_failure(mock_get, valid_config):
    """Test connection test with request failure."""
    mock_get.side_effect = requests.exceptions.RequestException("Connection refused")

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="Failed to connect"):
        fetcher.test_connection()


@patch("aletheia.fetchers.prometheus.requests.get")
def test_test_connection_timeout(mock_get, valid_config):
    """Test connection test with timeout."""
    mock_get.side_effect = requests.exceptions.Timeout()

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="timed out"):
        fetcher.test_connection()


@patch("aletheia.fetchers.prometheus.requests.get")
def test_test_connection_authentication_failure(mock_get, valid_config):
    """Test connection test with authentication failure."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(AuthenticationError, match="Authentication failed"):
        fetcher.test_connection()


@patch("aletheia.fetchers.prometheus.requests.get")
def test_test_connection_query_failure(mock_get, valid_config):
    """Test connection test with query failure."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "error", "error": "invalid query"}
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="Prometheus query failed"):
        fetcher.test_connection()


# Capabilities Tests


def test_get_capabilities(valid_config):
    """Test capabilities reporting."""
    fetcher = PrometheusFetcher(valid_config)
    capabilities = fetcher.get_capabilities()

    assert capabilities["supports_time_window"] is True
    assert capabilities["supports_streaming"] is False
    assert capabilities["max_sample_size"] == 11000
    assert "metrics" in capabilities["data_types"]
    assert capabilities["query_language"] == "PromQL"
    assert set(capabilities["templates"]) == set(PROMQL_TEMPLATES.keys())


# Fetch Tests


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_custom_query(mock_get, valid_config, mock_prometheus_response):
    """Test fetch with custom PromQL query."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    result = fetcher.fetch(query='rate(http_requests_total[5m])')

    assert isinstance(result, FetchResult)
    assert result.source == "prometheus"
    assert result.count == 8  # 4 + 4 data points
    assert len(result.data) == 2  # 2 time series
    assert "prometheus" in result.source.lower()


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_template(mock_get, valid_config, mock_prometheus_response):
    """Test fetch with query template."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    result = fetcher.fetch(
        template="error_rate",
        template_params={
            "metric_name": "http_requests_total",
            "service": "payments-svc",
            "window": "5m"
        }
    )

    assert isinstance(result, FetchResult)
    assert result.source == "prometheus"
    assert result.metadata["template"] == "error_rate"


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_time_window(mock_get, valid_config, mock_prometheus_response):
    """Test fetch with explicit time window."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    start_time = datetime(2023, 10, 13, 8, 0, 0)
    end_time = datetime(2023, 10, 13, 10, 0, 0)

    result = fetcher.fetch(
        query='up',
        time_window=(start_time, end_time)
    )

    assert result.time_range == (start_time, end_time)

    # Verify request parameters
    call_args = mock_get.call_args
    assert call_args.kwargs["params"]["start"] == start_time.timestamp()
    assert call_args.kwargs["params"]["end"] == end_time.timestamp()


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_without_time_window(mock_get, valid_config, mock_prometheus_response):
    """Test fetch without explicit time window (uses default 2 hours)."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    result = fetcher.fetch(query='up')

    # Should default to last 2 hours
    start_time, end_time = result.time_range
    assert (end_time - start_time) >= timedelta(hours=1, minutes=50)
    assert (end_time - start_time) <= timedelta(hours=2, minutes=10)


def test_fetch_without_query_or_template(valid_config):
    """Test fetch fails without query or template."""
    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ValueError, match="Either 'query' or 'template' must be specified"):
        fetcher.fetch()


def test_fetch_with_unknown_template(valid_config):
    """Test fetch fails with unknown template."""
    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(QueryError, match="Unknown template"):
        fetcher.fetch(template="nonexistent_template")


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_custom_step(mock_get, valid_config, mock_prometheus_response):
    """Test fetch with custom step parameter."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    result = fetcher.fetch(query='up', step="30s")

    assert result.metadata["step"] == "30s"

    # Verify request parameters
    call_args = mock_get.call_args
    assert call_args.kwargs["params"]["step"] == "30s"


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_adaptive_step(mock_get, valid_config, mock_prometheus_response):
    """Test fetch uses adaptive step based on time window."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_prometheus_response
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)

    # Test 30-minute window (should use 15s step)
    start_time = datetime.now() - timedelta(minutes=30)
    end_time = datetime.now()
    result = fetcher.fetch(query='up', time_window=(start_time, end_time))
    assert result.metadata["step"] == "15s"


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_query_failure(mock_get, valid_config):
    """Test fetch with query failure."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "parse error"}
    mock_get.return_value = mock_response

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(QueryError, match="Invalid PromQL query"):
        fetcher.fetch(query='invalid{query')


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_connection_failure(mock_get, valid_config):
    """Test fetch with connection failure."""
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="Failed to query Prometheus"):
        fetcher.fetch(query='up')


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_timeout(mock_get, valid_config):
    """Test fetch with timeout."""
    mock_get.side_effect = requests.exceptions.Timeout()

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="timed out"):
        fetcher.fetch(query='up', timeout=5)


# Template System Tests


def test_build_query_from_template_error_rate(valid_config):
    """Test building error rate query from template."""
    fetcher = PrometheusFetcher(valid_config)
    query = fetcher._build_query_from_template(
        "error_rate",
        {"metric_name": "http_requests_total", "service": "payments-svc", "window": "5m"}
    )
    expected = 'rate(http_requests_total{service="payments-svc",status=~"5.."}[5m])'
    assert query == expected


def test_build_query_from_template_latency_p95(valid_config):
    """Test building P95 latency query from template."""
    fetcher = PrometheusFetcher(valid_config)
    query = fetcher._build_query_from_template(
        "latency_p95",
        {"metric_name": "http_request_duration_seconds", "service": "api-svc", "window": "10m"}
    )
    expected = 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="api-svc"}[10m]))'
    assert query == expected


def test_build_query_from_template_missing_parameter(valid_config):
    """Test template fails with missing parameter."""
    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(QueryError, match="Missing required parameter 'service'"):
        fetcher._build_query_from_template("error_rate", {"metric_name": "http_requests_total"})


def test_all_templates_are_valid(valid_config):
    """Test all predefined templates have valid formats."""
    fetcher = PrometheusFetcher(valid_config)

    template_params = {
        "error_rate": {"metric_name": "test", "service": "svc", "window": "5m"},
        "latency_p95": {"metric_name": "test", "service": "svc", "window": "5m"},
        "latency_p99": {"metric_name": "test", "service": "svc", "window": "5m"},
        "request_rate": {"metric_name": "test", "service": "svc", "window": "5m"},
        "cpu_usage": {"pod_pattern": "pod.*", "window": "5m"},
        "memory_usage": {"pod_pattern": "pod.*"},
    }

    for template_name, params in template_params.items():
        query = fetcher._build_query_from_template(template_name, params)
        assert isinstance(query, str)
        assert len(query) > 0


# Adaptive Step Tests


def test_calculate_adaptive_step_1_hour(valid_config):
    """Test adaptive step for exactly 1-hour window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "1m"  # Exactly 1 hour falls in the 1-6 hour range


def test_calculate_adaptive_step_under_1_hour(valid_config):
    """Test adaptive step for under 1-hour window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(minutes=30)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "15s"


def test_calculate_adaptive_step_3_hours(valid_config):
    """Test adaptive step for 3-hour window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(hours=3)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "1m"


def test_calculate_adaptive_step_12_hours(valid_config):
    """Test adaptive step for 12-hour window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(hours=12)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "5m"


def test_calculate_adaptive_step_3_days(valid_config):
    """Test adaptive step for 3-day window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(days=3)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "30m"


def test_calculate_adaptive_step_10_days(valid_config):
    """Test adaptive step for 10-day window."""
    fetcher = PrometheusFetcher(valid_config)
    start = datetime.now() - timedelta(days=10)
    end = datetime.now()
    step = fetcher._calculate_adaptive_step(start, end)
    assert step == "1h"


# Authentication Tests


@patch.dict("os.environ", {"PROMETHEUS_USERNAME": "user", "PROMETHEUS_PASSWORD": "pass"})
def test_get_headers_with_env_auth(config_with_env_auth):
    """Test headers with environment-based authentication."""
    fetcher = PrometheusFetcher(config_with_env_auth)
    headers = fetcher._get_headers()

    assert "Authorization" in headers
    auth_value = headers["Authorization"]
    assert auth_value.startswith("Basic ")

    # Decode and verify
    encoded = auth_value.split(" ")[1]
    decoded = base64.b64decode(encoded).decode()
    assert decoded == "user:pass"


def test_get_headers_with_basic_auth(config_with_basic_auth):
    """Test headers with basic authentication."""
    fetcher = PrometheusFetcher(config_with_basic_auth)
    headers = fetcher._get_headers()

    assert "Authorization" in headers
    auth_value = headers["Authorization"]
    assert auth_value.startswith("Basic ")

    # Decode and verify
    encoded = auth_value.split(" ")[1]
    decoded = base64.b64decode(encoded).decode()
    assert decoded == "admin:secret"


def test_get_headers_with_bearer_auth(config_with_bearer_auth):
    """Test headers with bearer token authentication."""
    fetcher = PrometheusFetcher(config_with_bearer_auth)
    headers = fetcher._get_headers()

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer abc123token"


def test_get_headers_no_auth(valid_config):
    """Test headers without authentication."""
    fetcher = PrometheusFetcher(valid_config)
    headers = fetcher._get_headers()

    assert "Authorization" not in headers
    assert "Accept" in headers
    assert headers["Accept"] == "application/json"


# Summary Generation Tests


def test_generate_summary_with_data(valid_config):
    """Test summary generation with metric data."""
    fetcher = PrometheusFetcher(valid_config)
    metrics_data = [
        {
            "metric": {"__name__": "http_requests_total", "service": "api"},
            "values": [[1697200000, "1.0"], [1697200060, "2.0"]]
        },
        {
            "metric": {"__name__": "http_errors_total", "service": "api"},
            "values": [[1697200000, "0.1"], [1697200060, "0.2"], [1697200120, "0.3"]]
        }
    ]

    summary = fetcher._generate_summary(metrics_data, 'rate(http_requests_total[5m])')

    assert "2 time series" in summary
    assert "5 data points" in summary
    assert "http_requests_total" in summary or "http_errors_total" in summary


def test_generate_summary_empty_data(valid_config):
    """Test summary generation with no data."""
    fetcher = PrometheusFetcher(valid_config)
    summary = fetcher._generate_summary([], 'rate(http_requests_total[5m])')

    assert "No data" in summary
    assert "rate(http_requests_total[5m])" in summary


def test_generate_summary_with_spike(valid_config):
    """Test summary detects spikes in data."""
    fetcher = PrometheusFetcher(valid_config)
    metrics_data = [
        {
            "metric": {"__name__": "http_requests_total"},
            "values": [
                [1697200000, "1.0"],
                [1697200060, "1.2"],
                [1697200120, "15.0"],  # Spike: > 3x average
                [1697200180, "1.1"]
            ]
        }
    ]

    summary = fetcher._generate_summary(metrics_data, 'up')
    assert "spike detected" in summary


def test_generate_summary_with_drop(valid_config):
    """Test summary detects drops in data."""
    fetcher = PrometheusFetcher(valid_config)
    metrics_data = [
        {
            "metric": {"__name__": "http_requests_total"},
            "values": [
                [1697200000, "10.0"],
                [1697200060, "9.5"],
                [1697200120, "0.5"],  # Drop: < 1/3 average
                [1697200180, "10.2"]
            ]
        }
    ]

    summary = fetcher._generate_summary(metrics_data, 'up')
    assert "drop detected" in summary


def test_detect_anomalies_no_anomalies(valid_config):
    """Test anomaly detection with stable data."""
    fetcher = PrometheusFetcher(valid_config)
    metrics_data = [
        {
            "metric": {"__name__": "http_requests_total"},
            "values": [[1697200000, "1.0"], [1697200060, "1.1"], [1697200120, "0.9"]]
        }
    ]

    anomaly_info = fetcher._detect_anomalies(metrics_data)
    assert anomaly_info == ""


def test_detect_anomalies_with_nan_values(valid_config):
    """Test anomaly detection handles NaN values."""
    fetcher = PrometheusFetcher(valid_config)
    metrics_data = [
        {
            "metric": {"__name__": "http_requests_total"},
            "values": [[1697200000, "NaN"], [1697200060, "1.0"], [1697200120, "NaN"]]
        }
    ]

    # Should not raise exception
    anomaly_info = fetcher._detect_anomalies(metrics_data)
    assert isinstance(anomaly_info, str)


# Representation Tests


def test_repr(valid_config):
    """Test string representation."""
    fetcher = PrometheusFetcher(valid_config)
    repr_str = repr(fetcher)
    assert "PrometheusFetcher" in repr_str
    assert "prometheus.example.com" in repr_str


# Retry Logic Tests


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_with_retry_success_on_second_attempt(mock_get, valid_config, mock_prometheus_response):
    """Test fetch retries and succeeds on second attempt."""
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = mock_prometheus_response

    # Fail first, succeed second
    mock_get.side_effect = [
        requests.exceptions.RequestException("Temporary failure"),
        mock_response_success
    ]

    fetcher = PrometheusFetcher(valid_config)
    result = fetcher.fetch(query='up')

    assert isinstance(result, FetchResult)
    assert mock_get.call_count == 2


@patch("aletheia.fetchers.prometheus.requests.get")
def test_fetch_exhausts_retries(mock_get, valid_config):
    """Test fetch exhausts all retries and fails."""
    mock_get.side_effect = requests.exceptions.RequestException("Persistent failure")

    fetcher = PrometheusFetcher(valid_config)
    with pytest.raises(ConnectionError, match="Failed to query Prometheus"):
        fetcher.fetch(query='up')

    # Should retry 3 times (initial + 3 retries = 4 total calls)
    assert mock_get.call_count == 4
