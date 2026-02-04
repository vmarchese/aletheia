"""Prometheus Data Fetcher Agent implementation."""

import structlog

from aletheia.agents.base import BaseAgent
from aletheia.plugins.prometheus.prometheus_plugin import PrometheusPlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)
from aletheia.config import Config


class PrometheusDataFetcher(BaseAgent):
    """Prometheus Data Fetcher Agent for collecting and processing Prometheus metrics."""

    def __init__(
        self,
        name: str,
        config: Config,
        description: str,
        session: Session,
        scratchpad: Scratchpad,
    ):

        logger.debug("PrometheusDataFetcher::__init__:: called")
        logger.debug(
            "PrometheusDataFetcher::__init__:: initialize PrometheusFetcher plugin"
        )
        prometheus_fetcher_plugin = PrometheusPlugin(config)

        plugins = [prometheus_fetcher_plugin, scratchpad]

        super().__init__(
            name=name, description=description, session=session, plugins=plugins
        )
