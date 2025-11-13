from agent_framework import  BaseChatClient

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.network_plugin import NetworkPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class NetworkAgent(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("NetworkAgent::__init__:: called")

        log_debug("NetworkAgent::__init__:: setup plugins")
        network_plugin = NetworkPlugin(config=config, session=session, scratchpad=scratchpad)
        plugins = [network_plugin,scratchpad]

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         plugins=plugins)
    