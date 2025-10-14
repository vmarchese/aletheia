"""Integration tests for Kubernetes fetcher with real kubectl.

These tests require a running Kubernetes cluster accessible via kubectl.
Set the environment variable SKIP_K8S_INTEGRATION=1 to skip these tests.
"""

import os
import subprocess
from datetime import datetime, timedelta

import pytest

from aletheia.fetchers.kubernetes import KubernetesFetcher
from aletheia.fetchers.base import ConnectionError

# Skip all tests in this module if SKIP_K8S_INTEGRATION is set
pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_K8S_INTEGRATION", "0") == "1",
    reason="Kubernetes integration tests disabled (SKIP_K8S_INTEGRATION=1)"
)


@pytest.fixture(scope="module")
def kubernetes_context():
    """Get the current Kubernetes context.
    
    Yields:
        str: Current Kubernetes context name
        
    Raises:
        pytest.skip: If kubectl is not available or no context is configured
    """
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            pytest.skip("No Kubernetes context configured")
        
        context = result.stdout.strip()
        if not context:
            pytest.skip("No Kubernetes context configured")
            
        return context
    except FileNotFoundError:
        pytest.skip("kubectl command not found")
    except subprocess.TimeoutExpired:
        pytest.skip("kubectl command timed out")


@pytest.fixture(scope="module")
def test_namespace():
    """Get or create a test namespace.
    
    Returns:
        str: Test namespace name (default or kube-system as fallback)
    """
    # Try to use kube-system namespace which should always exist
    try:
        result = subprocess.run(
            ["kubectl", "get", "namespace", "kube-system"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return "kube-system"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback to default namespace
    return "default"


@pytest.fixture
def kubernetes_fetcher(kubernetes_context):
    """Create a KubernetesFetcher instance with test configuration.
    
    Args:
        kubernetes_context: Current Kubernetes context from fixture
        
    Returns:
        KubernetesFetcher: Configured fetcher instance
    """
    config = {
        "context": kubernetes_context,
        "namespace": "kube-system"  # Use kube-system as it should always exist
    }
    return KubernetesFetcher(config)


class TestKubernetesConnection:
    """Test Kubernetes connectivity and configuration."""
    
    def test_connection_success(self, kubernetes_fetcher):
        """Test successful connection to Kubernetes cluster."""
        assert kubernetes_fetcher.test_connection() is True
    
    def test_connection_with_invalid_context(self):
        """Test connection failure with invalid context."""
        config = {
            "context": "nonexistent-context-12345",
            "namespace": "default"
        }
        fetcher = KubernetesFetcher(config)
        assert fetcher.test_connection() is False
    
    def test_capabilities(self, kubernetes_fetcher):
        """Test that fetcher reports correct capabilities."""
        capabilities = kubernetes_fetcher.get_capabilities()
        
        assert "supports_time_window" in capabilities
        assert capabilities["supports_time_window"] is True
        assert "data_types" in capabilities
        assert "logs" in capabilities["data_types"]


class TestKubernetesPodOperations:
    """Test pod listing and status operations."""
    
    def test_list_pods_in_namespace(self, kubernetes_fetcher, test_namespace):
        """Test listing pods in a namespace."""
        pods = kubernetes_fetcher.list_pods()
        
        # Should return a list (may be empty)
        assert isinstance(pods, list)
        # If there are pods, they should be strings
        for pod in pods:
            assert isinstance(pod, str)
            assert len(pod) > 0
    
    def test_list_pods_with_selector(self, kubernetes_fetcher):
        """Test listing pods with label selector."""
        # Use a common label that might exist in kube-system
        pods = kubernetes_fetcher.list_pods(selector="k8s-app")
        
        # Should return a list (may be empty)
        assert isinstance(pods, list)
    
    def test_get_pod_status(self, kubernetes_fetcher):
        """Test getting status of a specific pod."""
        # First, list pods to get a real pod name
        pods = kubernetes_fetcher.list_pods()
        
        if not pods:
            pytest.skip("No pods found in test namespace")
        
        # Get status of first pod
        pod_name = pods[0]
        status = kubernetes_fetcher.get_pod_status(pod_name)
        
        # Status should be a dictionary with expected fields
        assert isinstance(status, dict)
        # Kubernetes pod status should have these fields
        assert "metadata" in status or "status" in status or "phase" in status


class TestKubernetesLogFetching:
    """Test log fetching operations."""
    
    def test_fetch_logs_without_pod(self, kubernetes_fetcher):
        """Test fetching logs without specifying a pod."""
        # This should work but may return empty results
        result = kubernetes_fetcher.fetch()
        
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)
        assert isinstance(result.count, int)
        assert result.count >= 0
        assert isinstance(result.summary, str)
    
    def test_fetch_logs_with_time_window(self, kubernetes_fetcher):
        """Test fetching logs with time window."""
        # Fetch logs from last 10 minutes
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=10)
        time_window = (start_time, end_time)
        
        result = kubernetes_fetcher.fetch(time_window=time_window)
        
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)
        assert result.count >= 0
    
    def test_fetch_logs_from_specific_pod(self, kubernetes_fetcher):
        """Test fetching logs from a specific pod."""
        # First, get a list of pods
        pods = kubernetes_fetcher.list_pods()
        
        if not pods:
            pytest.skip("No pods found in test namespace")
        
        # Fetch logs from the first pod
        pod_name = pods[0]
        result = kubernetes_fetcher.fetch(pod=pod_name, sample_size=50)
        
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)
        # Count should not exceed sample_size
        assert result.count <= 50
        assert pod_name in result.metadata.get("pod", "")
    
    def test_fetch_logs_with_small_sample_size(self, kubernetes_fetcher):
        """Test fetching with very small sample size."""
        result = kubernetes_fetcher.fetch(sample_size=10)
        
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)
        # Should respect sample size limit
        assert result.count <= 10


class TestKubernetesErrorScenarios:
    """Test error handling in Kubernetes operations."""
    
    def test_fetch_from_nonexistent_pod(self, kubernetes_fetcher):
        """Test fetching logs from non-existent pod."""
        # Use a pod name that definitely doesn't exist
        result = kubernetes_fetcher.fetch(pod="nonexistent-pod-12345-abcde")
        
        # Should return empty result or raise ConnectionError
        # Depending on implementation, this might be an empty result
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)
    
    def test_fetch_from_nonexistent_namespace(self, kubernetes_context):
        """Test fetching from non-existent namespace."""
        config = {
            "context": kubernetes_context,
            "namespace": "nonexistent-namespace-12345"
        }
        fetcher = KubernetesFetcher(config)
        
        # Should handle gracefully
        result = fetcher.fetch()
        assert result.source == "kubernetes"
    
    def test_invalid_time_window(self, kubernetes_fetcher):
        """Test fetch with invalid time window (future dates)."""
        # Time window in the future
        start_time = datetime.now() + timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=2)
        time_window = (start_time, end_time)
        
        # Should handle gracefully and return empty results
        result = kubernetes_fetcher.fetch(time_window=time_window)
        assert result.source == "kubernetes"
        assert isinstance(result.data, list)


class TestKubernetesDataQuality:
    """Test data quality and consistency."""
    
    def test_log_format_consistency(self, kubernetes_fetcher):
        """Test that fetched logs have consistent format."""
        result = kubernetes_fetcher.fetch(sample_size=20)
        
        # Each log entry should be a dictionary with expected fields
        for log in result.data:
            assert isinstance(log, dict)
            # Logs should have at least timestamp or message
            assert "timestamp" in log or "message" in log or "log" in log
    
    def test_summary_generation(self, kubernetes_fetcher):
        """Test that summary is generated correctly."""
        result = kubernetes_fetcher.fetch(sample_size=30)
        
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        
        # Summary should mention count
        if result.count > 0:
            assert str(result.count) in result.summary or "log" in result.summary.lower()
    
    def test_time_range_in_result(self, kubernetes_fetcher):
        """Test that time range is included in result."""
        result = kubernetes_fetcher.fetch()
        
        assert result.time_range is not None
        assert isinstance(result.time_range, tuple)
        assert len(result.time_range) == 2
        
        start_time, end_time = result.time_range
        assert isinstance(start_time, datetime)
        assert isinstance(end_time, datetime)
        # End time should be after start time
        assert end_time >= start_time
    
    def test_metadata_completeness(self, kubernetes_fetcher):
        """Test that metadata includes relevant information."""
        pods = kubernetes_fetcher.list_pods()
        
        if not pods:
            pytest.skip("No pods found in test namespace")
        
        result = kubernetes_fetcher.fetch(pod=pods[0], sample_size=10)
        
        assert isinstance(result.metadata, dict)
        # Metadata should include namespace and context
        assert "namespace" in result.metadata or "context" in result.metadata
