"""Semantic Kernel plugin for Kubernetes operations.

This plugin exposes Kubernetes operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides simplified async functions for:
- Fetching logs from pods
- Listing pods in namespaces
- Getting pod status information
"""

import json
import subprocess
from datetime import datetime
from typing import Annotated, Any, Dict, Optional

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType


class KubernetesPlugin:
    """Semantic Kernel plugin for Kubernetes operations.
    
    This plugin provides simplified async kernel functions for Kubernetes
    operations, allowing SK agents to automatically invoke them via function calling.
    
    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.
    
    Attributes:
        context: Kubernetes context name
        namespace: Default namespace for operations
    """
    
    def __init__(self, 
                 config: Config,
                 session: Session):
        """Initialize the Kubernetes plugin.
        
        Args:
            config: Configuration dictionary with Kubernetes settings.
                   Must contain 'context' key for kubectl context.
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.context = config.kubernetes_context 
        self.namespace = config.kubernetes_namespace or "default"
        self.session = session
    
    @kernel_function(
        name="fetch_kubernetes_logs",
        description="Fetch logs from a Kubernetes pod with optional filtering and limiting"
    )
    def fetch_kubernetes_logs(
        self,
        pod: Annotated[str, "The name of the pod to fetch logs from"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
        container: Annotated[str, "Optional container name within the pod"] = None,
        tail_lines: Annotated[int, "Number of lines to fetch from the end of logs (default: 100)"] = 100,
        since_minutes: Annotated[str, "Fetch logs from the last N minutes (default: 30m)"] = "30",
    ) -> Annotated[str, "JSON string containing logs and metadata"]:
        """Fetch logs from a Kubernetes pod.
        
        This function fetches logs from the specified pod and returns them
        in a structured format with metadata.
        
        Args:
            pod: Pod name to fetch logs from
            namespace: Kubernetes namespace (default: "default")
            container: Optional container name within the pod
            tail_lines: Number of lines to fetch from end of logs (default: 100)
            since_minutes: Optional time window in minutes (fetch logs from last N minutes)
        
        Returns:
            JSON string with structure:
            {
                "logs": [...],
                "pod": "pod-name",
                "namespace": "namespace",
                "container": "container-name",
                "count": 123
            }
        """
        cmd = ["kubectl"]
        log_debug(f"KubernetesPlugin::fetch_kubernetes_logs:: Fetching logs for pod '{pod}' in namespace '{namespace}'")
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "--namespace", namespace,
            "logs", pod,
            "--tail", str(tail_lines)
        ])
        # Defensive: Coerce container to None if it's 'None', empty string, or not a string
        if container in ("None", "", None):
            container = None
        elif not isinstance(container, str):
            container = str(container)
        
        if container:
            cmd.extend(["--container", container])
        
        if since_minutes:
            cmd.extend(["--since", f"{since_minutes}m"])
        
        try:
            # Run kubectl command asynchronously
            log_debug(f"KubernetesPlugin::fetch_kubernetes_logs:: Running command: {' '.join(cmd)}")
            process = subprocess.run(args=cmd, capture_output=True)
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"kubectl logs failed: {error_msg}",
                    "pod": pod,
                    "namespace": namespace,
                    "container": container
                })
            
            # Parse logs into lines
            log_text = process.stdout.decode()
            log_lines = [line for line in log_text.split('\n') if line.strip()]

            # save log lines to session folder
            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.LOGS, f"{pod}_logs", log_text)
                log_debug(f"KubernetesPlugin::fetch_kubernetes_logs:: Saved logs to {saved}")
            
            return json.dumps({
                "logs": log_lines,
                "pod": pod,
                "namespace": namespace,
                "container": container,
                "count": len(log_lines),
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to fetch logs: {str(e)}",
                "pod": pod,
                "namespace": namespace,
                "container": container
            })
    
    @kernel_function(
        name="list_kubernetes_pods",
        description="List all pods in a Kubernetes namespace, optionally filtered by label selector"
    )
    def list_kubernetes_pods(
        self,
        namespace: Annotated[str, "The Kubernetes namespace to list pods from"] = "default",
        selector: Annotated[Optional[str], "Optional label selector (e.g., 'app=payments-svc')"] = None,
    ) -> Annotated[str, "JSON array of pod information"]:
        """List pods in a Kubernetes namespace.
        
        Args:
            namespace: Kubernetes namespace to list pods from (default: "default")
            selector: Optional label selector for filtering pods (e.g., "app=payments-svc")
        
        Returns:
            JSON array of pod information including names, status, and age
        """
        log_debug(f"KubernetesPlugin::list_kubernetes_pods:: Listing pods in namespace '{namespace}' with selector '{selector}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "--namespace", namespace,
            "get", "pods",
            "-o", "json"
        ])
        
        if selector:
            cmd.extend(["-l", selector])
        
        try:
            # Run kubectl command asynchronously
            log_debug(f"KubernetesPlugin::list_kubernetes_pods:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)
            log_debug("KubernetesPlugin::list_kubernetes_pods:: Command completed")
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                log_error(f"KubernetesPlugin::list_kubernetes_pods:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl get pods failed: {error_msg}",
                    "namespace": namespace,
                    "selector": selector
                })
            
            # Parse kubectl JSON output
            log_debug("KubernetesPlugin::list_kubernetes_pods:: Parsing kubectl output: " + process.stdout.decode())
            kubectl_output = json.loads(process.stdout.decode())
            pods = []
            
            for item in kubectl_output.get("items", []):
                metadata = item.get("metadata", {})
                status = item.get("status", {})
                
                pods.append({
                    "name": metadata.get("name"),
                    "namespace": metadata.get("namespace"),
                    "phase": status.get("phase"),
                    "created": metadata.get("creationTimestamp"),
                    "ready": self._count_ready_containers(status)
                })

                saved = ""
                if self.session:
                    saved = self.session.save_data(SessionDataType.INFO, "pods", json.dumps(pods, indent=2))
                    log_debug(f"KubernetesPlugin::list_kubernetes_pods:: Saved pod information to {saved}")
            
            return json.dumps({
                "pods": pods,
                "namespace": namespace,
                "selector": selector,
                "count": len(pods),
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to list pods: {str(e)}",
                "namespace": namespace,
                "selector": selector
            })
    
    @kernel_function(
        name="get_pod_status",
        description="Get detailed status information for a specific Kubernetes pod"
    )
    def get_pod_status(
        self,
        pod: Annotated[str, "The name of the pod to get status for"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
    ) -> Annotated[str, "JSON object with detailed pod status information"]:
        """Get status information for a Kubernetes pod.
        
        Args:
            pod: Pod name to get status for
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            JSON string with pod status including:
            - name, namespace, phase
            - conditions and container statuses
            - start time and IP address
        """
        log_debug(f"KubernetesPlugin::get_pod_status:: Getting status for pod '{pod}' in namespace '{namespace}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context]) 

        cmd.extend([
            "--namespace", namespace,
            "get", "pod", pod,
            "-o", "json"
        ])
        
        try:
            # Run kubectl command asynchronously
            log_debug(f"KubernetesPlugin::get_pod_status:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"kubectl get pod failed: {error_msg}",
                    "pod": pod,
                    "namespace": namespace
                })
            
            # Parse kubectl JSON output
            pod_info = json.loads(process.stdout.decode())
            metadata = pod_info.get("metadata", {})
            status = pod_info.get("status", {})
            spec = pod_info.get("spec", {})


            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"{pod}_status", json.dumps(pod_info, indent=2))
                log_debug(f"KubernetesPlugin::get_pod_status:: Saved pod information to {saved}")
            
            # Extract key status information
            result = {
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "phase": status.get("phase"),
                "pod_ip": status.get("podIP"),
                "host_ip": status.get("hostIP"),
                "node": spec.get("nodeName"),
                "start_time": status.get("startTime"),
                "conditions": status.get("conditions", []),
                "container_statuses": status.get("containerStatuses", []),
                "ready": self._count_ready_containers(status),
                "restarts": self._count_restarts(status),
                "timestamp": datetime.now().isoformat(),
                "saved": str(saved)
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get pod status: {str(e)}",
                "pod": pod,
                "namespace": namespace
            })
    
    def _count_ready_containers(self, status: Dict[str, Any]) -> str:
        """Count ready vs total containers in pod status.
        
        Args:
            status: Pod status dict from kubectl
            
        Returns:
            String like "2/3" indicating ready/total containers
        """
        container_statuses = status.get("containerStatuses", [])
        if not container_statuses:
            return "0/0"
        
        ready_count = sum(1 for cs in container_statuses if cs.get("ready", False))
        total_count = len(container_statuses)
        
        return f"{ready_count}/{total_count}"
    
    def _count_restarts(self, status: Dict[str, Any]) -> int:
        """Count total restarts across all containers in pod.
        
        Args:
            status: Pod status dict from kubectl
            
        Returns:
            Total restart count
        """
        container_statuses = status.get("containerStatuses", [])
        return sum(cs.get("restartCount", 0) for cs in container_statuses)
    
    @kernel_function(
        name="describe_pod",
        description="Get detailed description of a Kubernetes pod including events, conditions, and configuration"
    )
    def describe_pod(
        self,
        pod: Annotated[str, "The name of the pod to describe"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
    ) -> Annotated[str, "Detailed pod description including events and configuration"]:
        """Describe a Kubernetes pod with full details.
        
        This function runs 'kubectl describe pod' to get comprehensive information
        about a pod including events, conditions, volumes, and configuration.
        
        Args:
            pod: Pod name to describe
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            String containing the full kubectl describe output
        """
        log_debug(f"KubernetesPlugin::describe_pod:: Describing pod '{pod}' in namespace '{namespace}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "--namespace", namespace,
            "describe", "pod", pod
        ])
        
        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::describe_pod:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"kubectl describe pod failed: {error_msg}",
                    "pod": pod,
                    "namespace": namespace
                })
            
            # Return the describe output as-is (it's already human-readable)
            description = process.stdout.decode()

            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"{pod}_describe", description)
                log_debug(f"KubernetesPlugin::describe_pod:: Saved pod description to {saved}")
            
            return json.dumps({
                "description": description,
                "pod": pod,
                "namespace": namespace,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to describe pod: {str(e)}",
                "pod": pod,
                "namespace": namespace
            })
