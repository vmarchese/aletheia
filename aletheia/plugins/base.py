"""Base plugin class for Aletheia plugins."""
from typing import List
from abc import abstractmethod

from agent_framework import ToolProtocol


class BasePlugin:
    """Base class for Aletheia plugins."""
    @abstractmethod
    def get_tools(self) -> List[ToolProtocol]:
        """Returns a list of tools provided by the plugin."""
