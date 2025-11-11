"""Semantic Kernel plugin for Kubernetes operations.

This plugin exposes Kubernetes operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides simplified async functions for:
- Fetching logs from pods
- Listing pods in namespaces
- Getting pod status information
"""

from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session
from aletheia.plugins.base import BasePlugin


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

    #@ai_function(description="Fetch logs from a file.")
    def fetch_logs_from_file(
        self,
        file_path: Annotated[str, "Path to the log file"]
    ) -> str:
        """Fetch logs from a specified log file.

        Args:
            file_path: Path to the log file

        Returns:
            Logs from the specified file
        """
        import os

        def try_read(path: str) -> str:
            try:
                log_debug(f"Fetching logs from file: {path}")
                with open(path, 'r') as f:
                    return f.read()
            except Exception as e:
                log_error(f"Error fetching logs from file {path}: {e}")
                return f"Error fetching logs: {e}"

        # 1. Check if the file exists at the given path
        if os.path.isfile(file_path):
            return try_read(file_path)

        # 2. If not, traverse session.data_dir to find the file by name
        log_debug(f"File not found at {file_path}, searching in session.data_dir: {self.session.data_dir}")
        file_name = os.path.basename(file_path)
        for root, _, files in os.walk(self.session.data_dir):
            if file_name in files:
                found_path = os.path.join(root, file_name)
                log_debug(f"Found file {file_name} at {found_path}")
                return try_read(found_path)

        # 3. If still not found, return error
        log_error(f"Log file {file_path} not found in session.data_dir: {self.session.data_dir}")
        return f"Error: Log file '{file_path}' not found in session data directory."

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [self.fetch_logs_from_file]
