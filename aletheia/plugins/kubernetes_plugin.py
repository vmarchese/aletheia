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
        name="get_nodes",
        description="Get the Kubernetes nodes list with status and resource information"
    )
    def get_nodes(
        self,
    ) -> Annotated[str, "JSON object with nodes information including status and resources"]:
        """Get Kubernetes nodes.

        Returns:
            JSON string with nodes information including:
            - name, status, roles
            - conditions and capacity
            - kernel version and container runtime
        """
        log_debug("KubernetesPlugin::get_nodes:: Getting cluster nodes")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "get", "nodes",
            "-o", "json"
        ])

        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::get_nodes:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)

            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                log_error(f"KubernetesPlugin::get_nodes:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl get nodes failed: {error_msg}"
                })

            # Parse kubectl JSON output
            log_debug("KubernetesPlugin::get_nodes:: Parsing kubectl output")
            kubectl_output = json.loads(process.stdout.decode())
            nodes = []

            for item in kubectl_output.get("items", []):
                metadata = item.get("metadata", {})
                status = item.get("status", {})

                # Extract node roles from labels
                labels = metadata.get("labels", {})
                roles = []
                for label_key in labels.keys():
                    if label_key.startswith("node-role.kubernetes.io/"):
                        role = label_key.replace("node-role.kubernetes.io/", "")
                        roles.append(role)

                # Get node conditions
                conditions = status.get("conditions", [])
                ready_condition = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    {}
                )

                nodes.append({
                    "name": metadata.get("name"),
                    "roles": roles if roles else ["<none>"],
                    "status": ready_condition.get("status", "Unknown"),
                    "age": metadata.get("creationTimestamp"),
                    "version": status.get("nodeInfo", {}).get("kubeletVersion"),
                    "internal_ip": next(
                        (addr.get("address") for addr in status.get("addresses", [])
                         if addr.get("type") == "InternalIP"),
                        None
                    ),
                    "os_image": status.get("nodeInfo", {}).get("osImage"),
                    "kernel_version": status.get("nodeInfo", {}).get("kernelVersion"),
                    "container_runtime": status.get("nodeInfo", {}).get("containerRuntimeVersion"),
                    "capacity": status.get("capacity", {}),
                    "allocatable": status.get("allocatable", {}),
                    "conditions": conditions
                })

            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, "nodes", json.dumps(nodes, indent=2))
                log_debug(f"KubernetesPlugin::get_nodes:: Saved nodes information to {saved}")

            return json.dumps({
                "nodes": nodes,
                "count": len(nodes),
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::get_nodes:: Failed to get nodes: {str(e)}")
            return json.dumps({
                "error": f"Failed to get nodes: {str(e)}"
            })

    @kernel_function(
        name="describe_node",
        description="Get detailed human-readable description of a specific Kubernetes node including events, conditions, and resource usage"
    )
    def describe_node(
        self,
        node: Annotated[str, "The name of the node to describe"],
    ) -> Annotated[str, "Human-readable description of the node with events and detailed information"]:
        """Describe a Kubernetes node in detail.

        Args:
            node: Node name to describe

        Returns:
            Human-readable description string with:
            - Node information and labels
            - Conditions and addresses
            - Resource capacity and allocatable
            - Allocated resources and usage
            - Events related to the node
        """
        log_debug(f"KubernetesPlugin::describe_node:: Describing node '{node}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "describe", "node", node
        ])

        try:
            # Run kubectl describe command
            log_debug(f"KubernetesPlugin::describe_node:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True, text=True)

            if process.returncode != 0:
                error_msg = process.stderr.strip()
                log_error(f"KubernetesPlugin::describe_node:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl describe node failed: {error_msg}",
                    "node": node
                })

            # Get the describe output
            description = process.stdout

            # Save to session if available
            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"node_describe_{node}", description)
                log_debug(f"KubernetesPlugin::describe_node:: Saved node description to {saved}")

            return json.dumps({
                "node": node,
                "description": description,
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::describe_node:: Failed to describe node: {str(e)}")
            return json.dumps({
                "error": f"Failed to describe node: {str(e)}",
                "node": node
            })

    @kernel_function(
        name="get_namespaces",
        description="Get the list of all Kubernetes namespaces with their status"
    )
    def get_namespaces(
        self,
    ) -> Annotated[str, "JSON object with namespaces information including status and age"]:
        """Get Kubernetes namespaces.

        Returns:
            JSON string with namespaces information including:
            - name, status, age
            - labels and annotations
            - creation timestamp
        """
        log_debug("KubernetesPlugin::get_namespaces:: Getting cluster namespaces")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "get", "namespaces",
            "-o", "json"
        ])

        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::get_namespaces:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)

            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                log_error(f"KubernetesPlugin::get_namespaces:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl get namespaces failed: {error_msg}"
                })

            # Parse kubectl JSON output
            log_debug("KubernetesPlugin::get_namespaces:: Parsing kubectl output")
            kubectl_output = json.loads(process.stdout.decode())
            namespaces = []

            for item in kubectl_output.get("items", []):
                metadata = item.get("metadata", {})
                status = item.get("status", {})

                namespaces.append({
                    "name": metadata.get("name"),
                    "status": status.get("phase", "Unknown"),
                    "age": metadata.get("creationTimestamp"),
                    "labels": metadata.get("labels", {}),
                    "annotations": metadata.get("annotations", {})
                })

            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, "namespaces", json.dumps(namespaces, indent=2))
                log_debug(f"KubernetesPlugin::get_namespaces:: Saved namespaces information to {saved}")

            return json.dumps({
                "namespaces": namespaces,
                "count": len(namespaces),
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::get_namespaces:: Failed to get namespaces: {str(e)}")
            return json.dumps({
                "error": f"Failed to get namespaces: {str(e)}"
            })

    @kernel_function(
        name="describe_namespace",
        description="Get detailed human-readable description of a specific Kubernetes namespace including resource quotas and limit ranges"
    )
    def describe_namespace(
        self,
        namespace: Annotated[str, "The name of the namespace to describe"],
    ) -> Annotated[str, "Human-readable description of the namespace with resource quotas and limits"]:
        """Describe a Kubernetes namespace in detail.

        Args:
            namespace: Namespace name to describe

        Returns:
            Human-readable description string with:
            - Namespace information and labels
            - Status and conditions
            - Resource quotas
            - Limit ranges
            - Events related to the namespace
        """
        log_debug(f"KubernetesPlugin::describe_namespace:: Describing namespace '{namespace}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "describe", "namespace", namespace
        ])

        try:
            # Run kubectl describe command
            log_debug(f"KubernetesPlugin::describe_namespace:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True, text=True)

            if process.returncode != 0:
                error_msg = process.stderr.strip()
                log_error(f"KubernetesPlugin::describe_namespace:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl describe namespace failed: {error_msg}",
                    "namespace": namespace
                })

            # Get the describe output
            description = process.stdout

            # Save to session if available
            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"namespace_describe_{namespace}", description)
                log_debug(f"KubernetesPlugin::describe_namespace:: Saved namespace description to {saved}")

            return json.dumps({
                "namespace": namespace,
                "description": description,
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::describe_namespace:: Failed to describe namespace: {str(e)}")
            return json.dumps({
                "error": f"Failed to describe namespace: {str(e)}",
                "namespace": namespace
            })

    @kernel_function(
        name="get_services",
        description="Get the list of Kubernetes services in a namespace or across all namespaces"
    )
    def get_services(
        self,
        namespace: Annotated[str, "The Kubernetes namespace to list services from. Use 'all' for all namespaces"] = "default",
    ) -> Annotated[str, "JSON object with services information including type, cluster IP, and ports"]:
        """Get Kubernetes services.

        Args:
            namespace: Kubernetes namespace (default: "default"), use "all" for all namespaces

        Returns:
            JSON string with services information including:
            - name, namespace, type
            - cluster IP and external IPs
            - ports and selectors
            - age and creation timestamp
        """
        log_debug(f"KubernetesPlugin::get_services:: Getting services in namespace '{namespace}'")
        cmd = ["kubectl"]
        if self.context:
            cmd.extend(["--context", self.context])

        if namespace.lower() == "all":
            cmd.extend(["get", "services", "--all-namespaces", "-o", "json"])
        else:
            cmd.extend(["--namespace", namespace, "get", "services", "-o", "json"])

        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::get_services:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)

            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                log_error(f"KubernetesPlugin::get_services:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl get services failed: {error_msg}",
                    "namespace": namespace
                })

            # Parse kubectl JSON output
            log_debug("KubernetesPlugin::get_services:: Parsing kubectl output")
            kubectl_output = json.loads(process.stdout.decode())
            services = []

            for item in kubectl_output.get("items", []):
                metadata = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})

                services.append({
                    "name": metadata.get("name"),
                    "namespace": metadata.get("namespace"),
                    "type": spec.get("type", "ClusterIP"),
                    "cluster_ip": spec.get("clusterIP"),
                    "external_ips": spec.get("externalIPs", []),
                    "ports": spec.get("ports", []),
                    "selector": spec.get("selector", {}),
                    "age": metadata.get("creationTimestamp"),
                    "load_balancer": status.get("loadBalancer", {})
                })

            saved = ""
            if self.session:
                filename = f"services_{namespace}" if namespace != "all" else "services_all"
                saved = self.session.save_data(SessionDataType.INFO, filename, json.dumps(services, indent=2))
                log_debug(f"KubernetesPlugin::get_services:: Saved services information to {saved}")

            return json.dumps({
                "services": services,
                "count": len(services),
                "namespace": namespace,
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::get_services:: Failed to get services: {str(e)}")
            return json.dumps({
                "error": f"Failed to get services: {str(e)}",
                "namespace": namespace
            })

    @kernel_function(
        name="describe_service",
        description="Get detailed human-readable description of a specific Kubernetes service including endpoints"
    )
    def describe_service(
        self,
        svc: Annotated[str, "The name of the service to describe"],
        namespace: Annotated[str, "The Kubernetes namespace containing the service"] = "default",
    ) -> Annotated[str, "Human-readable description of the service with endpoints and events"]:
        """Describe a Kubernetes service in detail.

        Args:
            service: Service name to describe
            namespace: Kubernetes namespace (default: "default")

        Returns:
            Human-readable description string with:
            - Service information and labels
            - Type, cluster IP, and ports
            - Endpoints and pod selectors
            - Events related to the service
        """
        log_debug(f"KubernetesPlugin::describe_service:: Describing service '{svc}' in namespace '{namespace}'")
        cmd = ["kubectl"]
        print(cmd)
        if self.context:
            cmd.extend(["--context", self.context])

        cmd.extend([
            "--namespace", namespace,
            "describe", "service", svc
        ])

        try:
            # Run kubectl describe command
            log_debug(f"KubernetesPlugin::describe_service:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True, text=True)

            if process.returncode != 0:
                error_msg = process.stderr.strip()
                log_error(f"KubernetesPlugin::describe_service:: Command failed with return code {process.returncode}, error: {error_msg}")
                return json.dumps({
                    "error": f"kubectl describe service failed: {error_msg}",
                    "service": svc,
                    "namespace": namespace
                })

            # Get the describe output
            description = process.stdout

            # Save to session if available
            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"service_describe_{namespace}_{svc}", description)
                log_debug(f"KubernetesPlugin::describe_service:: Saved service description to {saved}")

            return json.dumps({
                "service": svc,
                "namespace": namespace,
                "description": description,
                "saved": str(saved),
                "timestamp": datetime.now().isoformat()
            }, indent=2)

        except Exception as e:
            log_error(f"KubernetesPlugin::describe_service:: Failed to describe service: {str(e)}")
            return json.dumps({
                "error": f"Failed to describe service: {str(e)}",
                "service": svc,
                "namespace": namespace
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
