"""Unit tests for Prometheus Semantic Kernel plugin.

Tests the PrometheusPlugin class that exposes Prometheus operations
as kernel functions for SK agents.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.fetchers.base import FetchResult, ConnectionError, QueryError, AuthenticationError
from aletheia.fetchers.prometheus import PROMQL_TEMPLATES


class TestPrometheusPluginInitialization:
    """Tests for PrometheusPlugin initialization."""
    
    def test_init_with_valid_config(self):
        """Test plugin initialization with valid configuration."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        assert plugin.endpoint == "http://prometheus:9090"
        assert plugin.config == config
        assert plugin.fetcher is not None
    
    def test_init_without_endpoint_raises_error(self):
        """Test that initialization without endpoint raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="'endpoint' is required"):
            PrometheusPlugin(config)
    
    def test_init_with_additional_config(self):
        """Test initialization with additional configuration options."""
        config = {
            "endpoint": "https://prometheus.example.com",
            "credentials": {
                "type": "bearer",
                "token": "secret-token"
            },
            "timeout": 60
        }
        plugin = PrometheusPlugin(config)
        
        assert plugin.endpoint == "https://prometheus.example.com"
        assert plugin.config["credentials"]["type"] == "bearer"


class TestFetchPrometheusMetrics:
    """Tests for fetch_metrics kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_basic(self, mock_fetcher_class):
        """Test basic metric fetching without time window."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[{"metric": {"__name__": "http_requests"}, "values": [[1234567890, "100"]]}],
            summary="1 time series, 1 data points",
            count=1,
            time_range=(datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 12, 0)),
            metadata={"query": "http_requests", "step": "1m"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.fetch_metrics(query="http_requests")
        
        # Verify
        result = json.loads(result_json)
        assert result["count"] == 1
        assert result["summary"] == "1 time series, 1 data points"
        assert len(result["data"]) == 1
        
        # Verify fetcher was called correctly
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["query"] == "http_requests"
        assert call_kwargs["timeout"] == 30
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_with_time_window(self, mock_fetcher_class):
        """Test metric fetching with time window parameters."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[],
            summary="0 time series",
            count=0,
            time_range=(datetime(2025, 10, 15, 10, 0), datetime(2025, 10, 15, 12, 0)),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with time window
        result_json = plugin.fetch_metrics(
            query="up",
            start_time="2025-10-15T10:00:00",
            end_time="2025-10-15T12:00:00"
        )
        
        # Verify time window was passed
        mock_fetcher.fetch.assert_called_once()
        call_args = mock_fetcher.fetch.call_args
        time_window = call_args[1]["time_window"]
        
        assert time_window is not None
        start_time, end_time = time_window
        assert start_time == datetime(2025, 10, 15, 10, 0)
        assert end_time == datetime(2025, 10, 15, 12, 0)
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_with_step(self, mock_fetcher_class):
        """Test metric fetching with custom step parameter."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[],
            summary="0 time series",
            count=0,
            time_range=(datetime.now(), datetime.now()),
            metadata={"step": "5m"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with step
        result_json = plugin.fetch_metrics(
            query="cpu_usage",
            step="5m",
            timeout=60
        )
        
        # Verify parameters
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["step"] == "5m"
        assert call_kwargs["timeout"] == 60
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_returns_valid_json(self, mock_fetcher_class):
        """Test that fetch_metrics returns valid JSON string."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[{"metric": {}, "values": []}],
            summary="test summary",
            count=1,
            time_range=(datetime(2025, 1, 1), datetime(2025, 1, 2)),
            metadata={"test": "data"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.fetch_metrics(query="test_metric")
        
        # Verify JSON is valid
        result = json.loads(result_json)
        assert "data" in result
        assert "summary" in result
        assert "count" in result
        assert "time_range" in result
        assert "metadata" in result
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_handles_fetcher_error(self, mock_fetcher_class):
        """Test that fetch_metrics propagates errors from fetcher."""
        # Setup mock to raise error
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = QueryError("Invalid PromQL query")
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function should raise error
        with pytest.raises(QueryError, match="Invalid PromQL query"):
            plugin.fetch_metrics(query="invalid[")


class TestExecutePromQLQuery:
    """Tests for execute_query kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_execute_query_basic(self, mock_fetcher_class):
        """Test basic query execution."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[{"metric": {"job": "api"}, "values": [[1234567890, "42"]]}],
            summary="1 time series",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.execute_query(query="rate(http_requests[5m])")
        
        # Verify
        result = json.loads(result_json)
        assert result["count"] == 1
        assert "data" in result
        assert "summary" in result
        
        # Verify time window is approximately 2 hours
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        time_window = call_kwargs["time_window"]
        start_time, end_time = time_window
        duration = (end_time - start_time).total_seconds()
        assert 119 * 60 <= duration <= 121 * 60  # Allow 1 minute tolerance
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_execute_query_with_custom_time_window(self, mock_fetcher_class):
        """Test query execution with custom since_hours."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="prometheus",
            data=[],
            summary="0 time series",
            count=0,
            time_range=(datetime.now() - timedelta(hours=6), datetime.now()),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with since_hours=6
        result_json = plugin.execute_query(
            query="up",
            since_hours=6
        )
        
        # Verify time window
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        time_window = call_kwargs["time_window"]
        start_time, end_time = time_window
        duration = (end_time - start_time).total_seconds()
        assert 5.9 * 3600 <= duration <= 6.1 * 3600


class TestBuildPromQLFromTemplate:
    """Tests for build_query_from_template kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_build_query_without_execution(self, mock_fetcher_class):
        """Test building query from template without execution."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Mock the template building
        expected_query = 'rate(http_requests{service="payments-svc",status=~"5.."}[5m])'
        mock_fetcher._build_query_from_template.return_value = expected_query
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function without execution
        params_json = json.dumps({
            "metric_name": "http_requests",
            "service": "payments-svc",
            "window": "5m"
        })
        
        result = plugin.build_query_from_template(
            template="error_rate",
            params=params_json,
            execute=False
        )
        
        # Verify
        assert result == expected_query
        mock_fetcher._build_query_from_template.assert_called_once_with(
            "error_rate",
            {"metric_name": "http_requests", "service": "payments-svc", "window": "5m"}
        )
        # Should not fetch
        mock_fetcher.fetch.assert_not_called()
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_build_query_with_execution(self, mock_fetcher_class):
        """Test building query from template with execution."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        expected_query = 'histogram_quantile(0.95, rate(http_latency_bucket{service="api"}[5m]))'
        mock_fetcher._build_query_from_template.return_value = expected_query
        
        mock_result = FetchResult(
            source="prometheus",
            data=[{"metric": {}, "values": [[1234567890, "0.123"]]}],
            summary="1 time series",
            count=1,
            time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with execution
        params_json = json.dumps({
            "metric_name": "http_latency",
            "service": "api",
            "window": "5m"
        })
        
        result_json = plugin.build_query_from_template(
            template="latency_p95",
            params=params_json,
            execute=True,
            since_hours=2
        )
        
        # Verify
        result = json.loads(result_json)
        assert "query" in result
        assert result["query"] == expected_query
        assert "data" in result
        assert "summary" in result
        
        # Should have called fetch
        mock_fetcher.fetch.assert_called_once()
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_build_query_invalid_json_params(self, mock_fetcher_class):
        """Test building query with invalid JSON parameters."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with invalid JSON
        result_json = plugin.build_query_from_template(
            template="error_rate",
            params="invalid json{",
            execute=False
        )
        
        # Verify error is returned as JSON
        result = json.loads(result_json)
        assert "error" in result
        assert "Invalid JSON" in result["error"]
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_build_query_missing_template_params(self, mock_fetcher_class):
        """Test building query with missing required parameters."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Mock error from template building
        from aletheia.fetchers.base import QueryError
        mock_fetcher._build_query_from_template.side_effect = QueryError(
            "Missing required parameter 'service'"
        )
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with incomplete params
        params_json = json.dumps({"metric_name": "http_requests"})
        
        result_json = plugin.build_query_from_template(
            template="error_rate",
            params=params_json,
            execute=False
        )
        
        # Verify error is returned
        result = json.loads(result_json)
        assert "error" in result
        assert "Failed to build query" in result["error"]
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_build_query_execution_error(self, mock_fetcher_class):
        """Test building query with execution error."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        expected_query = 'rate(http_requests[5m])'
        mock_fetcher._build_query_from_template.return_value = expected_query
        mock_fetcher.fetch.side_effect = QueryError("Query timeout")
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with execution
        params_json = json.dumps({"metric_name": "http_requests", "window": "5m"})
        
        result_json = plugin.build_query_from_template(
            template="request_rate",
            params=params_json,
            execute=True
        )
        
        # Verify error is returned with query
        result = json.loads(result_json)
        assert "error" in result
        assert "Failed to execute query" in result["error"]
        assert "query" in result
        assert result["query"] == expected_query


class TestListPromQLTemplates:
    """Tests for list_templates kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_list_templates(self, mock_fetcher_class):
        """Test listing all available templates."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        # Call function
        result_json = plugin.list_templates()
        
        # Verify
        result = json.loads(result_json)
        
        # Check all templates are present
        expected_templates = [
            "error_rate",
            "latency_p95",
            "latency_p99",
            "request_rate",
            "cpu_usage",
            "memory_usage"
        ]
        
        for template_name in expected_templates:
            assert template_name in result
            assert "pattern" in result[template_name]
            assert "description" in result[template_name]
            assert "required_params" in result[template_name]
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_list_templates_includes_patterns(self, mock_fetcher_class):
        """Test that template listing includes actual PromQL patterns."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        # Call function
        result_json = plugin.list_templates()
        result = json.loads(result_json)
        
        # Verify patterns match PROMQL_TEMPLATES
        assert result["error_rate"]["pattern"] == PROMQL_TEMPLATES["error_rate"]
        assert result["latency_p95"]["pattern"] == PROMQL_TEMPLATES["latency_p95"]
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_list_templates_includes_required_params(self, mock_fetcher_class):
        """Test that template listing includes required parameters."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        # Call function
        result_json = plugin.list_templates()
        result = json.loads(result_json)
        
        # Verify required params
        assert "service" in result["error_rate"]["required_params"]
        assert "window" in result["error_rate"]["required_params"]
        assert "pod_pattern" in result["cpu_usage"]["required_params"]


class TestTestPrometheusConnection:
    """Tests for test_connection kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_connection_success(self, mock_fetcher_class):
        """Test successful connection test."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.return_value = True
        
        # Create plugin
        config = {"endpoint": "http://prometheus.prod.com:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "Successfully connected" in result
        assert "prometheus.prod.com:9090" in result
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_connection_failure(self, mock_fetcher_class):
        """Test failed connection test."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.return_value = False
        
        # Create plugin
        config = {"endpoint": "http://invalid-server:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "Failed to connect" in result
        assert "invalid-server:9090" in result
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_connection_exception(self, mock_fetcher_class):
        """Test connection test with exception."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.side_effect = ConnectionError("Network timeout")
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "connection error" in result
        assert "Network timeout" in result


class TestGetPrometheusCapabilities:
    """Tests for get_capabilities kernel function."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_get_capabilities(self, mock_fetcher_class):
        """Test getting plugin capabilities."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_capabilities = {
            "supports_time_window": True,
            "supports_streaming": False,
            "max_sample_size": 11000,
            "data_types": ["metrics"],
            "query_language": "PromQL",
            "templates": list(PROMQL_TEMPLATES.keys())
        }
        mock_fetcher.get_capabilities.return_value = mock_capabilities
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.get_capabilities()
        
        # Verify
        result = json.loads(result_json)
        assert result["supports_time_window"] is True
        assert result["max_sample_size"] == 11000
        assert "metrics" in result["data_types"]
        assert result["query_language"] == "PromQL"
        assert "error_rate" in result["templates"]


class TestKernelFunctionDecorators:
    """Tests for kernel function decorator metadata."""
    
    def test_fetch_metrics_has_kernel_function_decorator(self):
        """Test that fetch_metrics has kernel_function decorator."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        # Check that the method has kernel function metadata
        assert hasattr(plugin.fetch_metrics, '__kernel_function__') or \
               hasattr(plugin.fetch_metrics, '__kernel_function_name__') or \
               'fetch_prometheus_metrics' in str(plugin.fetch_metrics)
    
    def test_execute_query_has_kernel_function_decorator(self):
        """Test that execute_query has kernel_function decorator."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        assert hasattr(plugin.execute_query, '__kernel_function__') or \
               hasattr(plugin.execute_query, '__kernel_function_name__') or \
               'execute_promql_query' in str(plugin.execute_query)
    
    def test_all_public_methods_are_kernel_functions(self):
        """Test that all public methods (except __init__) are kernel functions."""
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        
        public_methods = [
            method for method in dir(plugin)
            if not method.startswith('_') and callable(getattr(plugin, method))
        ]
        
        # All public methods should be kernel functions
        expected_functions = [
            'fetch_metrics',
            'execute_query',
            'build_query_from_template',
            'list_templates',
            'test_connection',
            'get_capabilities'
        ]
        
        for func_name in expected_functions:
            assert func_name in public_methods


class TestPluginIntegrationWithKernel:
    """Integration tests for plugin with SK kernel."""
    
    @pytest.mark.asyncio
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    async def test_plugin_can_be_added_to_kernel(self, mock_fetcher_class):
        """Test that plugin can be added to SK kernel."""
        from semantic_kernel import Kernel
        
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin and kernel
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        kernel = Kernel()
        
        # Add plugin to kernel
        kernel.add_plugin(plugin, plugin_name="prometheus")
        
        # Verify plugin was added
        assert "prometheus" in kernel.plugins
        
        # Verify functions are available
        prom_plugin = kernel.plugins["prometheus"]
        function_names = [f.name for f in prom_plugin.functions.values()]
        assert "fetch_prometheus_metrics" in function_names
        assert "execute_promql_query" in function_names
        assert "build_promql_from_template" in function_names


class TestPluginErrorHandling:
    """Tests for error handling in plugin functions."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_connection_error_propagates(self, mock_fetcher_class):
        """Test that ConnectionError from fetcher propagates."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = ConnectionError("Connection refused")
        
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(ConnectionError):
            plugin.fetch_metrics(query="up")
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_query_error_propagates(self, mock_fetcher_class):
        """Test that QueryError from fetcher propagates."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = QueryError("Invalid PromQL syntax")
        
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(QueryError):
            plugin.fetch_metrics(query="invalid[")
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_auth_error_propagates(self, mock_fetcher_class):
        """Test that AuthenticationError from fetcher propagates."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = AuthenticationError("Invalid credentials")
        
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(AuthenticationError):
            plugin.fetch_metrics(query="up")
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_execute_query_error_propagates(self, mock_fetcher_class):
        """Test that errors from execute_query propagate."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = ConnectionError("Timeout")
        
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(ConnectionError):
            plugin.execute_query(query="up")


class TestPluginJSONSerialization:
    """Tests for JSON serialization of plugin responses."""
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_fetch_metrics_datetime_serialization(self, mock_fetcher_class):
        """Test that datetime objects are properly serialized to ISO format."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        start_time = datetime(2025, 10, 15, 10, 0, 0)
        end_time = datetime(2025, 10, 15, 12, 0, 0)
        
        mock_result = FetchResult(
            source="prometheus",
            data=[],
            summary="test",
            count=0,
            time_range=(start_time, end_time),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.fetch_metrics(query="up")
        
        # Verify datetime serialization
        result = json.loads(result_json)
        assert result["time_range"][0] == "2025-10-15T10:00:00"
        assert result["time_range"][1] == "2025-10-15T12:00:00"
    
    @patch('aletheia.plugins.prometheus_plugin.PrometheusFetcher')
    def test_all_functions_return_valid_json(self, mock_fetcher_class):
        """Test that all functions return valid JSON strings."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_fetcher.test_connection.return_value = True
        mock_fetcher.get_capabilities.return_value = {"test": "capability"}
        
        # Create plugin
        config = {"endpoint": "http://prometheus:9090"}
        plugin = PrometheusPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Test list_templates
        templates_json = plugin.list_templates()
        templates = json.loads(templates_json)
        assert isinstance(templates, dict)
        
        # Test get_capabilities
        capabilities_json = plugin.get_capabilities()
        capabilities = json.loads(capabilities_json)
        assert isinstance(capabilities, dict)
        
        # Test connection (returns string, not JSON)
        connection_result = plugin.test_connection()
        assert isinstance(connection_result, str)
