"""Prometheus Data Fetcher Agent for collecting Prometheus metrics.

This specialized agent is responsible for:
- Collecting metrics from Prometheus
- Executing PromQL queries
- Using query templates for common patterns
- Using PrometheusPlugin for SK-based automatic function calling
- Writing results to the scratchpad's DATA_COLLECTED section

This agent focuses exclusively on Prometheus data sources, providing better
separation of concerns and easier maintenance compared to the generic DataFetcherAgent.
"""


from jinja2 import Template

from agent_framework import  BaseChatClient, ChatMessageStore

from aletheia.agents.base import BaseAgent
from aletheia.session import Session
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.prometheus_plugin import PrometheusPlugin
from aletheia.utils.logging import log_debug
from aletheia.config import Config


class PrometheusDataFetcher(BaseAgent):
    def __init__(self, 
                 name: str, 
                 config: Config,
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):

        
        log_debug("PrometheusDataFetcher::__init__:: called")
        log_debug("PrometheusDataFetcher::__init__:: initialize PrometheusFetcher plugin")
        prometheus_fetcher_plugin = PrometheusPlugin(config)


        tools = []
        plugins = [prometheus_fetcher_plugin, scratchpad]
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