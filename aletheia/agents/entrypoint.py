"""Orchestrator agent for managing sub-agents and scratchpad."""


import structlog
from agent_framework import ToolProtocol

from aletheia.agents.base import BaseAgent
from aletheia.engram.tools import Engram
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)


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
        session: Session,
        scratchpad: Scratchpad,
        sub_agents: list[ToolProtocol],
        config=None,
        additional_middleware=None,
        engram: Engram | None = None,
    ):
        tools = []
        tools.extend(sub_agents)
        tools.extend(scratchpad.get_tools())

        logger.debug("Orchestrator::__init__:: called")
        super().__init__(
            name=name,
            description=description,
            instructions=instructions,
            session=session,
            tools=tools,
            render_instructions=True,
            config=config,
            additional_middleware=additional_middleware,
            engram=engram,
        )
