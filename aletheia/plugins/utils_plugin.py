import json
from typing import Annotated, List
import dateparser
from datetime import datetime

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin


class UtilsPlugin:
    """plugin for utility operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the UtilsPlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        loader = PluginInfoLoader()
        self.instructions = loader.load("utils_plugin")

    def _run_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
        """Helper to run commands and handle output, errors, and saving."""
        try:
            import subprocess
            log_debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True)
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": ' '.join(command) + f" failed: {error_msg}"
                })
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                log_debug(f"{log_prefix} Saved output to {saved}")
            return output
        except Exception as e:
            log_error(f"{log_prefix} Error launching command: {str(e)}")
            return f"Error launching command: {e}"        

    #@ai_function(description="Gunzips a file at the given path")
    def utils_gunzip_file(
        self,
        file_path: Annotated[str, "The path to the gzipped file"],
    ) -> str:
        """Gunzips the file at the given path."""
        command = ["gunzip", "-f", file_path]
        self._run_command(command, save_key="gunzip", log_prefix="UtilsPlugin::gunzip_file::")
        gunzipped_path = file_path.rstrip('.gz')
        if self.session:
                saved = self.session.save_data(SessionDataType.INFO, "gunzip", f"file gunzipped to {gunzipped_path}")
        return f"File {gunzipped_path} gunzipped successfully."

    #@ai_function(description="Gets a date offset in natural language (e.g., '5 days ago', '3 hours ago')")
    def utils_get_date_offset(
        self,
        time_delta: Annotated[str, "The time delta (e.g., '5 days', '3 hours', '5d', '3h')"],
    ) -> str:
        """Gets the date string for a time delta ago in ISO format (YYYY-MM-DDTHH:MM:SS)."""

        # Use dateparser to parse the time delta string relative to now
        now = datetime.now()
        dt = dateparser.parse(f"{time_delta} ago", settings={"RELATIVE_BASE": now})
        if not dt:
            return "Invalid time_delta format. Use e.g. '5 days', '3 hours', '5d', '3h', or combinations."
        return dt.isoformat(sep="T", timespec="seconds")

    def get_tools(self) -> List[ToolProtocol]: 
        """Get the list of tools provided by this plugin."""
        return [
            self.utils_gunzip_file,
            self.utils_get_date_offset
        ]   
