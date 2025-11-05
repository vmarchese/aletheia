import json
from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader


class UtilsPlugin:
    """Semantic Kernel plugin for utility operations."""

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

    async def _run_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
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

    @kernel_function(description="Gunzips a file at the given path")
    async def gunzip_file(
        self,
        file_path: Annotated[str, "The path to the gzipped file"],
    ) -> str:
        """Gunzips the file at the given path."""
        command = ["gunzip", "-f", file_path]
        return await self._run_command(command, save_key=None, log_prefix="UtilsPlugin::gunzip_file::")