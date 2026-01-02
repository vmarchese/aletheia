"""PCAP File Data Fetcher Agent implementation."""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.pcap_file.pcap_file_plugin import PCAPFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PCAPFileDataFetcher(BaseAgent):
    """PCAP File Data Fetcher Agent for collecting and processing PCAP files."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad,
                 **kwargs):

        log_debug("PCAPFileDataFetcher::__init__:: called")

        log_debug("PCAPFileDataFetcher::__init__:: setup plugins")
        pcap_file_plugin = PCAPFilePlugin(config=config, session=session)

        plugins = [pcap_file_plugin, scratchpad]

        super().__init__(name=name,
                         description=description,
                         session=session,
                         plugins=plugins,
                         **kwargs)
