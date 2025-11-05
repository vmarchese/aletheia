"""Semantic Kernel plugin for Kubernetes operations.

This plugin exposes Kubernetes operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides simplified async functions for:
- Fetching logs from pods
- Listing pods in namespaces
- Getting pod status information
"""

from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session


class LogFilePlugin:
    """Semantic Kernel plugin for log file operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the LogFilePlugin.

        Args:
            config: Configuration object for the plugin
        """
        self.name = "LogFilePlugin"
        self.config = config
        self.session = session
        loader = PluginInfoLoader()
        self.instructions = loader.load("log_file_plugin")        

    @kernel_function(description="Fetch logs from a file.")
    async def fetch_logs_from_file(
        self,
        file_path: Annotated[str, "Path to the log file"]
    ) -> str:
        """Fetch logs from a specified log file.

        Args:
            file_path: Path to the log file

        Returns:
            Logs from the specified file
        """
        try:
            log_debug(f"Fetching logs from file: {file_path}")
            with open(file_path, 'r') as f:
                logs = f.read()
            return logs
        except Exception as e:
            log_error(f"Error fetching logs from file {file_path}: {e}")
            return f"Error fetching logs: {e}"