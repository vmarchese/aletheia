"""plugin for Prometheus operations.

This plugin exposes Prometheus operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides synchronous functions for:
- Fetching metrics from Prometheus using PromQL queries
- Executing PromQL queries with time windows
- Building queries from templates
- Testing connectivity
"""

import json
from typing import Annotated, Any, List, Optional

import requests

from botocore.session import Session as BotocoreSession
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from agent_framework import ToolProtocol

from aletheia.config import Config
from aletheia.utils.logging import log_debug
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin
from aletheia.session import Session, SessionDataType
from aletheia.plugins.scratchpad.scratchpad import Scratchpad

# PromQL query templates for common use cases
PROMQL_TEMPLATES = {
    "error_rate": 'rate({metric_name}{{app="{service}",status=~"5.."}}[{window}])',
    "latency_p95": 'histogram_quantile(0.95, rate({metric_name}_bucket{{app="{service}"}}[{window}]))',
    "latency_p99": 'histogram_quantile(0.99, rate({metric_name}_bucket{{app="{service}"}}[{window}]))',
    "request_rate": 'rate({metric_name}{{app="{service}"}}[{window}])',
    "cpu_usage": 'rate(container_cpu_usage_seconds_total{{pod=~"{pod_pattern}"}}[{window}])',
    "memory_usage": 'container_memory_working_set_bytes{{pod=~"{pod_pattern}"}}',
}


class AWSAMPPlugin(BasePlugin):
    """plugin for AWS Managed Prometheus operations.

    This plugin provides synchronous kernel functions for Prometheus
    operations, allowing SK agents to automatically invoke them via function calling.

    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.

    Attributes:
        endpoint: Prometheus server endpoint URL
        timeout: Default timeout for HTTP requests
        session: requests.Session for reusing connections
    """

    def __init__(self,
                 config: Config,
                 session: Session,
                 scratchpad: Scratchpad):
        """Initialize the Prometheus plugin.

        Args:
            config: Configuration dictionary with Prometheus settings.
                   Must contain 'endpoint' key for Prometheus server URL.

        Raises:
            ValueError: If required configuration is missing
        """
        log_debug("AWSAMP::__init__:: called")
        self.name = "AWSAMPPlugin"

        if config.prometheus_endpoint:
            self.endpoint = config.prometheus_endpoint.rstrip('/')
        self.timeout = config.prometheus_timeout_seconds
        self.session = session
        self.scratchpad = scratchpad

        # Store auth config if provided
        loader = PluginInfoLoader()
        self.instructions = loader.load("aws_amp_plugin")

    def _save_response(
        self, data: Any, save_key: str, log_prefix: str = ""
    ) -> Optional[str]:
        """Save response data to session if session is available.

        Args:
            data: Data to save (will be JSON serialized)
            save_key: Key to save the data under
            log_prefix: Prefix for log messages

        Returns:
            Path where data was saved, or None if session unavailable
        """
        if self.session:
            json_data = json.dumps(data, indent=2, default=str)
            saved_path = self.session.save_data(SessionDataType.INFO, save_key, json_data)
            log_debug(f"{log_prefix} Saved output to {saved_path}")
            return str(saved_path)
        return None        

    def _make_request(self,
                      query: str,
                      profile: str,
                      region: str,
                      workspace_id: str) -> Any:
        """Make HTTP request to Prometheus API.

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        # 1. Get credentials from SSO profile via botocore
        bc_session = BotocoreSession(profile=profile)
        creds = bc_session.get_credentials().get_frozen_credentials()

        # 2. Build the AMP data-plane URL
        url = (
                f"https://aps-workspaces.{region}.amazonaws.com"
                f"/workspaces/{workspace_id}/api/v1/query"
            )
        params = {"query": query}

        # 3. Create and sign a botocore AWSRequest
        aws_request = AWSRequest(method="GET", url=url, params=params)
        SigV4Auth(creds, "aps", region).add_auth(aws_request)

        # 4. Prepare the AWSRequest (this gives AWSPreparedRequest)
        aws_prepared = aws_request.prepare()

        # 5. Translate AWSPreparedRequest → requests.Request → PreparedRequest
        req = requests.Request(
            method=aws_prepared.method,
            url=aws_prepared.url,
            headers=dict(aws_prepared.headers),
            data=aws_prepared.body,
        )
        session = requests.Session()
        prepared = session.prepare_request(req)

        # 6. Send with requests
        resp = session.send(prepared)
        resp.raise_for_status()
        data = resp.json()

        # AMP uses the standard Prometheus API shape
        # { "status": "success", "data": { "resultType": "...", "result": [...] } }
        return data["data"]["result"]

    def fetch_prometheus_metrics(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        region: Annotated[str, "AWS region of the Prometheus workspace"],
        profile: Annotated[str, "AWS CLI profile name for authentication"],
        workspace_id: Annotated[str, "AWS Managed Prometheus workspace ID"],
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
            result = self._make_request(query, profile, region, workspace_id)
            self._save_response(result, "amp_metrics", "AWSAMPPlugin::fetch_prometheus_metrics::")            

            return result
        except (ValueError, KeyError, TypeError, requests.RequestException) as e:
            return json.dumps({
                "error": f"Failed to fetch metrics: {str(e)}",
                "query": query,
                "endpoint": self.endpoint
            })

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [
            self.fetch_prometheus_metrics,
        ]
