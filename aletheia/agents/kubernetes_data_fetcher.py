"""Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information.

This specialized agent is responsible for:
- Collecting logs from Kubernetes pods
- Listing pods and their statuses
- Extracting pod/namespace information from problem descriptions
- Using KubernetesPlugin for SK-based automatic function calling
- Writing results to the scratchpad's DATA_COLLECTED section

This agent focuses exclusively on Kubernetes data sources, providing better
separation of concerns and easier maintenance compared to the generic DataFetcherAgent.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.fetchers.base import BaseFetcher, FetchResult, FetchError
from aletheia.fetchers.kubernetes import KubernetesFetcher
from aletheia.fetchers.summarization import LogSummarizer
from aletheia.llm.prompts import get_user_prompt_template
from aletheia.plugins.kubernetes_plugin import KubernetesPlugin
from aletheia.scratchpad import ScratchpadSection
from aletheia.utils.retry import retry_with_backoff
from aletheia.utils.validation import validate_time_window
from aletheia.utils.logging import log_info, log_error, log_prompt


class KubernetesDataFetcher(SKBaseAgent):
    """SK-based agent specialized for collecting Kubernetes observability data.
    
    This agent uses Semantic Kernel's ChatCompletionAgent with KubernetesPlugin
    for automatic function calling via FunctionChoiceBehavior.Auto().
    
    The Kubernetes Data Fetcher Agent:
    1. Reads the PROBLEM_DESCRIPTION section to understand what K8s data to collect
    2. Uses SK KubernetesPlugin for data collection (logs, pod status, etc.)
    3. Extracts pod names and namespaces from problem description
    4. Fetches data with intelligent sampling
    5. Generates summaries of collected logs
    6. Writes results to the DATA_COLLECTED section under "kubernetes" key
    
    Attributes:
        config: Agent configuration including kubernetes data source settings
        scratchpad: Scratchpad for reading problem and writing data
        fetcher: Direct KubernetesFetcher instance (for fallback)
        _plugin_registered: Whether SK plugin has been registered
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any):
        """Initialize the SK-based Kubernetes Data Fetcher Agent.
        
        Args:
            config: Configuration dictionary with data_sources.kubernetes and llm sections
            scratchpad: Scratchpad instance for agent communication
        """
        super().__init__(config, scratchpad, agent_name="kubernetes_data_fetcher")
        
        # Initialize Kubernetes fetcher (for direct access if needed)
        self.fetcher: Optional[KubernetesFetcher] = None
        self._initialize_fetcher()
        
        # Track plugin registration
        self._plugin_registered = False
    
    def _initialize_fetcher(self) -> None:
        """Initialize Kubernetes fetcher from configuration."""
        data_sources_config = self.config.get("data_sources", {})
        
        if "kubernetes" in data_sources_config:
            k8s_config = data_sources_config["kubernetes"]
            if k8s_config.get("context"):
                self.fetcher = KubernetesFetcher(k8s_config)
    
    def _register_plugin(self) -> None:
        """Register Kubernetes SK plugin with the kernel for automatic function calling.
        
        This registers the KubernetesPlugin so the SK agent can automatically
        invoke its functions via FunctionChoiceBehavior.Auto().
        """
        if self._plugin_registered:
            return
        
        data_sources_config = self.config.get("data_sources", {})
        
        if "kubernetes" in data_sources_config:
            k8s_config = data_sources_config["kubernetes"]
            if k8s_config.get("context"):
                k8s_plugin = KubernetesPlugin(k8s_config)
                self.kernel.add_plugin(k8s_plugin, plugin_name="kubernetes")
                self._plugin_registered = True
    
    async def execute(
        self,
        time_window: Optional[str] = None,
        use_sk: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the Kubernetes data fetching process.
        
        This method can operate in two modes:
        1. SK mode (default): Uses SK agent with automatic function calling via KubernetesPlugin
        2. Direct mode: Directly calls KubernetesFetcher (maintains backward compatibility)
        
        Args:
            time_window: Time window string (e.g., "2h", "30m")
                        If None, uses session default or problem description
            use_sk: If True, uses SK agent with plugin. If False, uses direct fetcher calls.
            **kwargs: Additional parameters (pod, namespace, container, conversation_history, etc.)
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - source: str - Always "kubernetes"
                - count: int - Number of log lines collected
                - summary: str - Summary of collected logs
                - sk_used: bool - Whether SK mode was used
        
        Raises:
            ValueError: If Kubernetes is not configured
        """
        if not self.fetcher and not self._plugin_registered:
            raise ValueError("Kubernetes data source is not configured")
        
        # Read problem description from scratchpad
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        # Log problem data for debugging
        log_info(f"Kubernetes Data Fetcher - Problem description: {problem}")
        
        # Parse time window
        time_range = self._parse_time_window(time_window, problem)
        
        # Choose execution mode
        if use_sk:
            return await self._execute_with_sk(time_range, problem, **kwargs)
        else:
            return self._execute_direct(time_range, problem, **kwargs)
    
    async def _execute_with_sk(
        self,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Kubernetes data fetching using SK agent with automatic plugin invocation.
        
        This method uses the SK ChatCompletionAgent which can automatically
        call KubernetesPlugin functions (fetch_kubernetes_logs, list_kubernetes_pods, etc.)
        based on the user's request.
        
        In conversational mode, it reads conversation history from scratchpad and
        delegates ALL parameter extraction to the LLM.
        
        Args:
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters (may include conversation_history, pod, namespace, etc.)
        
        Returns:
            Dictionary with execution results
        """
        # Register plugin with kernel
        self._register_plugin()
        
        # Read conversation history from scratchpad if not provided
        if "conversation_history" not in kwargs:
            conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY)
            if conversation_history:
                kwargs["conversation_history"] = conversation_history
        
        # Build prompt for SK agent (includes conversation history if available)
        prompt = self._build_sk_prompt(time_range, problem, **kwargs)
        
        # Log the prompt for debugging
        log_prompt("kubernetes_data_fetcher", prompt, self._model if hasattr(self, '_model') else "unknown")
        
        # Invoke SK agent - it will automatically call plugin functions
        try:
            response = await self.invoke_async(prompt, settings={"temperature": 0.1})
            
            # Parse the response to extract collected data
            collected_data = self._parse_sk_response(response)
            
            # Build results summary
            results = {
                "success": True,
                "source": "kubernetes",
                "count": collected_data.get("count", 0),
                "summary": collected_data.get("summary", ""),
                "sk_used": True,
            }
            
            # Write collected data to scratchpad under "kubernetes" key
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["kubernetes"] = collected_data
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, existing_data)
            
            return results
            
        except Exception as e:
            # Log the SK error for debugging
            log_error(f"SK agent execution failed: {str(e)}")
            # If SK fails, fall back to direct mode
            return self._execute_direct(time_range, problem, **kwargs)
    
    def _execute_direct(
        self,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute Kubernetes data fetching using direct fetcher calls (backward compatibility).
        
        This method directly calls the KubernetesFetcher implementation without SK.
        
        Args:
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters (pod, namespace, container, etc.)
        
        Returns:
            Dictionary with execution results
        """
        if not self.fetcher:
            raise ValueError("Kubernetes fetcher not available")
        
        try:
            # Fetch Kubernetes logs
            fetch_result = self._fetch_kubernetes(
                self.fetcher,
                time_range,
                problem,
                **kwargs
            )
            
            # Generate summary
            summary = self._summarize_logs(fetch_result)
            
            # Store results
            collected_data = {
                "source": "kubernetes",
                "count": fetch_result.count,
                "time_range": f"{fetch_result.time_range[0].isoformat()} - {fetch_result.time_range[1].isoformat()}",
                "summary": summary,
                "metadata": fetch_result.metadata,
            }
            
            # Write to scratchpad
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["kubernetes"] = collected_data
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, existing_data)
            
            results = {
                "success": True,
                "source": "kubernetes",
                "count": fetch_result.count,
                "summary": summary,
                "sk_used": False,
            }
            
            return results
            
        except FetchError as e:
            # Handle fetch failure
            log_error(f"Kubernetes fetch failed: {str(e)}")
            
            collected_data = {
                "source": "kubernetes",
                "error": str(e),
                "status": "failed",
            }
            
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["kubernetes"] = collected_data
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, existing_data)
            
            return {
                "success": False,
                "source": "kubernetes",
                "error": str(e),
                "sk_used": False,
            }
    
    def _build_sk_prompt(
        self,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> str:
        """Build a prompt for the SK agent to collect Kubernetes data.
        
        This method uses conversational mode with conversation history
        for the LLM to extract parameters naturally.
        
        Args:
            time_range: Time range for data collection
            problem: Problem description
            **kwargs: Additional parameters (may include conversation_history, pod, namespace, etc.)
        
        Returns:
            Prompt string for SK agent
        """
        # Check if this is conversational mode (has conversation history)
        conversation_history = kwargs.get("conversation_history", [])
        use_conversational = bool(conversation_history)
        
        if use_conversational:
            # Use conversational template with LLM-delegated parameter extraction
            template = get_user_prompt_template("kubernetes_data_fetcher_conversational")
            
            # Format problem description
            description = problem.get("description", "No description provided")
            affected_services = problem.get("affected_services", [])
            if affected_services:
                description += f"\nAffected services: {', '.join(affected_services)}"
            
            # Add pod/namespace info if available in problem
            if problem.get("pod"):
                description += f"\nPod: {problem['pod']}"
            if problem.get("namespace"):
                description += f"\nNamespace: {problem['namespace']}"
            if problem.get("container"):
                description += f"\nContainer: {problem['container']}"
            
            # Format conversation history
            if isinstance(conversation_history, list):
                conv_text = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
            else:
                conv_text = str(conversation_history)
            
            prompt = template.format(
                problem_description=description,
                conversation_history=conv_text if conv_text else "No prior conversation"
            )
            
            return prompt
        
        # Guided mode: Simple prompt that relies on system instructions
        start_time = time_range[0].isoformat()
        end_time = time_range[1].isoformat()
        
        affected_services = problem.get("affected_services", [])
        description = problem.get("description", "")
        
        # Build a simple, direct prompt
        prompt = f"""Collect Kubernetes logs for this issue:

{description}"""
        
        # Add affected services if available
        if affected_services:
            prompt += f"\nAffected services: {', '.join(affected_services)}"
        
        # Add explicit parameters if provided
        explicit_params = []
        if kwargs.get("pod"):
            explicit_params.append(f"Pod: {kwargs['pod']}")
        if kwargs.get("namespace"):
            explicit_params.append(f"Namespace: {kwargs['namespace']}")
        if kwargs.get("container"):
            explicit_params.append(f"Container: {kwargs['container']}")
        
        if explicit_params:
            prompt += "\n\nExplicit parameters:\n- " + "\n- ".join(explicit_params)
        
        # Add time window
        prompt += f"""

Time window: {start_time} to {end_time}

Task:
1. Extract Kubernetes parameters (pod names, namespaces, containers) from the description above
2. Use kubernetes.fetch_kubernetes_logs() to collect logs
3. If pod name is not explicit, use kubernetes.list_kubernetes_pods() to discover pods
4. Focus on ERROR and FATAL level logs

Return your results as JSON:
{{
    "count": <number of log lines>,
    "summary": "<brief summary of findings>",
    "metadata": {{<relevant metadata>}}
}}
"""
        
        return prompt
    
    def _parse_sk_response(self, response: str) -> Dict[str, Any]:
        """Parse the SK agent's response to extract collected Kubernetes data.
        
        Args:
            response: SK agent's response string
        
        Returns:
            Dictionary with Kubernetes data (count, summary, metadata)
        """
        # Try to parse as JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                return {
                    "source": "kubernetes",
                    "count": data.get("count", 0),
                    "summary": data.get("summary", ""),
                    "metadata": data.get("metadata", {}),
                }
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # If JSON parsing fails, create minimal structure
        return {
            "source": "kubernetes",
            "count": 0,
            "summary": "SK agent execution completed but data format unexpected",
            "metadata": {"raw_response": response[:500]},
        }
    
    def _parse_time_window(
        self,
        time_window: Optional[str],
        problem: Dict[str, Any]
    ) -> Tuple[datetime, datetime]:
        """Parse time window into start and end datetime.
        
        Args:
            time_window: Time window string (e.g., "2h")
            problem: Problem description which may contain time_window
        
        Returns:
            Tuple of (start_time, end_time)
        """
        # Get time window from parameter, problem, or default
        window_str = (
            time_window
            or problem.get("time_window")
            or self.config.get("session", {}).get("default_time_window", "2h")
        )
        
        # Parse time window
        delta = validate_time_window(window_str)
        end_time = datetime.now()
        start_time = end_time - delta
        
        return (start_time, end_time)
    
    @retry_with_backoff(retries=3, delays=(1, 2, 4))
    def _fetch_kubernetes(
        self,
        fetcher: KubernetesFetcher,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> FetchResult:
        """Fetch logs from Kubernetes with retry logic.
        
        Args:
            fetcher: Kubernetes fetcher instance
            time_range: Time range for logs
            problem: Problem description
            **kwargs: Additional parameters (pod, namespace, container, etc.)
        
        Returns:
            FetchResult with Kubernetes logs
        """
        # Extract parameters from kwargs or problem description
        pod = kwargs.get("pod") or self._extract_pod_from_problem(problem)
        namespace = kwargs.get("namespace") or self._extract_namespace_from_problem(problem) or fetcher.config.get("namespace", "default")
        container = kwargs.get("container")
        
        # Get sample size from config
        sample_size = self.config.get("sampling", {}).get("logs", {}).get(
            "default_sample_size", 200
        )
        
        # Get priority levels from config
        priority_levels = self.config.get("sampling", {}).get("logs", {}).get(
            "always_include_levels", ["ERROR", "FATAL", "CRITICAL"]
        )
        
        # If no pod specified, try to get from affected services
        if not pod:
            affected_services = problem.get("affected_services", [])
            if affected_services:
                # List pods for the first affected service
                pods = fetcher.list_pods(
                    namespace=namespace,
                    selector=f"app={affected_services[0]}"
                )
                if pods:
                    pod = pods[0]
        
        # Fetch logs
        return fetcher.fetch(
            pod=pod,
            namespace=namespace,
            container=container,
            time_window=time_range,
            sample_size=sample_size,
            always_include_levels=priority_levels,
        )
    
    def _extract_pod_from_problem(self, problem: Dict[str, Any]) -> Optional[str]:
        """Extract pod name from problem description.
        
        Looks for patterns like "pod:name" or "pod name" in the description.
        
        Args:
            problem: Problem description dictionary
        
        Returns:
            Pod name if found, None otherwise
        """
        # Check explicit pod field first
        if problem.get("pod"):
            return problem["pod"]
        
        # Try to extract from description
        description = problem.get("description", "")
        
        # Pattern: "pod: <name>" or "pod <name>"
        match = re.search(r'pod[:\s]+([a-z0-9-]+)', description, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_namespace_from_problem(self, problem: Dict[str, Any]) -> Optional[str]:
        """Extract namespace from problem description.
        
        Looks for patterns like "namespace:name" or "namespace name" in the description.
        
        Args:
            problem: Problem description dictionary
        
        Returns:
            Namespace if found, None otherwise
        """
        # Check explicit namespace field first
        if problem.get("namespace"):
            return problem["namespace"]
        
        # Try to extract from description
        description = problem.get("description", "")
        
        # Pattern: "namespace: <name>" or "namespace <name>"
        match = re.search(r'namespace[:\s]+([a-z0-9-]+)', description, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _summarize_logs(self, fetch_result: FetchResult) -> str:
        """Generate a summary of fetched Kubernetes logs.
        
        Args:
            fetch_result: Result from fetching
        
        Returns:
            Human-readable summary string
        """
        summarizer = LogSummarizer()
        summary_dict = summarizer.summarize(fetch_result.data)
        return summary_dict.get("summary", "No summary available")
