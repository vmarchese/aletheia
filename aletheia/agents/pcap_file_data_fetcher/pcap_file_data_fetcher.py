from agent_framework import  BaseChatClient, ChatMessageStore

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.pcap_file_plugin import PCAPFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PCAPFileDataFetcher(BaseAgent):

    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("PCAPFileDataFetcher::__init__:: called")

        log_debug("PCAPFileDataFetcher::__init__:: setup plugins")
        pcap_file_plugin = PCAPFilePlugin(config=config, session=session)

        plugins = [pcap_file_plugin, scratchpad]

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         plugins=plugins)
    