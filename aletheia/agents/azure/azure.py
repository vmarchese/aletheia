from jinja2 import Template

from agent_framework import  BaseChatClient

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.azure_plugin import AzurePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class AzureAgent(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("AzureAgent::__init__:: called")

        log_debug("AzureAgent::__init__:: setup plugins")
        azure_plugin = AzurePlugin(config=config, session=session)
        plugins = [azure_plugin,scratchpad]

        tools = []
        for plugin in plugins:
            tools.extend(plugin.get_tools())


        template = Template(instructions)
        rendered_instructions = template.render(plugins=plugins)

        super().__init__(name=name,
                         description=description,
                         instructions=rendered_instructions,
                         service=service,
                         session=session,
                         tools=tools)
    