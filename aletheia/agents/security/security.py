"""
Security Agent Module
"""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.security.security import SecurityPlugin
from aletheia.plugins.utils.utils_plugin import UtilsPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class SecurityAgent(BaseAgent):
    """Security Agent for managing security testing and analysis."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad,
                 **kwargs):

        log_debug("SecurityAgent::__init__:: called")
        log_debug("SecurityAgent::__init__:: setup plugins")
        security_plugin = SecurityPlugin(config=config, session=session, scratchpad=scratchpad)
        utils_plugin = UtilsPlugin(config=config, session=session)
        plugins = [security_plugin, scratchpad, utils_plugin]

        super().__init__(name=name,
                         config=config,
                         description=description,
                         session=session,
                         plugins=plugins,
                         **kwargs)
