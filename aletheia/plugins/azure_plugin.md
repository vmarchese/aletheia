You have access to the Azure cli to fetch resources on Azure:

- **azure_accounts()**: gets the accounts on Azure for the current user
- **azure_resource_groups(region)**: gets the resource groups for a region (if present)
- **azure_vm(resource_group)**: gets the azure virtual machines in a resource group (if present)
- **azure_vm_show(vm_name,resource_group)**: gets the azure virtual machine details in a resource group (if present)