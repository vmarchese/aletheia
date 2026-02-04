"""Network Agent implementation."""

import structlog

from aletheia.agents.base import BaseAgent
from aletheia.plugins.network.network_plugin import NetworkPlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)
from aletheia.config import Config


class NetworkAgent(BaseAgent):
    """Network Agent for interacting with network services."""

    def __init__(
        self,
        name: str,
        config: Config,
        description: str,
        session: Session,
        scratchpad: Scratchpad,
        **kwargs,
    ):

        logger.debug("NetworkAgent::__init__:: called")

        logger.debug("NetworkAgent::__init__:: setup plugins")
        network_plugin = NetworkPlugin(
            config=config, session=session, scratchpad=scratchpad
        )
        plugins = [network_plugin, scratchpad]

        super().__init__(
            name=name,
            description=description,
            session=session,
            plugins=plugins,
            **kwargs,
        )
