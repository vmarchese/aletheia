"""Azure Agent implementation."""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.azure_plugin import AzurePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class AzureAgent(BaseAgent):
    """Azure Agent for interacting with Azure services."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("AzureAgent::__init__:: called")

        log_debug("AzureAgent::__init__:: setup plugins")
        azure_plugin = AzurePlugin(config=config, session=session)
        plugins = [azure_plugin, scratchpad]

        super().__init__(name=name,
                         description=description,
                         session=session,
                         plugins=plugins)
