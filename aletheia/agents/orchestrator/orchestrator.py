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



from agent_framework import  BaseChatClient,ChatMessageStore

from aletheia.agents.base import BaseAgent
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.utils.logging import log_debug

class OrchestratorAgent(BaseAgent):
    def __init__(self, 
                 name: str, 
                 description: str,
                 instructions: str,
                 service: BaseChatClient,
                 session: Session,
                 scratchpad: Scratchpad):
        log_debug("OrchestratorAgent::__init__:: called")
        

        plugins = []
        plugins.extend(scratchpad.get_tools())
        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         tools=plugins
                         )