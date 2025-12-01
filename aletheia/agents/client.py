"""
LLM Client selection based on environment variables.
"""
import os
from agent_framework.openai import OpenAIChatClient
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential


class LLMClient:
    """Selects and initializes the appropriate LLM client based on environment variables."""
    def __init__(self):
        self._client = None
        self.model = None
        self.provider = None
        if os.environ.get("AZURE_OPENAI_ENDPOINT") is None:
            if os.environ.get("ALETHEIA_OPENAI_ENDPOINT") is not None:
                api_key = os.environ.get("ALETHEIA_OPENAI_API_KEY", "none")
                self.model = os.environ.get("ALETHEIA_OPENAI_MODEL", "gpt-4o")
                self._client = OpenAIChatClient(
                    api_key=api_key,
                    base_url=os.environ.get("ALETHEIA_OPENAI_ENDPOINT"),
                    model_id=self.model,
                )
                self.provider = "openai"
        else:
            self.model = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
            self._client = AzureOpenAIChatClient(credential=AzureCliCredential())
            self.provider = "azure"

    def get_client(self):
        """Returns the initialized LLM client.

        Raises:
            ValueError: If no valid LLM configuration is found.

        Returns:
            An instance of the appropriate LLM client.
        """
        if self._client is None:
            raise ValueError("No valid LLM configuration found in environment variables.")
        return self._client

    def get_provider(self):
        """Returns the LLM provider name.

        Returns:
            The name of the LLM provider (e.g., "openai", "azure").
        """
        return self.provider

    def get_model(self):
        """Returns the LLM model name."""
        return self.model
