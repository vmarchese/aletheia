"""
SysDiag Agent Module
"""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.sysdiag.sysdiag import SysDiagPlugin
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.utils.utils_plugin import UtilsPlugin
from aletheia.plugins.log_file.log_file_plugin import LogFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class SysDiagAgent(BaseAgent):
    """SysDiag Agent for system diagnostics and troubleshooting."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("SysDiagAgent::__init__:: called")

        log_debug("SysDiagAgent::__init__:: setup plugins")
        sysdiag_plugin = SysDiagPlugin(config=config, session=session, scratchpad=scratchpad)
        utils_plugin = UtilsPlugin(config=config, session=session)
        log_file_plugin = LogFilePlugin(config=config, session=session)
        plugins = [scratchpad, sysdiag_plugin, utils_plugin, log_file_plugin]

        super().__init__(name=name,
                         config=config,
                         description=description,
                         session=session,
                         plugins=plugins)
