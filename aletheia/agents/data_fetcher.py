"""Data Fetcher Agent for collecting observability data.

This agent is responsible for:
- Collecting logs, metrics, and traces from various data sources
- Constructing queries using templates or LLM-assisted generation
- Sampling data intelligently
- Generating summaries of collected data
- Writing results to the scratchpad's DATA_COLLECTED section

This is the SK-based version that uses Semantic Kernel's ChatCompletionAgent
with Kubernetes and Prometheus plugins for automatic function calling.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.fetchers.base import BaseFetcher, FetchResult, FetchError
from aletheia.fetchers.kubernetes import KubernetesFetcher
from aletheia.fetchers.prometheus import PrometheusFetcher
from aletheia.fetchers.summarization import LogSummarizer, MetricSummarizer
from aletheia.llm.prompts import compose_messages, get_user_prompt_template
from aletheia.plugins.kubernetes_plugin import KubernetesPlugin
from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.scratchpad import ScratchpadSection
from aletheia.utils.retry import retry_with_backoff
from aletheia.utils.validation import validate_time_window
from aletheia.utils.logging import log_info, log_error, log_prompt


class DataFetcherAgent(SKBaseAgent):
    """SK-based agent responsible for collecting observability data from various sources.
    
    This agent uses Semantic Kernel's ChatCompletionAgent with plugins for
    Kubernetes and Prometheus operations. The LLM can automatically invoke
    plugin functions via FunctionChoiceBehavior.Auto().
    
    The Data Fetcher Agent:
    1. Reads the PROBLEM_DESCRIPTION section to understand what data to collect
    2. Uses SK plugins (Kubernetes, Prometheus) for data collection
    3. Constructs queries using templates or LLM-assisted generation
    4. Fetches data with intelligent sampling via plugin functions
    5. Generates summaries of collected data
    6. Writes results to the DATA_COLLECTED section
    
    Attributes:
        config: Agent configuration including data source settings
        scratchpad: Scratchpad for reading problem and writing data
        fetchers: Dictionary of available data source fetchers (for direct access)
        _plugins_registered: Whether SK plugins have been registered
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any):
        """Initialize the SK-based Data Fetcher Agent.
        
        Args:
            config: Configuration dictionary with data_sources and llm sections
            scratchpad: Scratchpad instance for agent communication
        """
        super().__init__(config, scratchpad, agent_name="data_fetcher")
        
        # Initialize available fetchers (for direct access if needed)
        self.fetchers: Dict[str, BaseFetcher] = {}
        self._initialize_fetchers()
        
        # Track plugin registration
        self._plugins_registered = False
    
    def _initialize_fetchers(self) -> None:
        """Initialize data source fetchers from configuration."""
        data_sources_config = self.config.get("data_sources", {})
        
        # Initialize Kubernetes fetcher if configured
        if "kubernetes" in data_sources_config:
            k8s_config = data_sources_config["kubernetes"]
            if k8s_config.get("context"):
                self.fetchers["kubernetes"] = KubernetesFetcher(k8s_config)
        
        # Initialize Prometheus fetcher if configured
        if "prometheus" in data_sources_config:
            prom_config = data_sources_config["prometheus"]
            if prom_config.get("endpoint"):
                self.fetchers["prometheus"] = PrometheusFetcher(prom_config)
    
    def _register_plugins(self) -> None:
        """Register SK plugins with the kernel for automatic function calling.
        
        This registers Kubernetes and Prometheus plugins so the SK agent can
        automatically invoke their functions via FunctionChoiceBehavior.Auto().
        """
        if self._plugins_registered:
            return
        
        data_sources_config = self.config.get("data_sources", {})
        
        # Register Kubernetes plugin if configured
        if "kubernetes" in data_sources_config:
            k8s_config = data_sources_config["kubernetes"]
            if k8s_config.get("context"):
                k8s_plugin = KubernetesPlugin(k8s_config)
                self.kernel.add_plugin(k8s_plugin, plugin_name="kubernetes")
        
        # Register Prometheus plugin if configured
        if "prometheus" in data_sources_config:
            prom_config = data_sources_config["prometheus"]
            if prom_config.get("endpoint"):
                prom_plugin = PrometheusPlugin(prom_config)
                self.kernel.add_plugin(prom_plugin, plugin_name="prometheus")
        
        self._plugins_registered = True
    
    async def execute(
        self,
        sources: Optional[List[str]] = None,
        time_window: Optional[str] = None,
        use_sk: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the data fetching process.
        
        This method can operate in two modes:
        1. SK mode (default): Uses SK agent with automatic function calling via plugins
        2. Direct mode: Directly calls fetchers (maintains backward compatibility)
        
        Args:
            sources: List of data source names to fetch from (e.g., ["kubernetes", "prometheus"])
                    If None, attempts to determine from problem description
            time_window: Time window string (e.g., "2h", "30m")
                        If None, uses session default or problem description
            use_sk: If True, uses SK agent with plugins. If False, uses direct fetcher calls.
            **kwargs: Additional parameters for specific data sources
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - sources_fetched: List[str] - Successfully fetched sources
                - sources_failed: List[str] - Failed sources
                - total_data_points: int - Total data points collected
                - summaries: Dict[str, str] - Summaries by source
                - sk_used: bool - Whether SK mode was used
        
        Raises:
            ValueError: If no data sources are available or specified
        """
        # Read problem description from scratchpad
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        # Log problem data for debugging
        log_info(f"Data Fetcher - Problem description: {problem}")
        log_info(f"Data Fetcher - Sources requested: {sources}")
        
        # Determine which sources to fetch from
        sources_to_fetch = self._determine_sources(sources, problem)
        log_info(f"Data Fetcher - Sources determined: {sources_to_fetch}")
        if not sources_to_fetch:
            log_error("No data sources specified or available")
            raise ValueError("No data sources specified or available")
        
        # Parse time window
        time_range = self._parse_time_window(time_window, problem)
        
        # Choose execution mode
        if use_sk:
            return await self._execute_with_sk(sources_to_fetch, time_range, problem, **kwargs)
        else:
            return self._execute_direct(sources_to_fetch, time_range, problem, **kwargs)
    
    async def _execute_with_sk(
        self,
        sources: List[str],
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute data fetching using SK agent with automatic plugin invocation.
        
        This method uses the SK ChatCompletionAgent which can automatically
        call plugin functions (fetch_kubernetes_logs, fetch_prometheus_metrics, etc.)
        based on the user's request.
        
        In conversational mode, it reads conversation history from scratchpad and
        delegates ALL parameter extraction to the LLM.
        
        Args:
            sources: List of data sources to fetch from
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters (may include conversation_history)
        
        Returns:
            Dictionary with execution results
        """
        # Register plugins with kernel
        self._register_plugins()
        
        # Read conversation history from scratchpad if not provided
        if "conversation_history" not in kwargs:
            conversation_history = self.read_scratchpad(ScratchpadSection.CONVERSATION_HISTORY)
            if conversation_history:
                kwargs["conversation_history"] = conversation_history
        
        # Build prompt for SK agent (includes conversation history if available)
        prompt = self._build_sk_prompt(sources, time_range, problem, **kwargs)
        
        # Log the prompt for debugging
        log_prompt("data_fetcher", prompt, self._model if hasattr(self, '_model') else "unknown")
        
        # Invoke SK agent - it will automatically call plugin functions
        try:
            response = await self.invoke_async(prompt, settings={"temperature": 0.1})
            
            # Parse the response to extract collected data
            # The SK agent should have called the plugin functions and received results
            collected_data = self._parse_sk_response(response, sources)
            
            # Build results summary
            results = {
                "success": True,
                "sources_fetched": list(collected_data.keys()),
                "sources_failed": [],
                "total_data_points": sum(d.get("count", 0) for d in collected_data.values()),
                "summaries": {s: d.get("summary", "") for s, d in collected_data.items()},
                "sk_used": True,
            }
            
            # Write collected data to scratchpad
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, collected_data)
            
            return results
            
        except Exception as e:
            # Log the SK error for debugging
            log_error(f"SK agent execution failed: {str(e)}")
            # If SK fails, fall back to direct mode
            return self._execute_direct(sources, time_range, problem, **kwargs)
    
    def _execute_direct(
        self,
        sources: List[str],
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute data fetching using direct fetcher calls (backward compatibility).
        
        This method directly calls the fetcher implementations without SK.
        
        Args:
            sources: List of data sources to fetch from
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters
        
        Returns:
            Dictionary with execution results
        """
        # Fetch data from each source
        results = {
            "success": True,
            "sources_fetched": [],
            "sources_failed": [],
            "total_data_points": 0,
            "summaries": {},
            "sk_used": False,
        }
        
        collected_data = {}
        
        for source in sources:
            try:
                # Fetch data from source
                fetch_result = self._fetch_from_source(
                    source=source,
                    time_range=time_range,
                    problem=problem,
                    **kwargs
                )
                
                # Generate summary
                summary = self._summarize_data(source, fetch_result)
                
                # Store results
                collected_data[source] = {
                    "source": source,
                    "count": fetch_result.count,
                    "time_range": f"{fetch_result.time_range[0].isoformat()} - {fetch_result.time_range[1].isoformat()}",
                    "summary": summary,
                    "metadata": fetch_result.metadata,
                }
                
                results["sources_fetched"].append(source)
                results["total_data_points"] += fetch_result.count
                results["summaries"][source] = summary
                
            except FetchError as e:
                # Handle fetch failures
                results["sources_failed"].append(source)
                results["success"] = False
                collected_data[source] = {
                    "source": source,
                    "error": str(e),
                    "status": "failed",
                }
        
        # Write collected data to scratchpad
        self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, collected_data)
        
        return results
    
    def _build_sk_prompt(
        self,
        sources: List[str],
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> str:
        """Build a prompt for the SK agent to collect data.
        
        This method supports both guided and conversational modes:
        - Guided mode: Uses structured parameters
        - Conversational mode: Includes conversation history for LLM to extract parameters
        
        Args:
            sources: Data sources to use
            time_range: Time range for data collection
            problem: Problem description
            **kwargs: Additional parameters (may include conversation_history)
        
        Returns:
            Prompt string for SK agent
        """
        # Check if this is conversational mode (has conversation history)
        conversation_history = kwargs.get("conversation_history", [])
        use_conversational = bool(conversation_history)
        
        if use_conversational:
            # Use conversational template with LLM-delegated parameter extraction
            from aletheia.llm.prompts import get_user_prompt_template
            
            template = get_user_prompt_template("data_fetcher_conversational")
            
            # Format problem description
            description = problem.get("description", "No description provided")
            affected_services = problem.get("affected_services", [])
            if affected_services:
                description += f"\nAffected services: {', '.join(affected_services)}"
            
            # Add pod/namespace info if available
            if problem.get("pod"):
                description += f"\nPod: {problem['pod']}"
            if problem.get("namespace"):
                description += f"\nNamespace: {problem['namespace']}"
            if problem.get("container"):
                description += f"\nContainer: {problem['container']}"
            
            # Format conversation history
            if isinstance(conversation_history, list):
                # List of message dicts
                conv_text = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])
            else:
                # Already formatted string
                conv_text = str(conversation_history)
            
            # Format data sources
            data_sources_text = "\n".join([
                f"- {source.upper()}: Available via {source} plugin"
                for source in sources
            ])
            
            prompt = template.format(
                problem_description=description,
                conversation_history=conv_text if conv_text else "No prior conversation",
                data_sources=data_sources_text
            )
            
            return prompt
        
        # Guided mode: Simple prompt that relies on system instructions
        start_time = time_range[0].isoformat()
        end_time = time_range[1].isoformat()
        
        affected_services = problem.get("affected_services", [])
        description = problem.get("description", "")
        user_input = problem.get("user_input", {})  # Additional context from user interactions
        
        # Build a simple, direct prompt
        prompt = f"""Collect observability data for this issue:

{description}"""
        
        # Add affected services if available
        if affected_services:
            prompt += f"\nAffected services: {', '.join(affected_services)}"
        
        # Add user-provided context if available
        if user_input:
            prompt += "\n\nAdditional context:"
            for key, value in user_input.items():
                prompt += f"\n- {key}: {value}"
        
        # Add explicit parameters if provided
        explicit_params = []
        if kwargs.get("pod"):
            explicit_params.append(f"Pod: {kwargs['pod']}")
        if kwargs.get("namespace"):
            explicit_params.append(f"Namespace: {kwargs['namespace']}")
        if kwargs.get("container"):
            explicit_params.append(f"Container: {kwargs['container']}")
        if kwargs.get("query"):
            explicit_params.append(f"Prometheus query: {kwargs['query']}")
        if kwargs.get("template"):
            explicit_params.append(f"Prometheus template: {kwargs['template']}")
        
        if explicit_params:
            prompt += "\n\nExplicit parameters:\n- " + "\n- ".join(explicit_params)
        
        # Add time window and sources
        prompt += f"""

Time window: {start_time} to {end_time}
Available data sources: {', '.join(sources)}

Task:
1. Determine which data sources are relevant for this specific issue
2. Use the appropriate plugin functions to collect data (only call functions for relevant sources)
3. Extract parameters (pod names, namespaces, services, metrics) from the description

For example:
- For Kubernetes issues: use kubernetes.fetch_kubernetes_logs(), kubernetes.list_kubernetes_pods(), etc.
- For metrics/performance issues: use prometheus.fetch_prometheus_metrics()
- You don't need to use ALL available sources - only the ones relevant to this issue

Return your results as JSON:
{{
    "<source>": {{
        "count": <number of data points>,
        "summary": "<brief summary>",
        "metadata": {{<relevant metadata>}}
    }}
}}
"""
        
        return prompt
    
    def _parse_sk_response(
        self,
        response: str,
        sources: List[str]
    ) -> Dict[str, Any]:
        """Parse the SK agent's response to extract collected data.
        
        Args:
            response: SK agent's response string
            sources: Expected data sources
        
        Returns:
            Dictionary mapping source names to collected data
        """
        # Try to parse as JSON
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                return data
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # If JSON parsing fails, create minimal structure
        collected_data = {}
        for source in sources:
            collected_data[source] = {
                "source": source,
                "count": 0,
                "summary": "SK agent execution completed but data format unexpected",
                "metadata": {"raw_response": response[:500]},  # First 500 chars
            }
        
        return collected_data
    
    def _determine_sources(
        self,
        sources: Optional[List[str]],
        problem: Dict[str, Any]
    ) -> List[str]:
        """Determine which data sources to fetch from.
        
        Args:
            sources: User-specified sources
            problem: Problem description from scratchpad
        
        Returns:
            List of data source names to fetch from
        """
        if sources:
            # Validate requested sources are available
            available = []
            for source in sources:
                if source in self.fetchers:
                    available.append(source)
            return available
        
        # If no sources specified, use all available fetchers
        return list(self.fetchers.keys())
    
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
    def _fetch_from_source(
        self,
        source: str,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> FetchResult:
        """Fetch data from a specific source with retry logic.
        
        Args:
            source: Data source name
            time_range: Tuple of (start_time, end_time)
            problem: Problem description for context
            **kwargs: Source-specific parameters
        
        Returns:
            FetchResult containing the fetched data
        
        Raises:
            FetchError: If fetching fails after retries
        """
        fetcher = self.fetchers.get(source)
        if not fetcher:
            raise ValueError(f"Unknown data source: {source}")
        
        # Fetch data with source-specific parameters
        if source == "kubernetes":
            return self._fetch_kubernetes(fetcher, time_range, problem, **kwargs)
        elif source == "prometheus":
            return self._fetch_prometheus(fetcher, time_range, problem, **kwargs)
        else:
            # Generic fetch
            return fetcher.fetch(time_window=time_range, **kwargs)
    
    def _fetch_kubernetes(
        self,
        fetcher: KubernetesFetcher,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> FetchResult:
        """Fetch logs from Kubernetes.
        
        Args:
            fetcher: Kubernetes fetcher instance
            time_range: Time range for logs
            problem: Problem description
            **kwargs: Additional parameters (pod, namespace, etc.)
        
        Returns:
            FetchResult with Kubernetes logs
        """
        # Extract parameters from kwargs or fall back to config/defaults
        # The LLM will infer the actual values from the problem description
        pod = kwargs.get("pod")
        namespace = kwargs.get("namespace") or fetcher.config.get("namespace", "default")
        container = kwargs.get("container")
        
        # Get sample size from config
        sample_size = self.config.get("sampling", {}).get("logs", {}).get(
            "default_sample_size", 200
        )
        
        # Get priority levels from config
        priority_levels = self.config.get("sampling", {}).get("logs", {}).get(
            "always_include_levels", ["ERROR", "FATAL", "CRITICAL"]
        )
        
        # If no pod specified, try to get from problem description
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
    
    def _fetch_prometheus(
        self,
        fetcher: PrometheusFetcher,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> FetchResult:
        """Fetch metrics from Prometheus.
        
        Args:
            fetcher: Prometheus fetcher instance
            time_range: Time range for metrics
            problem: Problem description
            **kwargs: Additional parameters (query, template, etc.)
        
        Returns:
            FetchResult with Prometheus metrics
        """
        # Check if query or template is provided
        query = kwargs.get("query")
        template = kwargs.get("template")
        template_params = kwargs.get("template_params", {})
        
        # If no query/template, try to generate one
        if not query and not template:
            # Get affected services from problem
            affected_services = problem.get("affected_services", [])
            if affected_services:
                # Use error_rate template for first service
                template = "error_rate"
                template_params = {
                    "metric_name": "http_requests_total",
                    "service": affected_services[0],
                    "window": "5m",
                }
        
        # Get step from config or calculate adaptively
        step = kwargs.get("step")
        
        return fetcher.fetch(
            query=query,
            template=template,
            template_params=template_params,
            time_window=time_range,
            step=step,
        )
    
    def _summarize_data(self, source: str, fetch_result: FetchResult) -> str:
        """Generate a summary of fetched data.
        
        Args:
            source: Data source name
            fetch_result: Result from fetching
        
        Returns:
            Human-readable summary string
        """
        if source == "kubernetes":
            # Use log summarizer
            summarizer = LogSummarizer()
            summary_dict = summarizer.summarize(fetch_result.data)
            return summary_dict.get("summary", "No summary available")
        elif source == "prometheus":
            # Use metric summarizer
            summarizer = MetricSummarizer()
            summary_dict = summarizer.summarize(fetch_result.data)
            return summary_dict.get("summary", "No summary available")
        else:
            # Generic summary
            return fetch_result.summary
    
    def generate_query(
        self,
        source: str,
        intent: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a query for a data source using LLM assistance.
        
        This method uses the LLM to construct complex queries when templates
        are insufficient.
        
        Args:
            source: Data source name (e.g., "prometheus", "elasticsearch")
            intent: User's intent in natural language
            context: Optional context for query generation
        
        Returns:
            Generated query string
        
        Raises:
            ValueError: If source is not supported
        """
        # Get prompt template
        template = get_user_prompt_template("data_fetcher_query_generation")
        
        # Prepare context
        context = context or {}
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        
        # Format prompt
        prompt = template.format(
            source=source,
            intent=intent,
            context=context_str if context_str else "None"
        )
        
        # Get LLM completion
        llm = self.get_llm()
        messages = compose_messages(
            agent="data_fetcher",
            user_prompt=prompt
        )
        
        response = llm.complete(messages=messages, temperature=0.0)
        
        return response.content.strip()
    
    def validate_query(self, source: str, query: str) -> bool:
        """Validate a generated query.
        
        Args:
            source: Data source name
            query: Query string to validate
        
        Returns:
            True if query is valid, False otherwise
        """
        # For MVP, we rely on the data source to validate
        # More sophisticated validation can be added later
        return bool(query and query.strip())
