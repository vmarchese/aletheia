"""Unit tests for Kubernetes Semantic Kernel plugin.

Tests the KubernetesPlugin class that exposes Kubernetes operations
as kernel functions for SK agents.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from aletheia.plugins.kubernetes_plugin import KubernetesPlugin
from aletheia.fetchers.base import FetchResult, ConnectionError, QueryError


class TestKubernetesPluginInitialization:
    """Tests for KubernetesPlugin initialization."""
    
    def test_init_with_valid_config(self):
        """Test plugin initialization with valid configuration."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        assert plugin.context == "test-context"
        assert plugin.config == config
        assert plugin.fetcher is not None
    
    def test_init_without_context_raises_error(self):
        """Test that initialization without context raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="'context' is required"):
            KubernetesPlugin(config)
    
    def test_init_with_additional_config(self):
        """Test initialization with additional configuration options."""
        config = {
            "context": "prod-cluster",
            "namespace": "production",
            "timeout": 60
        }
        plugin = KubernetesPlugin(config)
        
        assert plugin.context == "prod-cluster"
        assert plugin.config["namespace"] == "production"


class TestFetchKubernetesLogs:
    """Tests for fetch_logs kernel function."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_basic(self, mock_fetcher_class):
        """Test basic log fetching without time window."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="kubernetes",
            data=[{"level": "ERROR", "message": "test error"}],
            summary="1 logs (1 ERROR)",
            count=1,
            time_range=(datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 11, 0)),
            metadata={"pod": "test-pod"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.fetch_logs(
            pod="test-pod",
            namespace="default"
        )
        
        # Verify
        result = json.loads(result_json)
        assert result["count"] == 1
        assert result["summary"] == "1 logs (1 ERROR)"
        assert len(result["logs"]) == 1
        assert result["logs"][0]["level"] == "ERROR"
        
        # Verify fetcher was called correctly
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["namespace"] == "default"
        assert call_kwargs["pod"] == "test-pod"
        assert call_kwargs["sample_size"] == 200
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_with_time_window(self, mock_fetcher_class):
        """Test log fetching with since_minutes parameter."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now() - timedelta(minutes=30), datetime.now()),
            metadata={}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with time window
        result_json = plugin.fetch_logs(
            pod="test-pod",
            namespace="default",
            since_minutes=30
        )
        
        # Verify time window was passed
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["time_window"] is not None
        
        start_time, end_time = call_kwargs["time_window"]
        # Time window should be approximately 30 minutes
        duration = (end_time - start_time).total_seconds()
        assert 29 * 60 <= duration <= 31 * 60
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_with_container(self, mock_fetcher_class):
        """Test log fetching with container parameter."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="kubernetes",
            data=[],
            summary="0 logs",
            count=0,
            time_range=(datetime.now(), datetime.now()),
            metadata={"container": "app"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with container
        result_json = plugin.fetch_logs(
            pod="test-pod",
            namespace="production",
            container="app",
            sample_size=500
        )
        
        # Verify parameters
        mock_fetcher.fetch.assert_called_once()
        call_kwargs = mock_fetcher.fetch.call_args[1]
        assert call_kwargs["container"] == "app"
        assert call_kwargs["sample_size"] == 500
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_returns_valid_json(self, mock_fetcher_class):
        """Test that fetch_logs returns valid JSON string."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_result = FetchResult(
            source="kubernetes",
            data=[{"level": "INFO", "message": "test"}],
            summary="1 logs",
            count=1,
            time_range=(datetime(2025, 1, 1), datetime(2025, 1, 2)),
            metadata={"test": "data"}
        )
        mock_fetcher.fetch.return_value = mock_result
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.fetch_logs(pod="test-pod")
        
        # Verify JSON is valid
        result = json.loads(result_json)
        assert "logs" in result
        assert "summary" in result
        assert "count" in result
        assert "time_range" in result
        assert "metadata" in result
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_handles_fetcher_error(self, mock_fetcher_class):
        """Test that fetch_logs propagates errors from fetcher."""
        # Setup mock to raise error
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = ConnectionError("kubectl failed")
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function should raise error
        with pytest.raises(ConnectionError, match="kubectl failed"):
            plugin.fetch_logs(pod="test-pod")


class TestListKubernetesPods:
    """Tests for list_pods kernel function."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_list_pods_basic(self, mock_fetcher_class):
        """Test basic pod listing."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.list_pods.return_value = ["pod1", "pod2", "pod3"]
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.list_pods(namespace="default")
        
        # Verify
        result = json.loads(result_json)
        assert result == ["pod1", "pod2", "pod3"]
        
        mock_fetcher.list_pods.assert_called_once_with(
            namespace="default",
            selector=None
        )
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_list_pods_with_selector(self, mock_fetcher_class):
        """Test pod listing with label selector."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.list_pods.return_value = ["app-pod-1", "app-pod-2"]
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function with selector
        result_json = plugin.list_pods(
            namespace="production",
            selector="app=payments-svc"
        )
        
        # Verify
        result = json.loads(result_json)
        assert result == ["app-pod-1", "app-pod-2"]
        
        mock_fetcher.list_pods.assert_called_once_with(
            namespace="production",
            selector="app=payments-svc"
        )
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_list_pods_empty_result(self, mock_fetcher_class):
        """Test pod listing with no pods found."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.list_pods.return_value = []
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.list_pods(namespace="empty")
        
        # Verify
        result = json.loads(result_json)
        assert result == []


class TestGetKubernetesPodStatus:
    """Tests for get_pod_status kernel function."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_get_pod_status_basic(self, mock_fetcher_class):
        """Test getting pod status."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_status = {
            "name": "test-pod",
            "namespace": "default",
            "phase": "Running",
            "conditions": [{"type": "Ready", "status": "True"}],
            "container_statuses": [{"name": "app", "ready": True}],
            "start_time": "2025-01-01T10:00:00Z"
        }
        mock_fetcher.get_pod_status.return_value = mock_status
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.get_pod_status(
            pod="test-pod",
            namespace="default"
        )
        
        # Verify
        result = json.loads(result_json)
        assert result["name"] == "test-pod"
        assert result["phase"] == "Running"
        assert len(result["conditions"]) == 1
        
        mock_fetcher.get_pod_status.assert_called_once_with(
            pod="test-pod",
            namespace="default"
        )
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_get_pod_status_failed_pod(self, mock_fetcher_class):
        """Test getting status of a failed pod."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_status = {
            "name": "failed-pod",
            "namespace": "production",
            "phase": "Failed",
            "conditions": [],
            "container_statuses": [],
            "start_time": None
        }
        mock_fetcher.get_pod_status.return_value = mock_status
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.get_pod_status(
            pod="failed-pod",
            namespace="production"
        )
        
        # Verify
        result = json.loads(result_json)
        assert result["phase"] == "Failed"
        assert result["start_time"] is None


class TestTestKubernetesConnection:
    """Tests for test_connection kernel function."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_connection_success(self, mock_fetcher_class):
        """Test successful connection test."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.return_value = True
        
        # Create plugin
        config = {"context": "prod-cluster"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "Successfully connected" in result
        assert "prod-cluster" in result
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_connection_failure(self, mock_fetcher_class):
        """Test failed connection test."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.return_value = False
        
        # Create plugin
        config = {"context": "invalid-cluster"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "Failed to connect" in result
        assert "invalid-cluster" in result
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_connection_exception(self, mock_fetcher_class):
        """Test connection test with exception."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.test_connection.side_effect = Exception("Network error")
        
        # Create plugin
        config = {"context": "test-cluster"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result = plugin.test_connection()
        
        # Verify
        assert "connection error" in result
        assert "Network error" in result


class TestGetKubernetesCapabilities:
    """Tests for get_capabilities kernel function."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_get_capabilities(self, mock_fetcher_class):
        """Test getting plugin capabilities."""
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        mock_capabilities = {
            "supports_time_window": True,
            "supports_streaming": False,
            "max_sample_size": 10000,
            "data_types": ["logs"],
            "sampling_strategies": ["level-based", "random"],
            "retry_enabled": True,
            "default_retries": 3
        }
        mock_fetcher.get_capabilities.return_value = mock_capabilities
        
        # Create plugin
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        # Call function
        result_json = plugin.get_capabilities()
        
        # Verify
        result = json.loads(result_json)
        assert result["supports_time_window"] is True
        assert result["max_sample_size"] == 10000
        assert "logs" in result["data_types"]


class TestKernelFunctionDecorators:
    """Tests for kernel function decorator metadata."""
    
    def test_fetch_logs_has_kernel_function_decorator(self):
        """Test that fetch_logs has kernel_function decorator."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Check that the method has kernel function metadata
        assert hasattr(plugin.fetch_logs, '__kernel_function__') or \
               hasattr(plugin.fetch_logs, '__kernel_function_name__') or \
               'fetch_kubernetes_logs' in str(plugin.fetch_logs)
    
    def test_list_pods_has_kernel_function_decorator(self):
        """Test that list_pods has kernel_function decorator."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        assert hasattr(plugin.list_pods, '__kernel_function__') or \
               hasattr(plugin.list_pods, '__kernel_function_name__') or \
               'list_kubernetes_pods' in str(plugin.list_pods)
    
    def test_all_public_methods_are_kernel_functions(self):
        """Test that all public methods (except __init__) are kernel functions."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        public_methods = [
            method for method in dir(plugin)
            if not method.startswith('_') and callable(getattr(plugin, method))
        ]
        
        # All public methods should be kernel functions
        # (except properties like 'context', 'config', 'fetcher')
        expected_functions = [
            'fetch_logs',
            'list_pods',
            'get_pod_status',
            'test_connection',
            'get_capabilities'
        ]
        
        for func_name in expected_functions:
            assert func_name in public_methods


class TestPluginIntegrationWithKernel:
    """Integration tests for plugin with SK kernel."""
    
    @pytest.mark.asyncio
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    async def test_plugin_can_be_added_to_kernel(self, mock_fetcher_class):
        """Test that plugin can be added to SK kernel."""
        from semantic_kernel import Kernel
        
        # Setup mock
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        
        # Create plugin and kernel
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        kernel = Kernel()
        
        # Add plugin to kernel
        kernel.add_plugin(plugin, plugin_name="kubernetes")
        
        # Verify plugin was added
        assert "kubernetes" in kernel.plugins
        
        # Verify functions are available
        k8s_plugin = kernel.plugins["kubernetes"]
        assert "fetch_kubernetes_logs" in [f.name for f in k8s_plugin.functions.values()]
        assert "list_kubernetes_pods" in [f.name for f in k8s_plugin.functions.values()]


class TestPluginErrorHandling:
    """Tests for error handling in plugin functions."""
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_fetch_logs_connection_error_propagates(self, mock_fetcher_class):
        """Test that ConnectionError from fetcher propagates."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.fetch.side_effect = ConnectionError("Connection refused")
        
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(ConnectionError):
            plugin.fetch_logs(pod="test-pod")
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_list_pods_query_error_propagates(self, mock_fetcher_class):
        """Test that QueryError from fetcher propagates."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.list_pods.side_effect = QueryError("Invalid selector")
        
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(QueryError):
            plugin.list_pods(namespace="default", selector="invalid=")
    
    @patch('aletheia.plugins.kubernetes_plugin.KubernetesFetcher')
    def test_get_pod_status_error_propagates(self, mock_fetcher_class):
        """Test that errors from get_pod_status propagate."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher
        mock_fetcher.get_pod_status.side_effect = ConnectionError("Pod not found")
        
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        plugin.fetcher = mock_fetcher
        
        with pytest.raises(ConnectionError):
            plugin.get_pod_status(pod="missing-pod")
