"""Semantic Kernel plugin for Prometheus operations.

This plugin exposes Prometheus operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides synchronous functions for:
- Fetching metrics from Prometheus using PromQL queries
- Executing PromQL queries with time windows
- Building queries from templates
- Testing connectivity
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, Optional, List

from agent_framework import ai_function, ToolProtocol

from aletheia.config import Config
from aletheia.utils.logging import log_debug, log_error
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin


# PromQL query templates for common use cases
PROMQL_TEMPLATES = {
    "error_rate": 'rate({metric_name}{{app="{service}",status=~"5.."}}[{window}])',
    "latency_p95": 'histogram_quantile(0.95, rate({metric_name}_bucket{{app="{service}"}}[{window}]))',
    "latency_p99": 'histogram_quantile(0.99, rate({metric_name}_bucket{{app="{service}"}}[{window}]))',
    "request_rate": 'rate({metric_name}{{app="{service}"}}[{window}])',
    "cpu_usage": 'rate(container_cpu_usage_seconds_total{{pod=~"{pod_pattern}"}}[{window}])',
    "memory_usage": 'container_memory_working_set_bytes{{pod=~"{pod_pattern}"}}',
}


class PrometheusPlugin(BasePlugin):
    """Semantic Kernel plugin for Prometheus operations.
    
    This plugin provides synchronous kernel functions for Prometheus
    operations, allowing SK agents to automatically invoke them via function calling.
    
    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.
    
    Attributes:
        endpoint: Prometheus server endpoint URL
        timeout: Default timeout for HTTP requests
        session: requests.Session for reusing connections
    """
    
    def __init__(self, config: Config):
        """Initialize the Prometheus plugin.
        
        Args:
            config: Configuration dictionary with Prometheus settings.
                   Must contain 'endpoint' key for Prometheus server URL.
        
        Raises:
            ValueError: If required configuration is missing
        """
        log_debug("PrometheusPlugin::__init__:: called")
        self.name = "PrometheusPlugin"
        
        if config.prometheus_endpoint:
            self.endpoint = config.prometheus_endpoint.rstrip('/')
        self.timeout = config.prometheus_timeout_seconds
        self.session = requests.Session()
        
        # Store auth config if provided
        self.auth_config = config.prometheus_credentials_type
        loader = PluginInfoLoader()
        self.instructions = loader.load("prometheus_plugin")        
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for authentication.
        
        Returns:
            Dictionary of headers for HTTP requests
        """
        headers = {"Accept": "application/json"}
        
        # MUST HANDLE AUTHENTICATION IF NEEDED
#        auth_type = self.auth_config.get("type")
#        if auth_type == "bearer":
#            token = self.auth_config.get("token")
#            if token:
#                headers["Authorization"] = f"Bearer {token}"
        
        return headers
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Prometheus API.
        
        Args:
            url: Request URL
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            Exception: If request fails
        """
        log_debug(f"PrometheusPlugin::_make_request:: URL={url} PARAMS={params}")
        headers = self._get_headers()
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            log_debug(f"PrometheusPlugin::_make_request:: HTTP Status={response.status_code}")
            if response.status_code == 401:
                log_error("PrometheusPlugin::_make_request:: Authentication failed with 401")
                raise Exception("Authentication failed: Invalid credentials")
            
            response.raise_for_status()
            data = response.json()
            log_debug(f"PrometheusPlugin::_make_request:: Response Data={data}")
            
            if data.get("status") != "success":
                log_error(f"PrometheusPlugin::_make_request:: Query failed: {data}")
                error_msg = data.get("error", "Unknown error")
                raise Exception(f"Prometheus query failed: {error_msg}")
            
            return data
                
        except requests.RequestException as e:
            log_error(f"PrometheusPlugin::_make_request:: HTTP request error: {str(e)}")
            raise Exception(f"HTTP request failed: {str(e)}")
    
    #@ai_function( name="fetch_prometheus_metrics", description="Fetch metrics from Prometheus using a PromQL query with optional time window filtering")
    def fetch_prometheus_metrics(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        start_time: Annotated[Optional[str], "Start time in ISO format (e.g., '2024-10-15T10:00:00')"] = None,
        end_time: Annotated[Optional[str], "End time in ISO format (e.g., '2024-10-15T12:00:00')"] = None,
        step: Annotated[Optional[str], "Query resolution step (e.g., '1m', '5m', '1h')"] = None,
        since_hours: Annotated[int, "If start_time/end_time not provided, hours to look back (default: 2)"] = 2,
    ) -> Annotated[str, "JSON string containing metrics, summary, and metadata"]:
        """Fetch metrics from Prometheus using a PromQL query.
        
        This function executes a PromQL query against Prometheus and returns
        structured metric data with summarization.
        
        Args:
            query: PromQL query string to execute
            start_time: Optional start time in ISO format (default: calculated from since_hours)
            end_time: Optional end time in ISO format (default: now)
            step: Optional query resolution step (default: calculated based on time range)
            since_hours: If times not provided, hours to look back (default: 2)
        
        Returns:
            JSON string with structure:
            {
                "data": [...],
                "summary": "...",
                "count": 123,
                "query": "...",
                "time_range": [...],
                "metadata": {...}
            }
        """
        log_debug("PrometheusPlugin::fetch_prometheus_metrics:: called")
        try:
            # Calculate time window
            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            else:
                end_dt = datetime.now()
            
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            else:
                start_dt = end_dt - timedelta(hours=since_hours)
            
            # Calculate step if not provided
            if not step:
                duration_hours = (end_dt - start_dt).total_seconds() / 3600
                if duration_hours <= 1:
                    step = "30s"
                elif duration_hours <= 6:
                    step = "1m"
                elif duration_hours <= 24:
                    step = "5m"
                else:
                    step = "1h"
            
            # Make range query to Prometheus
            url = f"{self.endpoint}/api/v1/query_range"
            params = {
                "query": query,
                "start": start_dt.timestamp(),
                "end": end_dt.timestamp(),
                "step": step
            }
            
            data = self._make_request(url, params)
            
            # Process results
            result_data = data.get("data", {}).get("result", [])
            all_values = []
            series_count = len(result_data)
            
            for series in result_data:
                metric_labels = series.get("metric", {})
                values = series.get("values", [])
                
                for timestamp, value in values:
                    all_values.append({
                        "timestamp": datetime.fromtimestamp(float(timestamp)).isoformat(),
                        "value": float(value) if value != "NaN" else None,
                        "metric": metric_labels
                    })
            
            # Generate summary
            valid_values = [v["value"] for v in all_values if v["value"] is not None]
            if valid_values:
                avg_value = sum(valid_values) / len(valid_values)
                max_value = max(valid_values)
                min_value = min(valid_values)
                summary = f"{len(all_values)} data points from {series_count} series. "
                summary += f"Values: min={min_value:.3f}, avg={avg_value:.3f}, max={max_value:.3f}"
            else:
                summary = f"No valid data points returned from {series_count} series"
            
            return json.dumps({
                "data": all_values,
                "summary": summary,
                "count": len(all_values),
                "series_count": series_count,
                "query": query,
                "step": step,
                "time_range": [start_dt.isoformat(), end_dt.isoformat()],
                "metadata": {
                    "endpoint": self.endpoint,
                    "query_type": "range"
                },
                "timestamp": datetime.now().isoformat()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to fetch metrics: {str(e)}",
                "query": query,
                "endpoint": self.endpoint
            })
    
    #@ai_function( name="execute_promql_query", description="Execute a PromQL query for instant values (single point in time)")
    def execute_promql_query(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        time: Annotated[Optional[str], "Time for query evaluation in ISO format (default: now)"] = None,
    ) -> Annotated[str, "JSON string containing instant query results"]:
        """Execute an instant PromQL query against Prometheus.
        
        This executes an instant query that returns values at a single point in time.
        
        Args:
            query: PromQL query string to execute
            time: Optional time for evaluation in ISO format (default: now)
        
        Returns:
            JSON string with query results
        """
        log_debug("PrometheusPlugin::execute_promql_query:: called")
        try:
            # Calculate evaluation time
            if time:
                eval_time = datetime.fromisoformat(time.replace('Z', '+00:00'))
            else:
                eval_time = datetime.now()
            
            # Make instant query to Prometheus
            url = f"{self.endpoint}/api/v1/query"
            params = {
                "query": query,
                "time": eval_time.timestamp()
            }
            
            data = self._make_request(url, params)
            
            # Process results
            result_data = data.get("data", {}).get("result", [])
            instant_values = []
            
            for series in result_data:
                metric_labels = series.get("metric", {})
                value_data = series.get("value", [])
                
                if len(value_data) >= 2:
                    timestamp, value = value_data
                    instant_values.append({
                        "timestamp": datetime.fromtimestamp(float(timestamp)).isoformat(),
                        "value": float(value) if value != "NaN" else None,
                        "metric": metric_labels
                    })
            
            # Generate summary
            valid_values = [v["value"] for v in instant_values if v["value"] is not None]
            if valid_values:
                summary = f"{len(instant_values)} instant values. "
                if len(valid_values) > 1:
                    avg_value = sum(valid_values) / len(valid_values)
                    summary += f"Average: {avg_value:.3f}"
                else:
                    summary += f"Value: {valid_values[0]:.3f}"
            else:
                summary = f"No valid instant values returned"
            
            return json.dumps({
                "data": instant_values,
                "summary": summary,
                "count": len(instant_values),
                "query": query,
                "evaluation_time": eval_time.isoformat(),
                "metadata": {
                    "endpoint": self.endpoint,
                    "query_type": "instant"
                },
                "timestamp": datetime.now().isoformat()
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to execute query: {str(e)}",
                "query": query,
                "endpoint": self.endpoint
            })
    
    #@ai_function( name="build_promql_from_template", description="Build a PromQL query from a predefined template with parameter substitution")
    def build_promql_from_template(
        self,
        template: Annotated[
            str,
            "Template name. Available: error_rate, latency_p95, latency_p99, request_rate, cpu_usage, memory_usage"
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
        log_debug("PrometheusPlugin::build_promql_from_template:: called")
        try:
            # Parse parameters
            try:
                template_params = json.loads(params)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"Invalid JSON parameters: {str(e)}"})
            
            # Check if template exists
            if template not in PROMQL_TEMPLATES:
                available = list(PROMQL_TEMPLATES.keys())
                return json.dumps({
                    "error": f"Unknown template: {template}",
                    "available_templates": available
                })
            
            # Build query from template
            template_pattern = PROMQL_TEMPLATES[template]
            try:
                query = template_pattern.format(**template_params)
            except KeyError as e:
                return json.dumps({
                    "error": f"Missing required parameter: {str(e)}",
                    "template": template,
                    "template_pattern": template_pattern
                })
            
            # If not executing, just return the query
            if not execute:
                return json.dumps({
                    "query": query,
                    "template": template,
                    "parameters": template_params
                })
            
            # Execute the query using fetch_prometheus_metrics
            result_json = self.fetch_prometheus_metrics(
                query=query,
                since_hours=since_hours
            )
            
            # Parse and enhance the result
            result = json.loads(result_json)
            result["template"] = template
            result["template_parameters"] = template_params
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to build/execute template query: {str(e)}",
                "template": template
            })
    
    #@ai_function( name="list_promql_templates", description="List all available PromQL query templates with their descriptions")
    def list_promql_templates(self) -> Annotated[str, "JSON object mapping template names to their descriptions"]:
        """List available PromQL query templates.
        
        Returns:
            JSON string with template names, patterns, and descriptions
        """
        log_debug("PrometheusPlugin::list_promql_templates:: called")
        templates_with_descriptions = {
            "error_rate": {
                "pattern": PROMQL_TEMPLATES["error_rate"],
                "description": "Rate of HTTP 5xx errors for a service",
                "required_params": ["metric_name", "service", "window"],
                "example_params": {
                    "metric_name": "http_requests_total",
                    "service": "payments-svc",
                    "window": "5m"
                }
            },
            "latency_p95": {
                "pattern": PROMQL_TEMPLATES["latency_p95"],
                "description": "95th percentile latency for a service",
                "required_params": ["metric_name", "service", "window"],
                "example_params": {
                    "metric_name": "http_request_duration_seconds",
                    "service": "payments-svc",
                    "window": "5m"
                }
            },
            "latency_p99": {
                "pattern": PROMQL_TEMPLATES["latency_p99"],
                "description": "99th percentile latency for a service",
                "required_params": ["metric_name", "service", "window"],
                "example_params": {
                    "metric_name": "http_request_duration_seconds",
                    "service": "payments-svc",
                    "window": "5m"
                }
            },
            "request_rate": {
                "pattern": PROMQL_TEMPLATES["request_rate"],
                "description": "Request rate for a service",
                "required_params": ["metric_name", "service", "window"],
                "example_params": {
                    "metric_name": "http_requests_total",
                    "service": "payments-svc",
                    "window": "5m"
                }
            },
            "cpu_usage": {
                "pattern": PROMQL_TEMPLATES["cpu_usage"],
                "description": "Container CPU usage rate",
                "required_params": ["pod_pattern", "window"],
                "example_params": {
                    "pod_pattern": "payments-.*",
                    "window": "5m"
                }
            },
            "memory_usage": {
                "pattern": PROMQL_TEMPLATES["memory_usage"],
                "description": "Container memory working set bytes",
                "required_params": ["pod_pattern"],
                "example_params": {
                    "pod_pattern": "payments-.*"
                }
            }
        }
        
        return json.dumps({
            "templates": templates_with_descriptions,
            "count": len(templates_with_descriptions),
            "usage": "Use build_promql_from_template to create queries from these templates"
        }, indent=2)
    
    #@ai_function( name="test_prometheus_connection", description="Test connectivity to the Prometheus server")
    def test_prometheus_connection(self) -> Annotated[str, "Connection test result message"]:
        """Test connection to Prometheus server.
        
        Returns:
            Success message if connection works, error message otherwise
        """
        log_debug("PrometheusPlugin::test_prometheus_connection:: called")
        try:
            url = f"{self.endpoint}/api/v1/query"
            params = {"query": "up"}
            
            data = self._make_request(url, params)
            
            # If we get here, the connection worked
            result_count = len(data.get("data", {}).get("result", []))
            return json.dumps({
                "success": True,
                "message": f"Successfully connected to Prometheus server",
                "endpoint": self.endpoint,
                "test_query_results": result_count,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Failed to connect to Prometheus server: {str(e)}",
                "endpoint": self.endpoint,
                "timestamp": datetime.now().isoformat()
            })
    
    def __del__(self):
        """Cleanup session on deletion."""
        if hasattr(self, 'session'):
            self.session.close()

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [
            self.fetch_prometheus_metrics,
            self.execute_promql_query,
            self.build_promql_from_template,
            self.list_promql_templates,
            self.test_prometheus_connection
        ]
