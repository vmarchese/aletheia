"""
AWS Agent implementation for managing AWS resources via chat interface."""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.aws_amp.aws_amp_plugin import AWSAMPPlugin
from aletheia.plugins.utils.utils_plugin import UtilsPlugin
from aletheia.plugins.log_file.log_file_plugin import LogFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class AWSAMPAgent(BaseAgent):
    """AWS Managed Prometheus Agent for managing AWS Managed Prometheus resources."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad,
                 **kwargs):

        log_debug("AWSAgent::__init__:: called")

        log_debug("AWSAgent::__init__:: setup plugins")
        aws_amp_plugin = AWSAMPPlugin(config=config, session=session, scratchpad=scratchpad)
        utils_plugin = UtilsPlugin(config=config, session=session)
        log_file_plugin = LogFilePlugin(config=config, session=session)
        plugins = [aws_amp_plugin, scratchpad, utils_plugin, log_file_plugin]

        super().__init__(name=name,
                         config=config,
                         description=description,
                         session=session,
                         plugins=plugins,
                         **kwargs)
