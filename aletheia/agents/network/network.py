from jinja2 import Template

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


        tools = []
        tools.extend(network_plugin.get_tools())
        tools.extend(scratchpad.get_tools())

        template = Template(instructions)
        rendered_instructions = template.render(plugins=plugins)

        super().__init__(name=name,
                         description=description,
                         instructions=rendered_instructions,
                         service=service,
                         session=session,
                         tools=tools)
    