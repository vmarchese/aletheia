import json
from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin


class AzurePlugin(BasePlugin):
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

    def _run_azure_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
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

    #@ai_function(description="Gets Azure accounts for the current user.")
    def azure_accounts(self) -> str:
        """Launches az account list."""
        command = ["az", "account", "list"]
        return self._run_azure_command(command, save_key="azure_accounts", log_prefix="AzurePlugin::azure_accounts::")

    #@ai_function(description="Gets Azure resource group for a region user.")
    def azure_resource_groups(self,
                                     region: Annotated[str, "The default region"] = "",) -> str:
        """Launches az account list."""

        command = ["az", "group", "list"]
        if region and region.strip() != "":
            command.extend(["--query", f"[?location=='{region}']"])

        return self._run_azure_command(command, save_key="azure_resource_groups", log_prefix="AzurePlugin::azure_resource_groups::")

    #@ai_function(description="Gets Azure virtual machines for a resource group.")
    def azure_vms(self,
                       resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm list."""
        command = ["az", "vm", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_vms", log_prefix="AzurePlugin::azure_vms::")


    #@ai_function(description="Gets Azure virtual machine details")
    def azure_vm_show(self,
                             vm_name: Annotated[str, "The virtual machine name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm show."""
        command = ["az", "vm", "show", "--name", vm_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_vm_show", log_prefix="AzurePlugin::azure_vm_show::")


    #@ai_function(description="Gets Azure storage accounts for a resource group.")
    def azure_storage_accounts(self,
                                     resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az vm list."""
        command = ["az", "storage", "account", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_storage_accounts", log_prefix="AzurePlugin::azure_storage_accounts::")


    #@ai_function(description="Gets Azure storage account details")
    def azure_storage_account_show(self,
                             account_name: Annotated[str, "The storage account name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az storage account show."""
        command = ["az", "storage", "account", "show", "--name", account_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_storage_account_show", log_prefix="AzurePlugin::azure_storage_account_show::")


    #@ai_function(description="Gets Azure Keyvault list for a resource group.")
    def azure_keyvaults(self,
                               resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault list."""
        command = ["az", "keyvault", "list"]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvaults", log_prefix="AzurePlugin::azure_keyvaults::")


    #@ai_function(description="Gets Azure Keyvault details")
    def azure_keyvault_show(self,
                             keyvault_name: Annotated[str, "The Keyvault name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault show."""
        command = ["az", "keyvault", "show", "--name", keyvault_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvault_show", log_prefix="AzurePlugin::azure_keyvault_show::")


    #@ai_function(description="Gets Azure Keyvault keys for a Keyvault.")
    def azure_keyvault_keys(self,
                                   keyvault_name: Annotated[str, "The Keyvault name"],
                                   resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault key list."""
        command = ["az", "keyvault", "key", "list", "--vault-name", keyvault_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvault_keys", log_prefix="AzurePlugin::azure_keyvault_keys::")


    #@ai_function(description="Gets Azure Keyvault Key details")
    def azure_keyvault_key_show(self,
                             keyvault_name: Annotated[str, "The Keyvault name"],
                             key_name: Annotated[str, "The Key name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault key show."""
        command = ["az", "keyvault", "key", "show", "--vault-name", keyvault_name, "--name", key_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvault_key_show", log_prefix="AzurePlugin::azure_keyvault_key_show::")


    #@ai_function(description="Gets Azure Keyvault secrets for a Keyvault.")
    def azure_keyvault_secrets(self,
                                   keyvault_name: Annotated[str, "The Keyvault name"],
                                   resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault secret list."""
        command = ["az", "keyvault", "secret", "list", "--vault-name", keyvault_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvault_secrets", log_prefix="AzurePlugin::azure_keyvault_secrets::")


    #@ai_function(description="Gets Azure Keyvault Secret details")
    def azure_keyvault_secret_show(self,
                             keyvault_name: Annotated[str, "The Keyvault name"],
                             secret_name: Annotated[str, "The Secret name"],
                             resource_group: Annotated[str, "The resource group name"] = "") -> str:
        """Launches az keyvault secret show."""
        command = ["az", "keyvault", "secret", "show", "--vault-name", keyvault_name, "--name", secret_name]
        if resource_group and resource_group.strip() != "":
            command.extend(["--resource-group", resource_group])
        return self._run_azure_command(command, save_key="azure_keyvault_secret_show", log_prefix="AzurePlugin::azure_keyvault_secret_show::")


    def get_tools(self) -> List[ToolProtocol]:
        """Returns the list of tools provided by this plugin."""
        return [
            self.azure_accounts,
            self.azure_resource_groups,
            self.azure_vms,
            self.azure_vm_show,
            self.azure_storage_accounts,
            self.azure_storage_account_show,
            self.azure_keyvaults,
            self.azure_keyvault_show,
            self.azure_keyvault_keys,
            self.azure_keyvault_key_show,
            self.azure_keyvault_secrets,
            self.azure_keyvault_secret_show,
        ]
