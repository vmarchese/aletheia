"""Timeline Agent implementation."""

from aletheia.agents.base import BaseAgent
from aletheia.utils.logging import log_debug


class TimelineAgent(BaseAgent):
    """Timeline Agent for managing and visualizing event timelines."""
    def __init__(self,
                 name: str,
                 instructions: str,
                 description: str):

        log_debug("TimelineAgent::__init__:: called")

        super().__init__(name=name,
                         description=description,
                         instructions=instructions,
                         scratchpad=None,
                         render_instructions=False)
