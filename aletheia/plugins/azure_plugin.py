import json
from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader


class AzurePlugin:
    """Semantic Kernel plugin for Azure operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the AzurePlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "AzurePlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("azure_plugin")

    async def _run_azure_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
        """Helper to run Azure CLI commands and handle output, errors, and saving."""
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
            log_error(f"{log_prefix} Error launching aws cli: {str(e)}")
            return f"Error launching aws cli: {e}"

    @kernel_function(description="Gets Azure accounts for the current user.")
    async def azure_accounts(self) -> str:
        """Launches az account list."""
        command = ["az", "account", "list"]
        return await self._run_azure_command(command, save_key="azure_accounts", log_prefix="AzurePlugin::azure_accounts::")

    @kernel_function(description="Gets Azure resource group for a region user.")
    async def azure_resource_groups(self,
                                     region: Annotated[str, "The default region"] = "",) -> str:
        """Launches az account list."""

        command = ["az", "group", "list"]
        if region and region.strip() != "":
            command.extend(["--query", f"[?location=='{region}']"])

        return await self._run_azure_command(command, save_key="azure_resource_groups", log_prefix="AzurePlugin::azure_resource_groups::")
