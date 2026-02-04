"""Azure Agent implementation."""

import structlog

from aletheia.agents.base import BaseAgent
from aletheia.plugins.azure.azure_plugin import AzurePlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)
from aletheia.config import Config


class AzureAgent(BaseAgent):
    """Azure Agent for interacting with Azure services."""

    def __init__(
        self,
        name: str,
        config: Config,
        description: str,
        session: Session,
        scratchpad: Scratchpad,
        **kwargs,
    ):

        logger.debug("AzureAgent::__init__:: called")

        logger.debug("AzureAgent::__init__:: setup plugins")
        azure_plugin = AzurePlugin(config=config, session=session)
        plugins = [azure_plugin, scratchpad]

        super().__init__(
            name=name,
            config=config,
            description=description,
            session=session,
            plugins=plugins,
            **kwargs,
        )
