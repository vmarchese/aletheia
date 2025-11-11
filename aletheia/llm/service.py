
from agent_framework.azure import AzureAIAgentClient
from azure.identity import AzureCliCredential

from aletheia.config import Config


class LLMService:
    def __init__(self, config: Config):
        self.config = config
        """
        self.client = AzureAIAgentClient(
            model_deployment_name=self.config.llm_azure_deployment,
            project_endpoint=self.config.llm_azure_endpoint,
            credential=credential
        )
        """
        self.client = None
