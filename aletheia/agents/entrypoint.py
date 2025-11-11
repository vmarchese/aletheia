"""Semantic Kernel orchestration integration for Aletheia.

This module provides SK HandoffOrchestration integration for agent coordination,
replacing the custom routing logic with Semantic Kernel's orchestration pattern.
"""

from typing import List
from jinja2 import Template


from agent_framework import  BaseChatClient, ToolProtocol
from agent_framework import ChatMessageStore

from aletheia.plugins.scratchpad import Scratchpad
from aletheia.utils.logging import log_debug
from aletheia.session import Session
from aletheia.agents.base import BaseAgent


class Orchestrator(BaseAgent):
    """Wrapper for SK HandoffOrchestration with Aletheia-specific configuration.
    
    This class manages the SK HandoffOrchestration with appropriate callbacks
    for scratchpad updates, user interaction, and progress tracking.
    """
    
    def __init__(
        self,
        name: str, 
        description: str,
        instructions: str,
        service: BaseChatClient,
        session: Session,
        scratchpad: Scratchpad,
        sub_agents: List[ToolProtocol]):

        plugins = []
        plugins.extend(sub_agents)
        plugins.extend(scratchpad.get_tools())

        template = Template(instructions)
        rendered_instructions = template.render(plugins=plugins)   


        log_debug("Orchestrator::__init__:: called")
        super().__init__(name=name,
                         description=description,
                         instructions=rendered_instructions,
                         service=service,
                         session=session,
                         tools=plugins
                         )
