
import json
import subprocess

from typing import Annotated, Optional, List
from pydantic import Field
from agent_framework import  ToolProtocol, ai_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin    
from datetime import datetime


class KubernetesPlugin(BasePlugin):
    """Semantic Kernel plugin for Kubernetes operations."""

    def __init__(self, config: Config, session: Session):
        self.session = session
        self.config = config
        self.name = "KubernetesPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("kubernetes_plugin")
        self.context = getattr(config, "kubernetes_context", None)
        self.namespace = getattr(config, "kubernetes_namespace", "default") or "default"

    def _run_kubectl(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
        """Helper to run kubectl commands and handle output, errors, and saving."""
        try:
            import subprocess
            log_debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True)
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": ' '.join(command) + f" failed: {error_msg}"
                })
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                log_debug(f"{log_prefix} Saved output to {saved}")
            return output
        except Exception as e:
            log_error(f"{log_prefix} Error launching kubectl: {str(e)}")
            return f"Error launching kubectl: {e}"

    
#    @ai_function(description="Fetch logs from a Kubernetes pod with optional filtering and limiting")
    def fetch_kubernetes_logs(
        self,
        pod: Annotated[str, "The name of the pod to fetch logs from"],
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
        container: Annotated[str, "Optional container name within the pod"] = None,
        tail_lines: Annotated[int, "Number of lines to fetch from the end of logs (default: 100)"] = 100,
        since_minutes: Annotated[str, "Fetch logs from the last N minutes (default: 30m)"] = "30",
        context: Annotated[str, "Kubernetes context to use (overrides default)"] = None,
    ) -> str:
        cmd = ["kubectl"]
        _context = context or self.context
        if _context:
            cmd.extend(["--context", _context])
        cmd.extend(["--namespace", namespace, "logs", pod, "--tail", str(tail_lines)])
        if container:
            cmd.extend(["--container", container])
        if since_minutes:
            cmd.extend(["--since", f"{since_minutes}m"])
        output = self._run_kubectl(cmd, save_key=f"{pod}_logs", log_prefix="KubernetesPlugin::fetch_kubernetes_logs::")
        try:
            log_lines = [line for line in output.split('\n') if line.strip()]
            return json.dumps({
                "logs": log_lines,
                "pod": pod,
                "namespace": namespace,
                "container": container,
                "count": len(log_lines),
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        except Exception:
            return output
    
#    @ai_function(name="list_kubernetes_pods", description="List all pods in a Kubernetes namespace, optionally filtered by label selector")
    def list_kubernetes_pods(
        self,
        namespace: Annotated[str, Field(description="The Kubernetes namespace to list pods from")] = "default",
        selector: Annotated[Optional[str], Field(description="Optional label selector (e.g., 'app=payments-svc')")] = None,
        context: Annotated[Optional[str], Field(description="Kubernetes context to use (overrides default)")] = None,
    ) -> str:
        cmd = ["kubectl"]
        _context = context or self.context
        if _context:
            cmd.extend(["--context", _context])
        cmd.extend(["--namespace", namespace, "get", "pods", "-o", "json"])
        if selector:
            cmd.extend(["-l", selector])
        try:
            output = self._run_kubectl(cmd, save_key="pods", log_prefix="KubernetesPlugin::list_kubernetes_pods::")
            kubectl_output = json.loads(output)
            pods = []
            for item in kubectl_output.get("items", []):
                metadata = item.get("metadata", {})
                status = item.get("status", {})
                pods.append({
                    "name": metadata.get("name"),
                    "namespace": metadata.get("namespace"),
                    "phase": status.get("phase"),
                    "created": metadata.get("creationTimestamp")
                })
            return json.dumps({
                "pods": pods,
                "namespace": namespace,
                "selector": selector,
                "count": len(pods),
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        except Exception:
            return output

#    @ai_function( name="get_nodes", description="Get the Kubernetes nodes list with status and resource information")
    def get_nodes(
        self,
        context: Annotated[str, "Kubernetes context to use (overrides default)"] = None,
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

        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="describe_node", description="Get detailed human-readable description of a specific Kubernetes node including events, conditions, and resource usage")
    def describe_node(
        self,
        node: Annotated[str, "The name of the node to describe"] = "",
        context: Annotated[str, "Kubernetes context to use (overrides default)"] = None,
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

        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="get_namespaces", description="Get the list of all Kubernetes namespaces with their status")
    def get_namespaces(
        self,
        context: Annotated[str, "Kubernetes context to use (overrides default)"] = None,
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
        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="describe_namespace", description="Get detailed human-readable description of a specific Kubernetes namespace including resource quotas and limit ranges")
    def describe_namespace(
        self,
        namespace: Annotated[str, "The name of the namespace to describe"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
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
        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="get_services", description="Get the list of Kubernetes services in a namespace or across all namespaces")
    def get_services(
        self,
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
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
        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="describe_service", description="Get detailed human-readable description of a specific Kubernetes service including endpoints")
    def describe_service(
        self,
        svc: Annotated[str, "The name of the service to describe"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
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
        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function(description="Get detailed status information for a specific Kubernetes pod")
    def get_pod_status(
        self,
        pod: Annotated[str, "The name of the pod to get status for"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"] = None,
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
    ) -> str:
        cmd = ["kubectl"]
        _context = context or self.context
        if _context:
            cmd.extend(["--context", _context])
        cmd.extend(["--namespace", namespace, "get", "pod", pod, "-o", "json"])
        output = self._run_kubectl(cmd, save_key=f"{pod}_status", log_prefix="KubernetesPlugin::get_pod_status::")
        try:
            pod_info = json.loads(output)
            metadata = pod_info.get("metadata", {})
            status = pod_info.get("status", {})
            spec = pod_info.get("spec", {})
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
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(result, indent=2)
        except Exception:
            return output
    
    
#    @ai_function( name="describe_pod", description="Get detailed description of a Kubernetes pod including events, conditions, and configuration")
    def describe_pod(
        self,
        pod: Annotated[str, "The name of the pod to describe"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
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

        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

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

#    @ai_function( name="thread_dump", description="Sends a SIGQUIT to all Java processes in a Kubernetes pod to generate thread dumps")
    def thread_dump(
        self,
        pod: Annotated[str, "The name of the pod"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
        container: Annotated[str, "The name of the container"] = "",
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default",
        pid: Annotated[str, "The PID of the Java process to dump"] = ""
    ) -> Annotated[str, "Detailed pod description including events and configuration"]:
        """Gets the thread dumps from all Java processes inside a container of a Kubernetes pod.

        This function runs 'kubectl exec <pod> -n <namespace> -- kill -QUIT <pid>' to get comprehensive information
        about the thread dumps from the specified container.

        Args:
            pod: Pod name to describe
            container: Container name (if multiple containers in pod)
            namespace: Kubernetes namespace (default: "default")
            pid: The PID of the Java process to dump
        
        Returns:
            n/A
        """
        log_debug(f"KubernetesPlugin::thread_dump:: Getting thread dumps for pod '{pod}'.'{container}'in namespace '{namespace}'")
        cmd = ["kubectl"]

        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

        cmd.extend([
            "--namespace", namespace,
            "exec", pod, "-n", namespace
        ])
        if container != "":
            cmd.extend(["-c", container])
        cmd.extend(["--", "kill", "-QUIT", pid])
        
        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::thread_dump:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"kubectl thread dump failed: {error_msg}",
                    "pod": pod,
                    "container": container,
                    "pid": pid,
                    "namespace": namespace
                })
            
            # Return the describe output as-is (it's already human-readable)
            description = process.stdout.decode()

            return json.dumps({
                "pod": pod,
                "pid": pid,
                "container": container,
                "namespace": namespace,
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get pod processes: {str(e)}",
                "pod": pod,
                "pid": pid,
                "container": container,
                "namespace": namespace
            })

#    @ai_function( name="ps", description="Lists all processes running in a Kubernetes pod")
    def ps(
        self,
        pod: Annotated[str, "The name of the pod"],
        context: Annotated[str, "Kubernetes context to use (overrides default)"],
        container: Annotated[str, "The name of the container"] = "",
        namespace: Annotated[str, "The Kubernetes namespace containing the pod"] = "default"
    ) -> Annotated[str, "Detailed process list from the pod"]:
        """Lists all processes running in a Kubernetes pod.

        This function runs 'kubectl exec <pod> -n <namespace> -- ps aux" to get comprehensive information
        about the processes from the specified container.

        Args:
            pod: Pod name to describe
            container: Container name (if multiple containers in pod)
            namespace: Kubernetes namespace (default: "default")
        
        Returns:
            n/A
        """
        log_debug(f"KubernetesPlugin::ps:: Getting process list for pod '{pod}'.'{container}'in namespace '{namespace}'")
        cmd = ["kubectl"]
        _context = self.context
        if context is not None and context.strip() != "":
            _context = context 
        if _context:
            cmd.extend(["--context", _context])

        cmd.extend([
            "--namespace", namespace,
            "exec", pod, "-n", namespace
        ])
        if container != "":
            cmd.extend(["-c", container])
        cmd.extend(["--", "ps", "aux"])
        
        try:
            # Run kubectl command
            log_debug(f"KubernetesPlugin::ps:: Running command: [{' '.join(cmd)}]")
            process = subprocess.run(args=cmd, capture_output=True)
            
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"kubectl thread dump failed: {error_msg}",
                    "pod": pod,
                    "container": container,
                    "namespace": namespace
                })
            
            # Return the describe output as-is (it's already human-readable)
            description = process.stdout.decode()
            saved = ""
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, f"{pod}_ps", description)
                log_debug(f"KubernetesPlugin::ps:: Saved pod process list to {saved}")


            return json.dumps({
                "process_list": description,
                "pod": pod,
                "container": container,
                "namespace": namespace,
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get pod processes: {str(e)}",
                "pod": pod,
                "container": container,
                "namespace": namespace
            })

    def get_tools(self) -> List[ToolProtocol]:
        return [
            self.fetch_kubernetes_logs,
            self.list_kubernetes_pods,
            self.get_nodes,
            self.describe_node,
            self.get_namespaces,
            self.describe_namespace,
            self.get_services,
            self.describe_service,
            self.get_pod_status,
            self.describe_pod,
            self.thread_dump,
            self.ps,
        ]

