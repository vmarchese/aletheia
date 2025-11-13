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


from jinja2 import Template

from agent_framework import  BaseChatClient, ChatMessageStore

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.pcap_file_plugin import PCAPFilePlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PCAPFileDataFetcher(BaseAgent):

    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        log_debug("PCAPFileDataFetcher::__init__:: called")

        log_debug("PCAPFileDataFetcher::__init__:: setup plugins")
        pcap_file_plugin = PCAPFilePlugin(config=config, session=session)

        tools = []
        plugins = [pcap_file_plugin, scratchpad]
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
    