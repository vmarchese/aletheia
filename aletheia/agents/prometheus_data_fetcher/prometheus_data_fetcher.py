"""Prometheus Data Fetcher Agent implementation."""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.prometheus.prometheus_plugin import PrometheusPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PrometheusDataFetcher(BaseAgent):
    """Prometheus Data Fetcher Agent for collecting and processing Prometheus metrics."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("PrometheusDataFetcher::__init__:: called")
        log_debug("PrometheusDataFetcher::__init__:: initialize PrometheusFetcher plugin")
        prometheus_fetcher_plugin = PrometheusPlugin(config)

        plugins = [prometheus_fetcher_plugin, scratchpad]

        super().__init__(name=name,
                         description=description,
                         session=session,
                         plugins=plugins)
