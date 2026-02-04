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

import structlog

from aletheia.agents.base import BaseAgent
from aletheia.plugins.kubernetes.kubernetes_plugin import KubernetesPlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)
from aletheia.config import Config


class KubernetesDataFetcher(BaseAgent):
    """Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information."""

    def __init__(
        self,
        name: str,
        config: Config,
        description: str,
        session: Session,
        scratchpad: Scratchpad,
        **kwargs,
    ):

        logger.debug("KubernetesDataFetcher::__init__:: called")

        logger.debug("KubernetesDataFetcher::__init__:: setup plugins")
        kube_fetcher_plugin = KubernetesPlugin(config=config, session=session)

        plugins = [kube_fetcher_plugin, scratchpad]

        super().__init__(
            name=name,
            config=config,
            description=description,
            session=session,
            plugins=plugins,
            **kwargs,
        )
