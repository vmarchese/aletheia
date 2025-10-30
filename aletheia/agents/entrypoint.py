"""Semantic Kernel orchestration integration for Aletheia.

This module provides SK HandoffOrchestration integration for agent coordination,
replacing the custom routing logic with Semantic Kernel's orchestration pattern.
"""

from typing import List

from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.functions.kernel_plugin import KernelPlugin


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
        service: ChatCompletionClientBase,
        session: Session,
        scratchpad: Scratchpad,
        sub_agents: List[KernelPlugin]):

        log_debug("Orchestrator::__init__:: called")
        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         service=service,
                         session=session,
                         plugins=[sub_agents, scratchpad])