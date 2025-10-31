The Kubernetes Plugin can access the kubernetes cluster to perform the following operations:

   **Pod Operations:**
   - Use `fetch_kubernetes_logs()` to get logs from specific pods
   - Use `list_kubernetes_pods()` to discover pods if the name is not explicit
   - Use `get_pod_status()` to check pod health and detailed status
   - Use `describe_pod()` to get comprehensive pod information with events

   **Node Operations:**
   - Use `get_nodes()` to list all cluster nodes with status and resources
   - Use `describe_node()` to get detailed node information including events and resource usage

   **Namespace Operations:**
   - Use `get_namespaces()` to list all namespaces in the cluster
   - Use `describe_namespace()` to get detailed namespace information including resource quotas

   **Service Operations:**
   - Use `get_services()` to list services in a namespace (or all namespaces with namespace="all")
   - Use `describe_service()` to get detailed service information including endpoints

   **Java Processes Operations:**
   - Use `ps()` to list processes in container in a pod
   - Use `thread_dump()` to send to the java process a SIGQUIT for a thread dump. 

