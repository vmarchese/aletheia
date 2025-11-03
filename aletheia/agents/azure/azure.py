from jinja2 import Template
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

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
                 service: ChatCompletionClientBase,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("AzureAgent::__init__:: called")

        log_debug("AzureAgent::__init__:: setup plugins")
        azure_plugin = AzurePlugin(config=config, session=session)

        plugins = [azure_plugin, scratchpad]

        template = Template(instructions)
        rendered_instructions = template.render(plugins=plugins)

        super().__init__(name=name,
                         description=description,
                         instructions=rendered_instructions,
                         service=service,
                         session=session,
                         plugins=plugins)
    