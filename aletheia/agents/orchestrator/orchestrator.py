"""Orchestrator agent for managing the investigation workflow.

This module provides the OrchestratorAgent class which manages the overall
investigation workflow, including:
- Session initialization
- User interaction via conversational mode
- Routing to specialist agents
- Presenting findings to the user
- Error handling and recovery

The orchestrator uses conversational mode with natural language interaction
and intent-based routing.

Routing strategies:
1. Custom routing (legacy): Direct agent-to-agent routing
"""
from aletheia.agents.base import BaseAgent
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.utils.logging import log_debug


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent for managing the investigation workflow."""
    def __init__(self,
                 name: str,
                 description: str,
                 instructions: str,
                 session: Session,
                 scratchpad: Scratchpad):
        log_debug("OrchestratorAgent::__init__:: called")

        plugins = [scratchpad]
        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         session=session,
                         plugins=plugins,
                         render_instructions=False
                         )
