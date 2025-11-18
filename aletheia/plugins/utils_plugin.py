""""Utility plugin for various helper functions."""
import json
import subprocess
import ipaddress
from typing import Annotated, List
from datetime import datetime
import dateparser

from agent_framework import ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader


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
            log_debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True, check=False)
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
        except (OSError, ValueError, ImportError, AttributeError, RuntimeError) as e:
            log_error(f"{log_prefix} Error launching command: {str(e)}")
            return f"Error launching command: {e}"
        except subprocess.SubprocessError as e:
            log_error(f"{log_prefix} Subprocess error: {str(e)}")
            return f"Subprocess error: {e}"

    def utils_gunzip_file(
        self,
        file_path: Annotated[str, "The path to the gzipped file"],
    ) -> str:
        """Gunzips the file at the given path."""
        command = ["gunzip", "-f", file_path]
        self._run_command(command, save_key="gunzip", log_prefix="UtilsPlugin::gunzip_file::")
        gunzipped_path = file_path.rstrip('.gz')
        if self.session:
            self.session.save_data(SessionDataType.INFO, "gunzip", f"file gunzipped to {gunzipped_path}")
        return f"File {gunzipped_path} gunzipped successfully."

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

    def ip_in_cidr(
        self,
        ip_address: Annotated[str, "The IP address to check"],
        cidr_block: Annotated[str, "The CIDR block to check against"],
    ) -> bool:
        """Checks if the given IP address is in the specified CIDR block."""
        try:
            ip = ipaddress.ip_address(ip_address)
            network = ipaddress.ip_network(cidr_block, strict=False)
            return ip in network
        except ValueError as e:
            log_error(f"UtilsPlugin::ip_in_cidr:: Invalid IP address or CIDR block: {str(e)}")
            return False

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [
            self.utils_gunzip_file,
            self.utils_get_date_offset,
            self.ip_in_cidr
        ]
