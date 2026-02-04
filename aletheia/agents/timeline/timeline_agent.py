"""Timeline Agent implementation."""

import structlog

from aletheia.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class TimelineAgent(BaseAgent):
    """Timeline Agent for managing and visualizing event timelines."""

    def __init__(self, name: str, instructions: str, description: str):

        logger.debug("TimelineAgent::__init__:: called")

        super().__init__(
            name=name,
            description=description,
            instructions=instructions,
            scratchpad=None,
            render_instructions=False,
        )
