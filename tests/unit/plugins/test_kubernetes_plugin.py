"""Unit tests for Kubernetes Semantic Kernel plugin.

Tests the KubernetesPlugin class that exposes Kubernetes operations
as kernel functions for SK agents.
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock

from aletheia.plugins.kubernetes_plugin import KubernetesPlugin


class TestKubernetesPluginInitialization:
    """Tests for KubernetesPlugin initialization."""
    
    def test_init_with_valid_config(self):
        """Test plugin initialization with valid configuration."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        assert plugin.context == "test-context"
        assert plugin.namespace == "default"
    
    def test_init_without_context_raises_error(self):
        """Test that initialization without context raises ValueError."""
        config = {}
        
        with pytest.raises(ValueError, match="'context' is required"):
            KubernetesPlugin(config)
    
    def test_init_with_custom_namespace(self):
        """Test initialization with custom namespace."""
        config = {
            "context": "prod-cluster",
            "namespace": "production"
        }
        plugin = KubernetesPlugin(config)
        
        assert plugin.context == "prod-cluster"
        assert plugin.namespace == "production"


class TestFetchKubernetesLogs:
    """Tests for fetch_kubernetes_logs kernel function."""
    
    @pytest.mark.asyncio
    async def test_fetch_logs_basic(self):
        """Test basic log fetching."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock successful kubectl process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"log line 1\nlog line 2\nlog line 3\n",
            b""
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.fetch_kubernetes_logs(
                pod="test-pod",
                namespace="default"
            )
        
        # Verify result
        result = json.loads(result_json)
        assert result["pod"] == "test-pod"
        assert result["namespace"] == "default"
        assert result["count"] == 3
        assert len(result["logs"]) == 3
        assert result["logs"][0] == "log line 1"
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_fetch_logs_with_container(self):
        """Test log fetching with container parameter."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock successful kubectl process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"container log\n", b"")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result_json = await plugin.fetch_kubernetes_logs(
                pod="test-pod",
                namespace="production",
                container="app",
                tail_lines=50,
                since_minutes=30
            )
        
        # Verify kubectl command was called correctly
        call_args = mock_exec.call_args[0]
        assert "kubectl" in call_args
        assert "--context" in call_args
        assert "test-context" in call_args
        assert "--namespace" in call_args
        assert "production" in call_args
        assert "logs" in call_args
        assert "test-pod" in call_args
        assert "--container" in call_args
        assert "app" in call_args
        assert "--tail" in call_args
        assert "50" in call_args
        assert "--since" in call_args
        assert "30m" in call_args
        
        # Verify result
        result = json.loads(result_json)
        assert result["container"] == "app"
    
    @pytest.mark.asyncio
    async def test_fetch_logs_kubectl_error(self):
        """Test handling of kubectl command errors."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock failed kubectl process
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (
            b"",
            b"Error from server (NotFound): pods \"missing-pod\" not found"
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.fetch_kubernetes_logs(
                pod="missing-pod",
                namespace="default"
            )
        
        # Verify error is returned in JSON
        result = json.loads(result_json)
        assert "error" in result
        assert "kubectl logs failed" in result["error"]
        assert "NotFound" in result["error"]
        assert result["pod"] == "missing-pod"
    
    @pytest.mark.asyncio
    async def test_fetch_logs_exception(self):
        """Test handling of exceptions during log fetching."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        with patch('asyncio.create_subprocess_exec', side_effect=Exception("Connection timeout")):
            result_json = await plugin.fetch_kubernetes_logs(
                pod="test-pod",
                namespace="default"
            )
        
        # Verify error is returned in JSON
        result = json.loads(result_json)
        assert "error" in result
        assert "Failed to fetch logs" in result["error"]
        assert "Connection timeout" in result["error"]


class TestListKubernetesPods:
    """Tests for list_kubernetes_pods kernel function."""
    
    @pytest.mark.asyncio
    async def test_list_pods_basic(self):
        """Test basic pod listing."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock kubectl get pods JSON output
        kubectl_output = {
            "items": [
                {
                    "metadata": {
                        "name": "pod1",
                        "namespace": "default",
                        "creationTimestamp": "2025-01-01T10:00:00Z"
                    },
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [
                            {"ready": True, "restartCount": 0}
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "pod2",
                        "namespace": "default",
                        "creationTimestamp": "2025-01-01T11:00:00Z"
                    },
                    "status": {
                        "phase": "Pending",
                        "containerStatuses": [
                            {"ready": False, "restartCount": 1}
                        ]
                    }
                }
            ]
        }
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            json.dumps(kubectl_output).encode(),
            b""
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.list_kubernetes_pods(namespace="default")
        
        # Verify result
        result = json.loads(result_json)
        assert result["namespace"] == "default"
        assert result["count"] == 2
        assert len(result["pods"]) == 2
        
        # Check first pod
        pod1 = result["pods"][0]
        assert pod1["name"] == "pod1"
        assert pod1["phase"] == "Running"
        assert pod1["ready"] == "1/1"
        
        # Check second pod
        pod2 = result["pods"][1]
        assert pod2["name"] == "pod2"
        assert pod2["phase"] == "Pending"
        assert pod2["ready"] == "0/1"
    
    @pytest.mark.asyncio
    async def test_list_pods_with_selector(self):
        """Test pod listing with label selector."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        kubectl_output = {"items": []}
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            json.dumps(kubectl_output).encode(),
            b""
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result_json = await plugin.list_kubernetes_pods(
                namespace="production",
                selector="app=payments-svc"
            )
        
        # Verify kubectl command included selector
        call_args = mock_exec.call_args[0]
        assert "-l" in call_args
        assert "app=payments-svc" in call_args
        
        # Verify result
        result = json.loads(result_json)
        assert result["selector"] == "app=payments-svc"
        assert result["count"] == 0
    
    @pytest.mark.asyncio
    async def test_list_pods_kubectl_error(self):
        """Test handling of kubectl errors."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (
            b"",
            b"Error from server (Forbidden): pods is forbidden"
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.list_kubernetes_pods(namespace="forbidden")
        
        # Verify error is returned
        result = json.loads(result_json)
        assert "error" in result
        assert "kubectl get pods failed" in result["error"]
        assert "Forbidden" in result["error"]


class TestGetPodStatus:
    """Tests for get_pod_status kernel function."""
    
    @pytest.mark.asyncio
    async def test_get_pod_status_basic(self):
        """Test getting pod status."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock kubectl get pod JSON output
        kubectl_output = {
            "metadata": {
                "name": "test-pod",
                "namespace": "default"
            },
            "spec": {
                "nodeName": "worker-node-1"
            },
            "status": {
                "phase": "Running",
                "podIP": "10.244.1.5",
                "hostIP": "192.168.1.10",
                "startTime": "2025-01-01T10:00:00Z",
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "PodScheduled", "status": "True"}
                ],
                "containerStatuses": [
                    {
                        "name": "app",
                        "ready": True,
                        "restartCount": 0
                    }
                ]
            }
        }
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            json.dumps(kubectl_output).encode(),
            b""
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.get_pod_status(
                pod="test-pod",
                namespace="default"
            )
        
        # Verify result
        result = json.loads(result_json)
        assert result["name"] == "test-pod"
        assert result["namespace"] == "default"
        assert result["phase"] == "Running"
        assert result["pod_ip"] == "10.244.1.5"
        assert result["node"] == "worker-node-1"
        assert result["ready"] == "1/1"
        assert result["restarts"] == 0
        assert len(result["conditions"]) == 2
        assert len(result["container_statuses"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_pod_status_failed_pod(self):
        """Test getting status of a failed pod."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        kubectl_output = {
            "metadata": {
                "name": "failed-pod",
                "namespace": "production"
            },
            "spec": {},
            "status": {
                "phase": "Failed",
                "conditions": [],
                "containerStatuses": [
                    {
                        "name": "app",
                        "ready": False,
                        "restartCount": 5
                    }
                ]
            }
        }
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            json.dumps(kubectl_output).encode(),
            b""
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.get_pod_status(
                pod="failed-pod",
                namespace="production"
            )
        
        # Verify result
        result = json.loads(result_json)
        assert result["phase"] == "Failed"
        assert result["ready"] == "0/1"
        assert result["restarts"] == 5
    
    @pytest.mark.asyncio
    async def test_get_pod_status_not_found(self):
        """Test getting status of non-existent pod."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (
            b"",
            b"Error from server (NotFound): pods \"missing-pod\" not found"
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result_json = await plugin.get_pod_status(
                pod="missing-pod",
                namespace="default"
            )
        
        # Verify error is returned
        result = json.loads(result_json)
        assert "error" in result
        assert "kubectl get pod failed" in result["error"]
        assert "NotFound" in result["error"]


class TestHelperMethods:
    """Tests for helper methods."""
    
    def test_count_ready_containers(self):
        """Test counting ready containers."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Test with no containers
        status = {"containerStatuses": []}
        assert plugin._count_ready_containers(status) == "0/0"
        
        # Test with mixed ready/not ready
        status = {
            "containerStatuses": [
                {"ready": True},
                {"ready": False},
                {"ready": True}
            ]
        }
        assert plugin._count_ready_containers(status) == "2/3"
        
        # Test with missing containerStatuses
        status = {}
        assert plugin._count_ready_containers(status) == "0/0"
    
    def test_count_restarts(self):
        """Test counting total restarts."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Test with no containers
        status = {"containerStatuses": []}
        assert plugin._count_restarts(status) == 0
        
        # Test with restarts
        status = {
            "containerStatuses": [
                {"restartCount": 2},
                {"restartCount": 5},
                {"restartCount": 0}
            ]
        }
        assert plugin._count_restarts(status) == 7
        
        # Test with missing restartCount
        status = {
            "containerStatuses": [
                {"restartCount": 1},
                {}  # Missing restartCount
            ]
        }
        assert plugin._count_restarts(status) == 1


class TestKernelFunctionDecorators:
    """Tests for kernel function decorator metadata."""
    
    def test_all_functions_have_kernel_decorators(self):
        """Test that all public methods have kernel_function decorators."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Get all async methods that should be kernel functions
        expected_functions = [
            "fetch_kubernetes_logs",
            "list_kubernetes_pods", 
            "get_pod_status"
        ]
        
        for func_name in expected_functions:
            method = getattr(plugin, func_name)
            # Check that method exists and is callable
            assert callable(method)
            # SK decorators add metadata to functions
            assert hasattr(method, '__name__')


class TestPluginIntegrationWithKernel:
    """Integration tests for plugin with SK kernel."""
    
    @pytest.mark.asyncio
    async def test_plugin_can_be_added_to_kernel(self):
        """Test that plugin can be added to SK kernel."""
        try:
            from semantic_kernel import Kernel
            
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
            function_names = [f.name for f in k8s_plugin.functions.values()]
            assert "fetch_kubernetes_logs" in function_names
            assert "list_kubernetes_pods" in function_names
            assert "get_pod_status" in function_names
            
        except ImportError:
            pytest.skip("Semantic Kernel not available for integration test")


class TestAsyncBehavior:
    """Tests for async behavior of plugin functions."""
    
    @pytest.mark.asyncio
    async def test_all_functions_are_async(self):
        """Test that all kernel functions are async."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Test that methods are coroutines
        assert asyncio.iscoroutinefunction(plugin.fetch_kubernetes_logs)
        assert asyncio.iscoroutinefunction(plugin.list_kubernetes_pods)
        assert asyncio.iscoroutinefunction(plugin.get_pod_status)
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test that multiple plugin calls can run concurrently."""
        config = {"context": "test-context"}
        plugin = KubernetesPlugin(config)
        
        # Mock processes for concurrent calls
        mock_process1 = AsyncMock()
        mock_process1.returncode = 0
        mock_process1.communicate.return_value = (b"logs from pod1\n", b"")
        
        mock_process2 = AsyncMock()
        mock_process2.returncode = 0
        mock_process2.communicate.return_value = (b"logs from pod2\n", b"")
        
        # Create side effect that returns different mocks for different calls
        call_count = 0
        def mock_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_process1 if call_count == 1 else mock_process2
        
        with patch('asyncio.create_subprocess_exec', side_effect=mock_subprocess):
            # Run two log fetches concurrently
            results = await asyncio.gather(
                plugin.fetch_kubernetes_logs(pod="pod1", namespace="default"),
                plugin.fetch_kubernetes_logs(pod="pod2", namespace="default")
            )
        
        # Verify both completed successfully
        assert len(results) == 2
        result1 = json.loads(results[0])
        result2 = json.loads(results[1])
        
        assert result1["pod"] == "pod1"
        assert result2["pod"] == "pod2"
        assert "logs from pod1" in result1["logs"][0]
        assert "logs from pod2" in result2["logs"][0]
