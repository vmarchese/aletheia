"""Semantic Kernel plugin for Kubernetes operations.

This plugin exposes Kubernetes operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin wraps KubernetesFetcher functionality and provides annotated
functions for:
- Fetching logs from pods
- Listing pods in namespaces
- Getting pod status information
- Testing Kubernetes connectivity
"""

import json
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from semantic_kernel.functions import kernel_function

from aletheia.fetchers.kubernetes import KubernetesFetcher
from aletheia.utils.logging import log_operation_start, log_operation_complete, log_plugin_invocation


class KubernetesPlugin:
    """Semantic Kernel plugin for Kubernetes operations.
    
    This plugin provides kernel functions that wrap KubernetesFetcher
    operations, allowing SK agents to automatically invoke Kubernetes
    operations via function calling.
    
    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.
    
    Attributes:
        fetcher: KubernetesFetcher instance for actual Kubernetes operations
        context: Kubernetes context name
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Kubernetes plugin.
        
        Args:
            config: Configuration dictionary with Kubernetes settings.
                   Must contain 'context' key for kubectl context.
        
        Raises:
            ValueError: If required configuration is missing
        """
        if "context" not in config:
            raise ValueError("Kubernetes 'context' is required in config")
        
        self.config = config
        self.fetcher = KubernetesFetcher(config)
        self.context = config["context"]
    
    @kernel_function(
        name="fetch_kubernetes_logs",
        description="Fetch logs from a Kubernetes pod with optional time window filtering and sampling"
    )
    def fetch_logs(
        self,
        pod: Annotated[str, "The name of the pod to fetch logs from"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
        container: Annotated[Optional[str], "Optional container name within the pod"] = None,
        sample_size: Annotated[int, "Target number of log entries to return (default: 200)"] = 200,
        since_minutes: Annotated[Optional[int], "Fetch logs from the last N minutes"] = None,
    ) -> Annotated[str, "JSON string containing logs, summary, and metadata"]:
        """Fetch logs from a Kubernetes pod.
        
        This function fetches logs from the specified pod, applies intelligent
        sampling (prioritizing ERROR and FATAL logs), and returns a structured
        result with logs, summary, and metadata.
        
        Args:
            pod: Pod name to fetch logs from
            namespace: Kubernetes namespace (default: "default")
            container: Optional container name within the pod
            sample_size: Target number of logs to return (default: 200)
            since_minutes: Optional time window in minutes (fetch logs from last N minutes)
        
        Returns:
            JSON string with structure:
            {
                "logs": [...],
                "summary": "...",
                "count": 123,
                "metadata": {...}
            }
        """
        # Log plugin invocation
        log_plugin_invocation(
            plugin_name="KubernetesPlugin",
            function_name="fetch_logs",
            parameters={
                "pod": pod,
                "namespace": namespace,
                "container": container,
                "sample_size": sample_size,
                "since_minutes": since_minutes
            }
        )
        
        # Start operation timing
        start_time = log_operation_start(
            operation_name=f"kubectl_logs_{pod}",
            details={"namespace": namespace, "pod": pod}
        )
        
        # Prepare time window if specified
        time_window = None
        if since_minutes is not None:
            from datetime import timedelta
            end_time = datetime.now()
            start_time_window = end_time - timedelta(minutes=since_minutes)
            time_window = (start_time_window, end_time)
        
        # Call fetcher
        result = self.fetcher.fetch(
            time_window=time_window,
            namespace=namespace,
            pod=pod,
            container=container,
            sample_size=sample_size
        )
        
        # Log completion
        log_operation_complete(
            operation_name=f"kubectl_logs_{pod}",
            start_time=start_time,
            result_summary=f"{result.count} logs collected"
        )
        
        # Return as JSON string for LLM consumption
        return json.dumps({
            "logs": result.data,
            "summary": result.summary,
            "count": result.count,
            "time_range": [
                result.time_range[0].isoformat(),
                result.time_range[1].isoformat()
            ],
            "metadata": result.metadata
        }, indent=2)
    
    @kernel_function(
        name="list_kubernetes_pods",
        description="List all pods in a Kubernetes namespace, optionally filtered by label selector"
    )
    def list_pods(
        self,
        namespace: Annotated[str, "The Kubernetes namespace to list pods from"] = "default",
        selector: Annotated[Optional[str], "Optional label selector (e.g., 'app=payments-svc')"] = None,
    ) -> Annotated[str, "JSON array of pod names"]:
        """List pods in a Kubernetes namespace.
        
        Args:
            namespace: Kubernetes namespace to list pods from (default: "default")
            selector: Optional label selector for filtering pods (e.g., "app=payments-svc")
        
        Returns:
            JSON array of pod names as a string
        """
        # Log plugin invocation
        log_plugin_invocation(
            plugin_name="KubernetesPlugin",
            function_name="list_pods",
            parameters={"namespace": namespace, "selector": selector}
        )
        
        # Start operation timing
        start_time = log_operation_start(
            operation_name=f"kubectl_list_pods_{namespace}",
            details={"namespace": namespace, "selector": selector}
        )
        
        pods = self.fetcher.list_pods(namespace=namespace, selector=selector)
        
        # Log completion
        log_operation_complete(
            operation_name=f"kubectl_list_pods_{namespace}",
            start_time=start_time,
            result_summary=f"{len(pods)} pods found"
        )
        
        return json.dumps(pods, indent=2)
    
    @kernel_function(
        name="get_kubernetes_pod_status",
        description="Get detailed status information for a specific Kubernetes pod"
    )
    def get_pod_status(
        self,
        pod: Annotated[str, "The name of the pod to get status for"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
    ) -> Annotated[str, "JSON object with pod status information"]:
        """Get status information for a Kubernetes pod.
        
        Args:
            pod: Pod name to get status for
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            JSON string with pod status including:
            - name, namespace
            - phase (Running, Pending, Failed, etc.)
            - conditions
            - container statuses
            - start time
        """
        # Log plugin invocation
        log_plugin_invocation(
            plugin_name="KubernetesPlugin",
            function_name="get_pod_status",
            parameters={"pod": pod, "namespace": namespace}
        )
        
        # Start operation timing
        start_time = log_operation_start(
            operation_name=f"kubectl_get_status_{pod}",
            details={"namespace": namespace, "pod": pod}
        )
        
        status = self.fetcher.get_pod_status(pod=pod, namespace=namespace)
        
        # Log completion
        log_operation_complete(
            operation_name=f"kubectl_get_status_{pod}",
            start_time=start_time,
            result_summary=f"Status: {status.get('phase', 'Unknown')}"
        )
        
        return json.dumps(status, indent=2)
    
    @kernel_function(
        name="test_kubernetes_connection",
        description="Test connectivity to the Kubernetes cluster"
    )
    def test_connection(self) -> Annotated[str, "Connection test result message"]:
        """Test connection to Kubernetes cluster.
        
        Returns:
            Success message if connection works, error message otherwise
        """
        try:
            success = self.fetcher.test_connection()
            if success:
                return f"Successfully connected to Kubernetes cluster (context: {self.context})"
            else:
                return f"Failed to connect to Kubernetes cluster (context: {self.context})"
        except Exception as e:
            return f"Kubernetes connection error: {str(e)}"
    
    @kernel_function(
        name="get_kubernetes_capabilities",
        description="Get information about what operations this Kubernetes plugin supports"
    )
    def get_capabilities(self) -> Annotated[str, "JSON object describing plugin capabilities"]:
        """Get Kubernetes plugin capabilities.
        
        Returns:
            JSON string describing what operations are supported
        """
        capabilities = self.fetcher.get_capabilities()
        return json.dumps(capabilities, indent=2)
