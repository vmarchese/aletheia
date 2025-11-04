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

    @kernel_function(description="Gets Azure virtual machines for a resource group.")
    async def azure_vms(self,
                       resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm list."""
        command = ["az", "vm", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_vms", log_prefix="AzurePlugin::azure_vms::")


    @kernel_function(description="Gets Azure virtual machine details")
    async def azure_vm_show(self,
                             vm_name: Annotated[str, "The virtual machine name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm show."""
        command = ["az", "vm", "show", "--name", vm_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_vm_show", log_prefix="AzurePlugin::azure_vm_show::")


    @kernel_function(description="Gets Azure storage accounts for a resource group.")
    async def azure_storage_accounts(self,
                                     resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm list."""
        command = ["az", "storage", "account", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_storage_accounts", log_prefix="AzurePlugin::azure_storage_accounts::")


    @kernel_function(description="Gets Azure storage account details")
    async def azure_storage_account_show(self,
                             account_name: Annotated[str, "The storage account name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az storage account show."""
        command = ["az", "storage", "account", "show", "--name", account_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_storage_account_show", log_prefix="AzurePlugin::azure_storage_account_show::")


    @kernel_function(description="Gets Azure Keyvault list for a resource group.")
    async def azure_keyvaults(self,
                               resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault list."""
        command = ["az", "keyvault", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_keyvaults", log_prefix="AzurePlugin::azure_keyvaults::")


    @kernel_function(description="Gets Azure Keyvault details")
    async def azure_keyvault_show(self,
                             keyvault_name: Annotated[str, "The Keyvault name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault show."""
        command = ["az", "keyvault", "show", "--name", keyvault_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_keyvault_show", log_prefix="AzurePlugin::azure_keyvault_show::")


    @kernel_function(description="Gets Azure Keyvault keys for a Keyvault.")
    async def azure_keyvault_keys(self,
                                   keyvault_name: Annotated[str, "The Keyvault name"],
                                   resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault key list."""
        command = ["az", "keyvault", "key", "list", "--vault-name", keyvault_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_keyvault_keys", log_prefix="AzurePlugin::azure_keyvault_keys::")


    @kernel_function(description="Gets Azure Keyvault Key details")
    async def azure_keyvault_key_show(self,
                             keyvault_name: Annotated[str, "The Keyvault name"],
                             key_name: Annotated[str, "The Key name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault key show."""
        command = ["az", "keyvault", "key", "show", "--vault-name", keyvault_name, "--name", key_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return await self._run_azure_command(command, save_key="azure_keyvault_key_show", log_prefix="AzurePlugin::azure_keyvault_key_show::")

