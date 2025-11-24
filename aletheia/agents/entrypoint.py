"""Orchestrator agent for managing sub-agents and scratchpad."""
from typing import List

from agent_framework import ToolProtocol

from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.utils.logging import log_debug
from aletheia.session import Session
from aletheia.agents.base import BaseAgent


class Orchestrator(BaseAgent):
    """Wrapper for SK HandoffOrchestration with Aletheia-specific configuration.
    This class manages the SK HandoffOrchestration with appropriate callbacks
    for scratchpad updates, user interaction, and progress tracking.
    """
    def __init__(self,
                 name: str,
                 description: str,
                 instructions: str,
                 session: Session,
                 scratchpad: Scratchpad,
                 sub_agents: List[ToolProtocol]):
        tools = []
        tools.extend(sub_agents)
        tools.extend(scratchpad.get_tools())

        log_debug("Orchestrator::__init__:: called")
        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         session=session,
                         tools=tools,
                         render_instructions=False
                         )
