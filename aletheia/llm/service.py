"""Module for LLM service integration."""

from aletheia.config import Config


class LLMService:
    """LLM Service integration class."""
    def __init__(self, config: Config):
        self.config = config
        self.client = None
