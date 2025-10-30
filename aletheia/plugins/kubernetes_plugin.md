The Kubernetes Plugin can access the kubernetes cluster to perform the following operations:

   **Pod Operations:**
   - Use `kubernetes.fetch_kubernetes_logs()` to get logs from specific pods
   - Use `kubernetes.list_kubernetes_pods()` to discover pods if the name is not explicit
   - Use `kubernetes.get_pod_status()` to check pod health and detailed status
   - Use `kubernetes.describe_pod()` to get comprehensive pod information with events

   **Node Operations:**
   - Use `kubernetes.get_nodes()` to list all cluster nodes with status and resources
   - Use `kubernetes.describe_node()` to get detailed node information including events and resource usage

   **Namespace Operations:**
   - Use `kubernetes.get_namespaces()` to list all namespaces in the cluster
   - Use `kubernetes.describe_namespace()` to get detailed namespace information including resource quotas

   **Service Operations:**
   - Use `kubernetes.get_services()` to list services in a namespace (or all namespaces with namespace="all")
   - Use `kubernetes.describe_service()` to get detailed service information including endpoints
