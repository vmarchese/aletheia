"""PCAP File Data Fetcher Agent implementation."""

import structlog

from aletheia.agents.base import BaseAgent
from aletheia.plugins.pcap_file.pcap_file_plugin import PCAPFilePlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)
from aletheia.config import Config


class PCAPFileDataFetcher(BaseAgent):
    """PCAP File Data Fetcher Agent for collecting and processing PCAP files."""

    def __init__(
        self,
        name: str,
        config: Config,
        description: str,
        session: Session,
        scratchpad: Scratchpad,
        **kwargs,
    ):

        logger.debug("PCAPFileDataFetcher::__init__:: called")

        logger.debug("PCAPFileDataFetcher::__init__:: setup plugins")
        pcap_file_plugin = PCAPFilePlugin(config=config, session=session)

        plugins = [pcap_file_plugin, scratchpad]

        super().__init__(
            name=name,
            description=description,
            session=session,
            plugins=plugins,
            **kwargs,
        )
