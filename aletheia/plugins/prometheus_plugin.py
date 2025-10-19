"""Semantic Kernel plugin for Prometheus operations.

This plugin exposes Prometheus operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin wraps PrometheusFetcher functionality and provides annotated
functions for:
- Fetching metrics from Prometheus
- Executing PromQL queries
- Building PromQL queries from templates
- Testing Prometheus connectivity
"""

import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List

from semantic_kernel.functions import kernel_function

from aletheia.fetchers.prometheus import PrometheusFetcher, PROMQL_TEMPLATES
from aletheia.utils.logging import log_operation_start, log_operation_complete, log_plugin_invocation


class PrometheusPlugin:
    """Semantic Kernel plugin for Prometheus operations.
    
    This plugin provides kernel functions that wrap PrometheusFetcher
    operations, allowing SK agents to automatically invoke Prometheus
    operations via function calling.
    
    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.
    
    Attributes:
        fetcher: PrometheusFetcher instance for actual Prometheus operations
        endpoint: Prometheus server endpoint URL
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Prometheus plugin.
        
        Args:
            config: Configuration dictionary with Prometheus settings.
                   Must contain 'endpoint' key for Prometheus server URL.
        
        Raises:
            ValueError: If required configuration is missing
        """
        if "endpoint" not in config:
            raise ValueError("Prometheus 'endpoint' is required in config")
        
        self.config = config
        self.fetcher = PrometheusFetcher(config)
        self.endpoint = config["endpoint"]
    
    @kernel_function(
        name="fetch_prometheus_metrics",
        description="Fetch metrics from Prometheus using a PromQL query with optional time window filtering"
    )
    def fetch_metrics(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        start_time: Annotated[str | None, "Start time in ISO format (e.g., '2024-10-15T10:00:00')"] = None,
        end_time: Annotated[str | None, "End time in ISO format (e.g., '2024-10-15T12:00:00')"] = None,
        step: Annotated[str | None, "Query resolution step (e.g., '1m', '5m', '1h'). If not specified, adaptive step will be used"] = None,
        timeout: Annotated[int, "Query timeout in seconds (default: 30)"] = 30,
    ) -> Annotated[str, "JSON string containing metrics, summary, and metadata"]:
        """Fetch metrics from Prometheus using a PromQL query.
        
        This function executes a PromQL query against Prometheus and returns
        structured metric data with automatic summarization and anomaly detection.
        
        Args:
            query: PromQL query string to execute
            start_time: Optional start time in ISO format (default: 2 hours ago)
            end_time: Optional end time in ISO format (default: now)
            step: Optional query resolution step (default: adaptive based on time window)
            timeout: Query timeout in seconds (default: 30)
        
        Returns:
            JSON string with structure:
            {
                "data": [...],
                "summary": "...",
                "count": 123,
                "time_range": [...],
                "metadata": {...}
            }
        """
        # Log plugin invocation
        log_plugin_invocation(
            plugin_name="PrometheusPlugin",
            function_name="fetch_metrics",
            parameters={
                "query": query,
                "start_time": start_time,
                "end_time": end_time,
                "step": step,
                "timeout": timeout
            }
        )
        
        # Start operation timing
        operation_start = log_operation_start(
            operation_name="prometheus_query",
            details={"query": query[:100], "endpoint": self.endpoint}
        )
        
        # Parse time window if specified
        time_window = None
        if start_time or end_time:
            start = datetime.fromisoformat(start_time) if start_time else datetime.now() - timedelta(hours=2)
            end = datetime.fromisoformat(end_time) if end_time else datetime.now()
            time_window = (start, end)
        
        # Prepare kwargs
        kwargs = {"query": query, "timeout": timeout}
        if step:
            kwargs["step"] = step
        
        # Call fetcher
        result = self.fetcher.fetch(time_window=time_window, **kwargs)
        
        # Log completion
        log_operation_complete(
            operation_name="prometheus_query",
            start_time=operation_start,
            result_summary=f"{result.count} data points collected"
        )
        
        # Return as JSON string for LLM consumption
        return json.dumps({
            "data": result.data,
            "summary": result.summary,
            "count": result.count,
            "time_range": [
                result.time_range[0].isoformat(),
                result.time_range[1].isoformat()
            ],
            "metadata": result.metadata
        }, indent=2)
    
    @kernel_function(
        name="execute_promql_query",
        description="Execute a raw PromQL query string against Prometheus"
    )
    def execute_query(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        since_hours: Annotated[int, "Number of hours to look back (default: 2)"] = 2,
    ) -> Annotated[str, "JSON string containing query results"]:
        """Execute a PromQL query with a simple time window.
        
        This is a simplified version of fetch_metrics that uses a relative
        time window specified in hours.
        
        Args:
            query: PromQL query string to execute
            since_hours: Number of hours to look back from now (default: 2)
        
        Returns:
            JSON string with query results
        """
        # Log plugin invocation
        log_plugin_invocation(
            plugin_name="PrometheusPlugin",
            function_name="execute_query",
            parameters={"query": query, "since_hours": since_hours}
        )
        
        # Start operation timing
        operation_start = log_operation_start(
            operation_name="prometheus_execute_query",
            details={"query": query[:100]}
        )
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=since_hours)
        time_window = (start_time, end_time)
        
        result = self.fetcher.fetch(time_window=time_window, query=query)
        
        # Log completion
        log_operation_complete(
            operation_name="prometheus_execute_query",
            start_time=operation_start,
            result_summary=f"{result.count} data points"
        )
        
        return json.dumps({
            "data": result.data,
            "summary": result.summary,
            "count": result.count,
            "time_range": [
                result.time_range[0].isoformat(),
                result.time_range[1].isoformat()
            ]
        }, indent=2)
    
    @kernel_function(
        name="build_promql_from_template",
        description="Build a PromQL query from a predefined template with parameter substitution"
    )
    def build_query_from_template(
        self,
        template: Annotated[
            str,
            "Template name. Available templates: error_rate, latency_p95, latency_p99, request_rate, cpu_usage, memory_usage"
        ],
        params: Annotated[str, "JSON string with template parameters (e.g., '{\"service\": \"payments-svc\", \"window\": \"5m\"}')"],
        execute: Annotated[bool, "Whether to execute the query immediately (default: False)"] = False,
        since_hours: Annotated[int, "If execute=True, number of hours to look back (default: 2)"] = 2,
    ) -> Annotated[str, "The built PromQL query string, or JSON with query results if execute=True"]:
        """Build a PromQL query from a template.
        
        Available templates:
        - error_rate: Rate of HTTP 5xx errors
        - latency_p95: 95th percentile latency
        - latency_p99: 99th percentile latency
        - request_rate: Request rate
        - cpu_usage: Container CPU usage
        - memory_usage: Container memory usage
        
        Args:
            template: Template name from available templates
            params: JSON string with parameters for template substitution
            execute: Whether to execute the query immediately (default: False)
            since_hours: If execute=True, number of hours to look back (default: 2)
        
        Returns:
            If execute=False: The built PromQL query string
            If execute=True: JSON string with query results
        """
        # Parse parameters
        try:
            template_params = json.loads(params)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON parameters: {str(e)}"})
        
        # Build query from template
        try:
            query = self.fetcher._build_query_from_template(template, template_params)
        except Exception as e:
            return json.dumps({"error": f"Failed to build query: {str(e)}"})
        
        # If not executing, just return the query
        if not execute:
            return query
        
        # Execute the query
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=since_hours)
        time_window = (start_time, end_time)
        
        try:
            result = self.fetcher.fetch(time_window=time_window, query=query)
            
            return json.dumps({
                "query": query,
                "data": result.data,
                "summary": result.summary,
                "count": result.count,
                "time_range": [
                    result.time_range[0].isoformat(),
                    result.time_range[1].isoformat()
                ]
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to execute query: {str(e)}", "query": query})
    
    @kernel_function(
        name="list_promql_templates",
        description="List all available PromQL query templates with their descriptions"
    )
    def list_templates(self) -> Annotated[str, "JSON object mapping template names to their PromQL patterns"]:
        """List available PromQL query templates.
        
        Returns:
            JSON string with template names and their PromQL patterns
        """
        templates_with_descriptions = {
            "error_rate": {
                "pattern": PROMQL_TEMPLATES["error_rate"],
                "description": "Rate of HTTP 5xx errors for a service",
                "required_params": ["metric_name", "service", "window"]
            },
            "latency_p95": {
                "pattern": PROMQL_TEMPLATES["latency_p95"],
                "description": "95th percentile latency for a service",
                "required_params": ["metric_name", "service", "window"]
            },
            "latency_p99": {
                "pattern": PROMQL_TEMPLATES["latency_p99"],
                "description": "99th percentile latency for a service",
                "required_params": ["metric_name", "service", "window"]
            },
            "request_rate": {
                "pattern": PROMQL_TEMPLATES["request_rate"],
                "description": "Request rate for a service",
                "required_params": ["metric_name", "service", "window"]
            },
            "cpu_usage": {
                "pattern": PROMQL_TEMPLATES["cpu_usage"],
                "description": "Container CPU usage rate",
                "required_params": ["pod_pattern", "window"]
            },
            "memory_usage": {
                "pattern": PROMQL_TEMPLATES["memory_usage"],
                "description": "Container memory working set bytes",
                "required_params": ["pod_pattern"]
            }
        }
        
        return json.dumps(templates_with_descriptions, indent=2)
    
    @kernel_function(
        name="test_prometheus_connection",
        description="Test connectivity to the Prometheus server"
    )
    def test_connection(self) -> Annotated[str, "Connection test result message"]:
        """Test connection to Prometheus server.
        
        Returns:
            Success message if connection works, error message otherwise
        """
        try:
            success = self.fetcher.test_connection()
            if success:
                return f"Successfully connected to Prometheus server (endpoint: {self.endpoint})"
            else:
                return f"Failed to connect to Prometheus server (endpoint: {self.endpoint})"
        except Exception as e:
            return f"Prometheus connection error: {str(e)}"
    
    @kernel_function(
        name="get_prometheus_capabilities",
        description="Get information about what operations this Prometheus plugin supports"
    )
    def get_capabilities(self) -> Annotated[str, "JSON object describing plugin capabilities"]:
        """Get Prometheus plugin capabilities.
        
        Returns:
            JSON string describing what operations are supported
        """
        capabilities = self.fetcher.get_capabilities()
        return json.dumps(capabilities, indent=2)
