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
from datetime import datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import requests
import structlog
from agent_framework import FunctionTool
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session, SessionDataType

logger = structlog.get_logger(__name__)

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

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the Prometheus plugin.

        Args:
            config: Configuration dictionary with Prometheus settings.
                   Must contain 'endpoint' key for Prometheus server URL.

        Raises:
            ValueError: If required configuration is missing
        """
        logger.debug("AWSAMP::__init__:: called")
        self.name = "AWSAMPPlugin"

        if config.prometheus_endpoint:
            self.endpoint = config.prometheus_endpoint.rstrip("/")
        self.timeout = config.prometheus_timeout_seconds
        self.session = session
        self.scratchpad = scratchpad

        # Store auth config if provided
        loader = PluginInfoLoader()
        self.instructions = loader.load("aws_amp")

    def _save_response(
        self, data: Any, save_key: str, log_prefix: str = ""
    ) -> str | None:
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
            saved_path = self.session.save_data(
                SessionDataType.INFO, save_key, json_data
            )
            logger.debug(f"{log_prefix} Saved output to {saved_path}")
            return str(saved_path)
        return None

    def _make_request(
        self,
        profile: str,
        region: str,
        workspace_id: str,
        endpoint: str | None = None,
        params: list[dict] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """Make HTTP request to Prometheus API.

        Args:
            query: PromQL query string
            profile: AWS CLI profile name
            region: AWS region
            workspace_id: AMP workspace ID
            start_date: Start time in ISO format (optional)
            end_date: End time in ISO format (optional)

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        # 1. Get credentials from SSO profile via botocore
        bc_session = BotocoreSession(profile=profile)
        creds = bc_session.get_credentials().get_frozen_credentials()

        # 2. Build the AMP data-plane URL
        # Use query_range endpoint if start_date provided, otherwise use instant query
        url = (
            f"https://aps-workspaces.{region}.amazonaws.com"
            f"/workspaces/{workspace_id}/api/v1/{endpoint}"
        )

        # 3. Merge params list into a single dictionary
        # Prometheus API expects form-encoded data: query=...&start=...&end=...
        params_dict = {}
        if params:
            for param in params:
                params_dict.update(param)

        # Add time parameters if provided
        if start_date:
            params_dict["start"] = start_date
        if end_date:
            params_dict["end"] = end_date
        if start_date and end_date:
            # Calculate step automatically (1 point per minute by default)
            params_dict["step"] = "60s"

        logger.debug(
            f"PrometheusPlugin::_make_request:: Making request to {url} with params {params_dict}"
        )

        # 4. Encode params as form data (application/x-www-form-urlencoded)
        body = urlencode(params_dict).encode("utf-8")

        # 5. Create and sign a botocore AWSRequest
        aws_request = AWSRequest(
            method="POST",
            url=url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        SigV4Auth(creds, "aps", region).add_auth(aws_request)

        # 6. Prepare the AWSRequest (this gives AWSPreparedRequest)
        aws_prepared = aws_request.prepare()

        logger.debug("PrometheusPlugin::_make_request:: Prepared signed request")
        logger.debug(f"URL: {aws_prepared.url}")
        logger.debug(f"Headers: {aws_prepared.headers}")
        logger.debug(f"Body: {aws_prepared.body}")

        # 7. Translate AWSPreparedRequest → requests.Request → PreparedRequest
        req = requests.Request(
            method=aws_prepared.method,
            url=aws_prepared.url,
            headers=dict(aws_prepared.headers),
            data=aws_prepared.body,
        )
        session = requests.Session()
        prepared = session.prepare_request(req)

        # 8. Send with requests
        resp = session.send(prepared)
        resp.raise_for_status()
        data = resp.json()

        # AMP uses the standard Prometheus API shape
        # For query/query_range: { "status": "success", "data": { "resultType": "...", "result": [...] } }
        # For series: { "status": "success", "data": [...] }

        # Return different structure based on endpoint
        if endpoint == "series":
            # Series endpoint returns data as a list directly
            return data["data"]
        else:
            # Query endpoints return data with result key
            return data["data"]["result"]

    def fetch_prometheus_metrics(
        self,
        query: Annotated[str, "The PromQL query string to execute"],
        region: Annotated[str, "AWS region of the Prometheus workspace"],
        profile: Annotated[str, "AWS CLI profile name for authentication"],
        workspace_id: Annotated[str, "AWS Managed Prometheus workspace ID"],
        start_date: Annotated[
            str | None,
            "Start time in ISO format (YYYY-MM-DDTHH:MM:SSZ). Default: 4 hours ago",
        ] = None,
        end_date: Annotated[
            str | None, "End time in ISO format (YYYY-MM-DDTHH:MM:SSZ). Default: now"
        ] = None,
    ) -> Annotated[str, "JSON string containing metrics, summary, and metadata"]:
        """Fetch metrics from Prometheus using a PromQL query.

        This function executes a PromQL query against Prometheus and returns
        structured metric data with summarization.

        Args:
            query: PromQL query string to execute
            region: AWS region of the Prometheus workspace
            profile: AWS CLI profile name for authentication
            workspace_id: AWS Managed Prometheus workspace ID
            start_date: Start time in ISO format (default: 4 hours ago)
            end_date: End time in ISO format (default: now)

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
        logger.debug("PrometheusPlugin::fetch_prometheus_metrics:: called")
        try:
            # Set default time range if not provided: now-4h to now
            if end_date is None:
                end_date = datetime.utcnow().isoformat() + "Z"
            if start_date is None:
                start_time = datetime.utcnow() - timedelta(hours=4)
                start_date = start_time.isoformat() + "Z"

            if start_date:
                endpoint = "query_range"
            else:
                endpoint = "query"

            result = self._make_request(
                params=[{"query": query}],
                endpoint=endpoint,
                profile=profile,
                region=region,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
            )
            self._save_response(
                result, "amp_metrics", "AWSAMPPlugin::fetch_prometheus_metrics::"
            )

            return result
        except (ValueError, KeyError, TypeError, requests.RequestException) as e:
            return json.dumps(
                {
                    "error": f"Failed to fetch metrics: {str(e)}",
                    "query": query,
                    "endpoint": self.endpoint,
                }
            )

    def get_series(
        self,
        profile: Annotated[str, "AWS CLI profile name for authentication"],
        region: Annotated[str, "AWS region of the Prometheus workspace"],
        workspace_id: Annotated[str, "AWS Managed Prometheus workspace ID"],
        matchers: Annotated[list[str], "PromQL series matchers string"],
    ) -> Annotated[list[dict], "List of matching time series"]:
        """Get time series from Prometheus matching the given matchers.

        Args:
            matchers: PromQL series matchers string
            profile: AWS CLI profile name for authentication
            region: AWS region of the Prometheus workspace
            workspace_id: AWS Managed Prometheus workspace ID
            start_date: Start time in ISO format (optional)
            end_date: End time in ISO format (optional)
        """
        # Implementation to fetch time series based on matchers
        logger.debug("PrometheusPlugin::get_series:: called")
        try:
            _matchers = []
            for matcher in matchers:
                _matchers.append({"match[]": matcher})

            result = self._make_request(
                endpoint="series",
                params=_matchers,
                profile=profile,
                region=region,
                workspace_id=workspace_id,
            )
            self._save_response(result, "amp_series", "AWSAMPPlugin::get_series::")

            return result
        except (ValueError, KeyError, TypeError, requests.RequestException) as e:
            return json.dumps(
                {
                    "error": f"Failed to fetch series: {str(e)}",
                    "matchers": matchers,
                    "endpoint": "series",
                }
            )

    def get_query_templates(
        self,
    ) -> Annotated[list[str], "List of available PromQL query templates"]:
        """Get the list of available PromQL query templates.

        Returns:
            List of template names
        """
        return list(PROMQL_TEMPLATES.keys())

    def get_tools(self) -> list[FunctionTool]:
        """Get the list of tools provided by this plugin."""
        return [self.fetch_prometheus_metrics, self.get_series]
