"""
LLM Client selection based on environment variables.
"""

import os

import structlog
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework.openai import OpenAIChatClient
from azure.identity import AzureCliCredential

try:
    from agent_framework_bedrock import BedrockChatClient

    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False

logger = structlog.get_logger(__name__)


class LLMClient:
    """Selects and initializes the appropriate LLM client based on environment variables."""

    def __init__(self, agent_name: str = None):
        self._client = None
        self.model = None
        self.provider = None
        self.agent_name = agent_name

        # First check for model override for agent
        if self.agent_name:
            if os.environ.get(f"ALETHEIA_{self.agent_name.upper()}_OPENAI_MODEL"):
                self.model = os.environ.get(
                    f"ALETHEIA_{self.agent_name.upper()}_OPENAI_MODEL"
                )
                self._client = OpenAIChatClient(
                    api_key=os.environ.get(
                        f"ALETHEIA_{self.agent_name.upper()}_OPENAI_API_KEY", "none"
                    ),
                    base_url=os.environ.get(
                        f"ALETHEIA_{self.agent_name.upper()}_OPENAI_ENDPOINT"
                    ),
                    model_id=self.model,
                )
                logger.debug(
                    f"LLMClient: Using model override for agent {self.agent_name}: {self.model}"
                )
                self.provider = "openai"
                return

        # Then check for Bedrock
        endpoint = os.environ.get("ALETHEIA_OPENAI_ENDPOINT", "")
        if "bedrock" in endpoint and BEDROCK_AVAILABLE:
            self.model = os.environ.get(
                "ALETHEIA_OPENAI_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0"
            )
            region = endpoint.split(".")[1] if "." in endpoint else "us-east-1"
            self._client = BedrockChatClient(model_id=self.model, region=region)
            self.provider = "bedrock"
        # Then check for missing Azure OpenAI configuration and default to OpenAI
        elif os.environ.get("AZURE_OPENAI_ENDPOINT") is None:
            if os.environ.get("ALETHEIA_OPENAI_ENDPOINT") is not None:
                api_key = os.environ.get("ALETHEIA_OPENAI_API_KEY", "none")
                self.model = os.environ.get("ALETHEIA_OPENAI_MODEL", "gpt-4o")
                self._client = OpenAIChatClient(
                    api_key=api_key,
                    base_url=os.environ.get("ALETHEIA_OPENAI_ENDPOINT"),
                    model_id=self.model,
                )
                self.provider = "openai"
        # Finally, check for Azure OpenAI configuration
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
            if not BEDROCK_AVAILABLE and "bedrock" in os.environ.get(
                "ALETHEIA_OPENAI_ENDPOINT", ""
            ):
                raise ValueError(
                    "Bedrock support requires agent-framework-bedrock. Install with: uv pip install agent-framework-bedrock --pre"
                )
            raise ValueError(
                "No valid LLM configuration found in environment variables."
            )
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
