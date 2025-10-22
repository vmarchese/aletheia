from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from aletheia.config import Config

class LLMService:
    def __init__(self, config: Config):
        self.config = config
        self.client = AzureChatCompletion(
            deployment_name=self.config.llm_azure_deployment,
            api_version=self.config.llm_azure_api_version,
            endpoint=self.config.llm_azure_endpoint,
            api_key=self.config.llm_azure_api_key
        )
