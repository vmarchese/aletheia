"""Kubernetes Data Fetcher Agent for collecting Kubernetes logs and pod information.

This specialized agent is responsible for:
- Collecting logs from Kubernetes pods
- Listing pods and their statuses
- Extracting pod/namespace information from problem descriptions
- Using KubernetesPlugin for SK-based automatic function calling
- Writing results to the scratchpad's DATA_COLLECTED section

This agent focuses exclusively on Kubernetes data sources, providing better
separation of concerns and easier maintenance compared to the generic DataFetcherAgent.
"""
from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.log_file.log_file_plugin import LogFilePlugin
from aletheia.plugins.utils.utils_plugin import UtilsPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class LogFileDataFetcher(BaseAgent):
    """Log File Data Fetcher Agent for collecting and processing log files."""
    def __init__(self,
                 name: str,
                 config: Config,
                 description: str,
                 session: Session,
                 scratchpad: Scratchpad,
                 **kwargs):

        log_debug("LogFileDataFetcher::__init__:: called")

        log_debug("LogFileDataFetcher::__init__:: setup plugins")
        log_file_plugin = LogFilePlugin(config=config, session=session)

        plugins = [log_file_plugin, scratchpad, UtilsPlugin(config=config, session=session)]

        super().__init__(name=name,
                         description=description,
                         session=session,
                         plugins=plugins,
                         **kwargs)
