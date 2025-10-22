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


from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.scratchpad import Scratchpad
from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PrometheusDataFetcher(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: ChatCompletionClientBase,
                 session: Session,
                 scratchpad: Scratchpad):

        
        log_debug("PrometheusDataFetcher::__init__:: called")
        log_debug("PrometheusDataFetcher::__init__:: initialize PrometheusFetcher plugin")
        prometheus_fetcher_plugin = PrometheusPlugin(config)

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         scratchpad=scratchpad,
                         plugins=[ prometheus_fetcher_plugin])  