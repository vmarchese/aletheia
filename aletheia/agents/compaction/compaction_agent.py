"""Compaction Agent for context compression."""

import structlog

from aletheia.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class CompactionAgent(BaseAgent):
    """Agent that compresses conversation history into a concise summary."""

    def __init__(self, name: str, instructions: str, description: str):
        logger.debug("CompactionAgent::__init__:: called")

        super().__init__(
            name=name,
            description=description,
            instructions=instructions,
            scratchpad=None,
            render_instructions=False,
        )
