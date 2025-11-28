You have access to the Azure cli to fetch resources on Azure:

- **azure_accounts()**: gets the accounts on Azure for the current user
- **azure_resource_groups(region)**: gets the resource groups for a region (if present)
- **azure_vms(resource_group)**: gets the azure virtual machines in a resource group (if present)
- **azure_vm_show(vm_name,resource_group)**: gets the azure virtual machine details in a resource group (if present)
- **azure_storage_accounts(resource_group)**: gets the azure storage account in a resource group (if present)
- **azure_storage_account_show(name,resource_group)**: gets the azure storage account details in a resource group (if present)
- **azure_keyvaults(resource_group)**: gets the azure Keyvaults list in a resource group (if present)
- **azure_keyvault_show(keyvault_name, resource_group)**: gets the azure Keyvault details in a resource group (if present)
- **azure_keyvault_keys(keyvault_name, resource_group)**: gets the azure Keyvaults Keys list for a Keyvault in a resource group (if present)
- **azure_keyvault_key_show(keyvault_name, key_name, resource_group)**: gets the azure Keyvault Key details for a Keyvault in a resource group (if present)
- **azure_keyvault_secrets(keyvault_name, resource_group)**: list the secrets in an Azure KeyVault in a  resource group (if present)
- **azure_keyvault_secret_show(keyvault_name, secret_name, resource_group)**: shows a secret in an Azure KeyVault in a  resource group (if present)