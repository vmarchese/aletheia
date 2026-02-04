"""Base plugin class for Aletheia plugins."""

from abc import abstractmethod

from agent_framework import ToolProtocol


class BasePlugin:
    """Base class for Aletheia plugins."""

    @abstractmethod
    def get_tools(self) -> list[ToolProtocol]:
        """Returns a list of tools provided by the plugin."""
