from jinja2 import Template

from agent_framework import  BaseChatClient

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.aws_plugin import AWSPlugin
from aletheia.plugins.utils_plugin import UtilsPlugin
from aletheia.plugins.log_file_plugin import LogFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class AWSAgent(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("AWSAgent::__init__:: called")

        log_debug("AWSAgent::__init__:: setup plugins")
        aws_plugin = AWSPlugin(config=config, session=session, scratchpad=scratchpad)


        tools = []
        tools.extend(aws_plugin.get_tools())
        tools.extend(scratchpad.get_tools())
        tools.extend(UtilsPlugin(config=config, session=session).get_tools())
        tools.extend(LogFilePlugin(config=config, session=session).get_tools())

        template = Template(instructions)
        rendered_instructions = template.render(plugins=tools)

        super().__init__(name=name,
                         description=description,
                         instructions=rendered_instructions,
                         service=service,
                         session=session,
                         tools=tools)
    