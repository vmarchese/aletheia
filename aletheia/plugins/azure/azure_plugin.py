"""Azure plugin for Aletheia."""

import json
import subprocess
from typing import Annotated

import structlog
from agent_framework import FunctionTool
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys import KeyClient
from azure.keyvault.secrets import SecretClient
from azure.mgmt.cdn import CdnManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from azure.mgmt.storage import StorageManagementClient
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

from aletheia.config import Config
from aletheia.plugins.azure.kusto_query_loader import KustoQueryLoader
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session, SessionDataType
from aletheia.utils.command import sanitize_command

logger = structlog.get_logger(__name__)


class AzurePlugin(BasePlugin):
    """plugin for Azure operations."""

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
        self.instructions = loader.load("azure")
        self.kusto_query_loader = KustoQueryLoader(config)

    def _run_azure_command(
        self, command: list, save_key: str = None, log_prefix: str = ""
    ) -> str:
        """Helper to run Azure CLI commands and handle output, errors, and saving."""
        try:
            logger.debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(
                args=sanitize_command(command), capture_output=True, check=False
            )
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps(
                    {"error": " ".join(command) + f" failed: {error_msg}"}
                )
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                logger.debug(f"{log_prefix} Saved output to {saved}")
            return output
        except (OSError, ValueError, ImportError, subprocess.CalledProcessError) as e:
            logger.error(f"{log_prefix} Error launching Azure CLI: {str(e)}")
            return f"Error launching Azure CLI: {e}"

    def azure_accounts(self) -> str:
        """Retrieves the list of Azure subscriptions using Azure SDK."""
        credential = DefaultAzureCredential()
        sub_client = SubscriptionClient(credential)

        subscriptions = [sub.as_dict() for sub in sub_client.subscriptions.list()]

        return json.dumps(subscriptions)

    def azure_resource_groups(
        self,
        region: Annotated[str, "The default region"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the list of resource groups in the specified region using Azure SDK."""
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        groups = [
            rg
            for rg in client.resource_groups.list()
            if rg.location.lower() == region.lower()
        ]
        group_list = [g.as_dict() for g in groups]
        return json.dumps(group_list)

    def azure_vms(
        self,
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """ " Retrieves the list of VMs in the specified resource group using Azure SDK."""
        credential = DefaultAzureCredential()
        compute = ComputeManagementClient(credential, subscription_id)

        vms = compute.virtual_machines.list(resource_group)
        vm_list = [vm.as_dict() for vm in vms]
        return json.dumps(vm_list)

    def azure_vm_show(
        self,
        vm_name: Annotated[str, "The virtual machine name"],
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific VM using Azure SDK."""
        credential = DefaultAzureCredential()
        compute = ComputeManagementClient(credential, subscription_id)
        vm = compute.virtual_machines.get(resource_group, vm_name)
        return json.dumps(vm.as_dict())

    def azure_storage_accounts(
        self,
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the list of storage accounts in the specified resource group using Azure SDK."""
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        storage_accounts = [
            sa
            for sa in client.resources.list_by_resource_group(resource_group)
            if sa.type.lower() == "microsoft.storage/storageaccounts"
        ]
        sa_list = [sa.as_dict() for sa in storage_accounts]
        return json.dumps(sa_list)

    def azure_storage_account_show(
        self,
        account_name: Annotated[str, "The storage account name"],
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific storage account using Azure SDK."""
        credential = DefaultAzureCredential()
        client = StorageManagementClient(credential, subscription_id=subscription_id)
        sa = client.storage_accounts.get_properties(resource_group, account_name)
        return json.dumps(sa.as_dict())

    def azure_keyvaults(
        self,
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the list of keyvaults in the specified resource group using Azure SDK."""
        credential = DefaultAzureCredential()
        client = KeyVaultManagementClient(credential, subscription_id=subscription_id)
        keyvaults = list(client.vaults.list_by_resource_group(resource_group))
        kv_list = [kv.as_dict() for kv in keyvaults]
        return json.dumps(kv_list)

    def azure_keyvault_show(
        self,
        keyvault_name: Annotated[str, "The Keyvault name"],
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific keyvault using Azure SDK."""
        credential = DefaultAzureCredential()
        client = KeyVaultManagementClient(credential, subscription_id=subscription_id)
        kv = client.vaults.get(resource_group, keyvault_name)
        return json.dumps(kv.as_dict())

    def azure_keyvault_keys(
        self, keyvault_name: Annotated[str, "The Keyvault name"]
    ) -> str:
        """Retrieves the list of keys in the specified keyvault using Azure SDK."""
        credential = DefaultAzureCredential()
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        key_client = KeyClient(vault_url=vault_url, credential=credential)
        keys = key_client.list_properties_of_keys()
        key_list = []
        for key in keys:
            key_list.append(
                {
                    "id": key.id,
                    "name": key.name,
                    "enabled": key.enabled,
                    "created_on": (
                        key.created_on.isoformat() if key.created_on else None
                    ),
                    "updated_on": (
                        key.updated_on.isoformat() if key.updated_on else None
                    ),
                    "expires_on": (
                        key.expires_on.isoformat() if key.expires_on else None
                    ),
                }
            )
        return json.dumps(key_list)

    def azure_keyvault_key_show(
        self,
        keyvault_name: Annotated[str, "The Keyvault name"],
        key_name: Annotated[str, "The Key name"],
    ) -> str:
        """Retrieves details of a specific key in the specified keyvault using Azure SDK."""
        credential = DefaultAzureCredential()
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        key_client = KeyClient(vault_url=vault_url, credential=credential)
        key = key_client.get_key(key_name)

        return {
            "id": key.id,
            "name": key.name,
            "key_type": key.key_type,
            "key_operations": key.key_operations,
            "created_on": (
                key.properties.created_on.isoformat()
                if key.properties.created_on
                else None
            ),
            "updated_on": (
                key.properties.updated_on.isoformat()
                if key.properties.updated_on
                else None
            ),
            "expires_on": (
                key.properties.expires_on.isoformat()
                if key.properties.expires_on
                else None
            ),
        }

    def azure_keyvault_secrets(
        self, keyvault_name: Annotated[str, "The Keyvault name"]
    ) -> str:
        """Retrieves the list of secrets in the specified keyvault using Azure SDK."""
        credential = DefaultAzureCredential()
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        secret_client = SecretClient(vault_url=vault_url, credential=credential)
        secrets = secret_client.list_properties_of_secrets()
        secret_list = []
        for secret in secrets:
            secret_list.append(
                {
                    "id": secret.id,
                    "name": secret.name,
                    "enabled": secret.enabled,
                    "created_on": (
                        secret.created_on.isoformat() if secret.created_on else None
                    ),
                    "updated_on": (
                        secret.updated_on.isoformat() if secret.updated_on else None
                    ),
                    "expires_on": (
                        secret.expires_on.isoformat() if secret.expires_on else None
                    ),
                }
            )
        return json.dumps(secret_list)

    def azure_keyvault_secret_show(
        self,
        keyvault_name: Annotated[str, "The Keyvault name"],
        secret_name: Annotated[str, "The Secret name"],
    ) -> str:
        """Retrieves details of a specific secret in the specified keyvault using Azure SDK."""
        credential = DefaultAzureCredential()
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        secret_client = SecretClient(vault_url=vault_url, credential=credential)
        secret = secret_client.get_secret(secret_name)
        return {
            "id": secret.id,
            "name": secret.name,
            "value": secret.value,
            "enabled": secret.properties.enabled,
            "created_on": (
                secret.properties.created_on.isoformat()
                if secret.properties.created_on
                else None
            ),
            "updated_on": (
                secret.properties.updated_on.isoformat()
                if secret.properties.updated_on
                else None
            ),
            "expires_on": (
                secret.properties.expires_on.isoformat()
                if secret.properties.expires_on
                else None
            ),
        }

    def azure_fd_custom_domains(
        self,
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Custom Domains in the specified resource group using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        custom_domains = cdn_client.afd_custom_domains.list_by_profile(
            resource_group_name=resource_group,
            profile_name=profile,
        )
        cd_list = [cd.as_dict() for cd in custom_domains]
        return json.dumps(cd_list)

    def azure_fd_custom_domain_show(
        self,
        domain_name: Annotated[str, "The Custom Domain name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Custom Domain using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        cd = cdn_client.afd_custom_domains.get(
            resource_group_name=resource_group,
            profile_name=profile,
            custom_domain_name=domain_name,
        )
        return json.dumps(cd.as_dict())

    def azure_fd_endpoints(
        self,
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Endpoints of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        endpoints = cdn_client.afd_endpoints.list_by_profile(
            resource_group_name=resource_group,
            profile_name=profile,
        )
        ep_list = [ep.as_dict() for ep in endpoints]
        return json.dumps(ep_list)

    def azure_fd_endpoint_show(
        self,
        endpoint_name: Annotated[str, "The Endpoint name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Endpoint of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        ep = cdn_client.afd_endpoints.get(
            resource_group_name=resource_group,
            profile_name=profile,
            endpoint_name=endpoint_name,
        )
        return json.dumps(ep.as_dict())

    def azure_fd_origin_group_list(
        self,
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Origin Groups of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        origins = cdn_client.afd_origin_groups.list_by_profile(
            resource_group_name=resource_group,
            profile_name=profile,
        )
        og_list = [origin.as_dict() for origin in origins]
        return json.dumps(og_list)

    def azure_fd_origin_group_show(
        self,
        origin_group_name: Annotated[str, "The Origin Group name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Origin Group of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        origin_group = cdn_client.afd_origin_groups.get(
            resource_group_name=resource_group,
            profile_name=profile,
            origin_group_name=origin_group_name,
        )
        return json.dumps(origin_group.as_dict())

    def azure_fd_origin_list(
        self,
        profile: Annotated[str, "The Front Door profile name"] = "",
        origin_group_name: Annotated[str, "The Origin Group name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Origins of a Front Door Origin Group using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        origins = cdn_client.afd_origins.list_by_origin_group(
            resource_group_name=resource_group,
            profile_name=profile,
            origin_group_name=origin_group_name,
        )
        origin_list = [origin.as_dict() for origin in origins]
        return json.dumps(origin_list)

    def azure_fd_origin_show(
        self,
        origin_name: Annotated[str, "The Origin name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        origin_group_name: Annotated[str, "The Origin Group name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Origin of a Front Door Origin Group using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        origin = cdn_client.afd_origins.get(
            resource_group_name=resource_group,
            profile_name=profile,
            origin_group_name=origin_group_name,
            origin_name=origin_name,
        )
        return json.dumps(origin.as_dict())

    def azure_fd_route_list(
        self,
        endpoint_name: Annotated[str, "The Endpoint name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Routes of a Front Door Endpoint using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        routes = cdn_client.routes.list_by_endpoint(
            resource_group_name=resource_group,
            profile_name=profile,
            endpoint_name=endpoint_name,
        )
        route_list = [route.as_dict() for route in routes]
        return json.dumps(route_list)

    def azure_fd_route_show(
        self,
        route_name: Annotated[str, "The Route name"],
        endpoint_name: Annotated[str, "The Endpoint name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Route of a Front Door Endpoint using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        route = cdn_client.routes.get(
            resource_group_name=resource_group,
            profile_name=profile,
            endpoint_name=endpoint_name,
            route_name=route_name,
        )
        return json.dumps(route.as_dict())

    def azure_fd_ruleset_list(
        self,
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Rulesets of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        rulesets = cdn_client.rule_sets.list_by_profile(
            resource_group_name=resource_group,
            profile_name=profile,
        )
        rs_list = [rs.as_dict() for rs in rulesets]
        return json.dumps(rs_list)

    def azure_fd_ruleset_show(
        self,
        ruleset_name: Annotated[str, "The Ruleset name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Ruleset of a Front Door profile using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        rs = cdn_client.rule_sets.get(
            resource_group_name=resource_group,
            profile_name=profile,
            rule_set_name=ruleset_name,
        )
        return json.dumps(rs.as_dict())

    def azure_fd_rule_list(
        self,
        ruleset_name: Annotated[str, "The Ruleset name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves the Rules of a Front Door Ruleset using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        rules = cdn_client.rules.list_by_rule_set(
            resource_group_name=resource_group,
            profile_name=profile,
            rule_set_name=ruleset_name,
        )
        rule_list = [rule.as_dict() for rule in rules]
        return json.dumps(rule_list)

    def azure_fd_rule_show(
        self,
        rule_name: Annotated[str, "The Rule name"],
        ruleset_name: Annotated[str, "The Ruleset name"],
        profile: Annotated[str, "The Front Door profile name"] = "",
        resource_group: Annotated[str, "The resource group name"] = "",
        subscription_id: Annotated[str, "The subscription ID"] = "",
    ) -> str:
        """Retrieves details of a specific Rule of a Front Door Ruleset using Azure SDK."""
        credential = DefaultAzureCredential()
        cdn_client = CdnManagementClient(credential, subscription_id)
        rule = cdn_client.rules.get(
            resource_group_name=resource_group,
            profile_name=profile,
            rule_set_name=ruleset_name,
            rule_name=rule_name,
        )
        return json.dumps(rule.as_dict())

    def azure_log_analytics_query_templates(self) -> str:
        """Lists all available Kusto queries for Log Analytics."""
        return json.dumps(self.kusto_query_loader.get_all_queries_as_dicts())

    def azure_log_analytics_run_query(
        self,
        workspace_id: Annotated[str, "The Log Analytics workspace ID"],
        query: Annotated[str, "The Kusto query to run"],
    ) -> str:
        """Runs a Kusto query against the specified Log Analytics workspace."""
        credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        response = client.query_workspace(
            workspace_id=workspace_id, query=query, timespan=None
        )
        results = []
        if response.status == LogsQueryStatus.SUCCESS:
            table = response.tables[0]
            results = []
            for row in table.rows:
                results.append(str(row))
            return results
        else:
            return json.dumps({"error": response.error.message})

    def get_tools(self) -> list[FunctionTool]:
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
            self.azure_fd_custom_domains,
            self.azure_fd_custom_domain_show,
            self.azure_fd_endpoints,
            self.azure_fd_endpoint_show,
            self.azure_fd_origin_group_list,
            self.azure_fd_origin_group_show,
            self.azure_fd_origin_list,
            self.azure_fd_origin_show,
            self.azure_fd_route_list,
            self.azure_fd_route_show,
            self.azure_fd_ruleset_list,
            self.azure_fd_ruleset_show,
            self.azure_fd_rule_list,
            self.azure_fd_rule_show,
            self.azure_log_analytics_query_templates,
            self.azure_log_analytics_run_query,
        ]
