"""Prometheus Data Fetcher Agent for collecting Prometheus metrics.

This specialized agent is responsible for:
- Collecting metrics from Prometheus
- Executing PromQL queries
- Using query templates for common patterns
- Using PrometheusPlugin for SK-based automatic function calling
- Writing results to the scratchpad's DATA_COLLECTED section

This agent focuses exclusively on Prometheus data sources, providing better
separation of concerns and easier maintenance compared to the generic DataFetcherAgent.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aletheia.agents.sk_base import SKBaseAgent
from aletheia.fetchers.base import BaseFetcher, FetchResult, FetchError
from aletheia.fetchers.prometheus import PrometheusFetcher
from aletheia.fetchers.summarization import MetricSummarizer
from aletheia.llm.prompts import get_user_prompt_template
from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.scratchpad import ScratchpadSection
from aletheia.utils.retry import retry_with_backoff
from aletheia.utils.validation import validate_time_window
from aletheia.utils.logging import log_info, log_error, log_prompt


class PrometheusDataFetcher(SKBaseAgent):
    """SK-based agent specialized for collecting Prometheus metrics data.
    
    This agent uses Semantic Kernel's ChatCompletionAgent with PrometheusPlugin
    for automatic function calling via FunctionChoiceBehavior.Auto().
    
    The Prometheus Data Fetcher Agent:
    1. Reads the PROBLEM_DESCRIPTION section to understand what metrics to collect
    2. Uses SK PrometheusPlugin for data collection (metrics queries, templates)
    3. Constructs PromQL queries using templates or LLM-assisted generation
    4. Fetches metrics with intelligent sampling and aggregation
    5. Generates summaries of collected metrics
    6. Writes results to the DATA_COLLECTED section under "prometheus" key
    
    Attributes:
        config: Agent configuration including prometheus data source settings
        scratchpad: Scratchpad for reading problem and writing data
        fetcher: Direct PrometheusFetcher instance (for fallback)
        _plugin_registered: Whether SK plugin has been registered
    """
    
    def __init__(self, config: Dict[str, Any], scratchpad: Any):
        """Initialize the SK-based Prometheus Data Fetcher Agent.
        
        Args:
            config: Configuration dictionary with data_sources.prometheus and llm sections
            scratchpad: Scratchpad instance for agent communication
        """
        super().__init__(config, scratchpad, agent_name="prometheus_data_fetcher")
        
        # Initialize Prometheus fetcher (for direct access if needed)
        self.fetcher: Optional[PrometheusFetcher] = None
        self._initialize_fetcher()
        
        # Track plugin registration
        self._plugin_registered = False
    
    def _initialize_fetcher(self) -> None:
        """Initialize Prometheus fetcher from configuration."""
        data_sources_config = self.config.get("data_sources", {})
        
        if "prometheus" in data_sources_config:
            prom_config = data_sources_config["prometheus"]
            if prom_config.get("endpoint"):
                self.fetcher = PrometheusFetcher(prom_config)
    
    def _register_plugin(self) -> None:
        """Register Prometheus SK plugin with the kernel for automatic function calling.
        
        This registers the PrometheusPlugin so the SK agent can automatically
        invoke its functions via FunctionChoiceBehavior.Auto().
        """
        if self._plugin_registered:
            return
        
        data_sources_config = self.config.get("data_sources", {})
        
        if "prometheus" in data_sources_config:
            prom_config = data_sources_config["prometheus"]
            if prom_config.get("endpoint"):
                prom_plugin = PrometheusPlugin(prom_config)
                self.kernel.add_plugin(prom_plugin, plugin_name="prometheus")
                self._plugin_registered = True
    
    async def execute(
        self,
        time_window: Optional[str] = None,
        use_sk: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the Prometheus data fetching process.
        
        This method can operate in two modes:
        1. SK mode (default): Uses SK agent with automatic function calling via PrometheusPlugin
        2. Direct mode: Directly calls PrometheusFetcher (maintains backward compatibility)
        
        Args:
            time_window: Time window string (e.g., "2h", "30m")
                        If None, uses session default or problem description
            use_sk: If True, uses SK agent with plugin. If False, uses direct fetcher calls.
            **kwargs: Additional parameters (query, template, template_params, conversation_history, etc.)
        
        Returns:
            Dictionary with execution results:
                - success: bool - Whether execution succeeded
                - source: str - Always "prometheus"
                - count: int - Number of metric data points collected
                - summary: str - Summary of collected metrics
                - sk_used: bool - Whether SK mode was used
        
        Raises:
            ValueError: If Prometheus is not configured
        """
        if not self.fetcher and not self._plugin_registered:
            raise ValueError("Prometheus data source is not configured")
        
        # Read problem description from scratchpad
        problem = self.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) or {}
        
        # Log problem data for debugging
        log_info(f"Prometheus Data Fetcher - Problem description: {problem}")
        
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
        """Execute Prometheus data fetching using SK agent with automatic plugin invocation.
        
        This method uses the SK ChatCompletionAgent which can automatically
        call PrometheusPlugin functions (fetch_prometheus_metrics, execute_promql_query, etc.)
        based on the user's request.
        
        In conversational mode, it reads conversation history from scratchpad and
        delegates ALL parameter extraction to the LLM.
        
        Args:
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters (may include conversation_history, query, template, etc.)
        
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
        log_prompt("prometheus_data_fetcher", prompt, self._model if hasattr(self, '_model') else "unknown")
        
        # Invoke SK agent - it will automatically call plugin functions
        try:
            response = await self.invoke_async(prompt, settings={"temperature": 0.1})
            
            # Parse the response to extract collected data
            collected_data = self._parse_sk_response(response)
            
            # Build results summary
            results = {
                "success": True,
                "source": "prometheus",
                "count": collected_data.get("count", 0),
                "summary": collected_data.get("summary", ""),
                "sk_used": True,
            }
            
            # Write collected data to scratchpad under "prometheus" key
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["prometheus"] = collected_data
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
        """Execute Prometheus data fetching using direct fetcher calls (backward compatibility).
        
        This method directly calls the PrometheusFetcher implementation without SK.
        
        Args:
            time_range: Time range tuple (start, end)
            problem: Problem description from scratchpad
            **kwargs: Additional parameters (query, template, template_params, etc.)
        
        Returns:
            Dictionary with execution results
        """
        if not self.fetcher:
            raise ValueError("Prometheus fetcher not available")
        
        try:
            # Fetch Prometheus metrics
            fetch_result = self._fetch_prometheus(
                self.fetcher,
                time_range,
                problem,
                **kwargs
            )
            
            # Generate summary
            summary = self._summarize_metrics(fetch_result)
            
            # Store results
            collected_data = {
                "source": "prometheus",
                "count": fetch_result.count,
                "time_range": f"{fetch_result.time_range[0].isoformat()} - {fetch_result.time_range[1].isoformat()}",
                "summary": summary,
                "metadata": fetch_result.metadata,
            }
            
            # Write to scratchpad
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["prometheus"] = collected_data
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, existing_data)
            
            results = {
                "success": True,
                "source": "prometheus",
                "count": fetch_result.count,
                "summary": summary,
                "sk_used": False,
            }
            
            return results
            
        except FetchError as e:
            # Handle fetch failure
            log_error(f"Prometheus fetch failed: {str(e)}")
            
            collected_data = {
                "source": "prometheus",
                "error": str(e),
                "status": "failed",
            }
            
            existing_data = self.read_scratchpad(ScratchpadSection.DATA_COLLECTED) or {}
            existing_data["prometheus"] = collected_data
            self.write_scratchpad(ScratchpadSection.DATA_COLLECTED, existing_data)
            
            return {
                "success": False,
                "source": "prometheus",
                "error": str(e),
                "sk_used": False,
            }
    
    def _build_sk_prompt(
        self,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> str:
        """Build a prompt for the SK agent to collect Prometheus metrics.
        
        This method uses conversational mode with conversation history
        for the LLM to extract parameters naturally.
        
        Args:
            time_range: Time range for data collection
            problem: Problem description
            **kwargs: Additional parameters (may include conversation_history, query, template, etc.)
        
        Returns:
            Prompt string for SK agent
        """
        # Check if this is conversational mode (has conversation history)
        conversation_history = kwargs.get("conversation_history", [])
        use_conversational = bool(conversation_history)
        
        if use_conversational:
            # Use conversational template with LLM-delegated parameter extraction
            template = get_user_prompt_template("prometheus_data_fetcher_conversational")
            
            # Format problem description
            description = problem.get("description", "No description provided")
            affected_services = problem.get("affected_services", [])
            if affected_services:
                description += f"\nAffected services: {', '.join(affected_services)}"
            
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
        prompt = f"""Collect Prometheus metrics for this issue:

{description}"""
        
        # Add affected services if available
        if affected_services:
            prompt += f"\nAffected services: {', '.join(affected_services)}"
        
        # Add explicit parameters if provided
        explicit_params = []
        if kwargs.get("query"):
            explicit_params.append(f"PromQL query: {kwargs['query']}")
        if kwargs.get("template"):
            explicit_params.append(f"Template: {kwargs['template']}")
            if kwargs.get("template_params"):
                explicit_params.append(f"Template params: {kwargs['template_params']}")
        
        if explicit_params:
            prompt += "\n\nExplicit parameters:\n- " + "\n- ".join(explicit_params)
        
        # Add time window
        prompt += f"""

Time window: {start_time} to {end_time}

Task:
1. Determine which metrics are relevant for this issue (error rates, latency, resource usage, etc.)
2. Use prometheus.fetch_prometheus_metrics() or prometheus.build_promql_from_template() to collect metrics
3. Focus on metrics that show anomalies or spikes during the time window

Available templates:
- error_rate: Error rate over time
- latency_p95: 95th percentile latency
- request_rate: Request rate over time
- resource_usage_cpu: CPU usage
- resource_usage_memory: Memory usage
- custom_counter_rate: Rate of change for any counter metric

Return your results as JSON:
{{
    "count": <number of data points>,
    "summary": "<brief summary of findings>",
    "metadata": {{<relevant metadata like queries used>}}
}}
"""
        
        return prompt
    
    def _parse_sk_response(self, response: str) -> Dict[str, Any]:
        """Parse the SK agent's response to extract collected Prometheus data.
        
        Args:
            response: SK agent's response string
        
        Returns:
            Dictionary with Prometheus data (count, summary, metadata)
        """
        # Try to parse as JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                return {
                    "source": "prometheus",
                    "count": data.get("count", 0),
                    "summary": data.get("summary", ""),
                    "metadata": data.get("metadata", {}),
                }
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # If JSON parsing fails, create minimal structure
        return {
            "source": "prometheus",
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
    def _fetch_prometheus(
        self,
        fetcher: PrometheusFetcher,
        time_range: Tuple[datetime, datetime],
        problem: Dict[str, Any],
        **kwargs
    ) -> FetchResult:
        """Fetch metrics from Prometheus with retry logic.
        
        Args:
            fetcher: Prometheus fetcher instance
            time_range: Time range for metrics
            problem: Problem description
            **kwargs: Additional parameters (query, template, template_params, step, etc.)
        
        Returns:
            FetchResult with Prometheus metrics
        """
        # Check if query or template is provided
        query = kwargs.get("query")
        template = kwargs.get("template")
        template_params = kwargs.get("template_params", {})
        
        # If no query/template, try to generate one from problem
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
    
    def _summarize_metrics(self, fetch_result: FetchResult) -> str:
        """Generate a summary of fetched Prometheus metrics.
        
        Args:
            fetch_result: Result from fetching
        
        Returns:
            Human-readable summary string
        """
        summarizer = MetricSummarizer()
        summary_dict = summarizer.summarize(fetch_result.data)
        return summary_dict.get("summary", "No summary available")
