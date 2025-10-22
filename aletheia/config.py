"""
Configuration management for Aletheia.

Implements multi-level configuration loading with precedence:
1. Environment variables (highest priority)
2. Project config (./.aletheia/config.yaml)
3. User config (~/.aletheia/config.yaml)
4. System config (/etc/aletheia/config.yaml)
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource, PydanticBaseSettingsSource


"""Configuration management for Aletheia.

Implements simplified configuration loading with precedence using Pydantic Settings:
1. Environment variables (highest priority)
2. Project config (./.aletheia/config.yaml)
3. User config (~/.aletheia/config.yaml)
4. System config (/etc/aletheia/config.yaml)
5. .env files
6. Default values
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource, PydanticBaseSettingsSource


class Config(BaseSettings):
    """Complete configuration schema for Aletheia with flat structure."""

    model_config = SettingsConfigDict(
        # Load from .env files in order of precedence (lowest to highest)
        env_file=[
            ".env.defaults",  # Project defaults
            ".env",  # Project-specific
            str(Path.home() / ".aletheia" / ".env"),  # User-specific
        ],
        # Load from YAML files in order of precedence (lowest to highest)
        yaml_file=[
            "/etc/aletheia/config.yaml",  # System-wide
            str(Path.home() / ".aletheia" / "config.yaml"),  # User-specific
            str(Path.cwd() / ".aletheia" / "config.yaml"),  # Project-specific
        ],
        # Environment variable prefix
        env_prefix="ALETHEIA_",
        # Nested environment variables use double underscore
        env_nested_delimiter="__",
        # Case-insensitive environment variables
        case_sensitive=False,
        # Ignore extra fields (like OPENAI_API_KEY that aren't part of config schema)
        extra="ignore",
        # Ignore missing .env files
        env_file_encoding="utf-8",
    )

    # =================================================================
    # LLM Configuration (flat)
    # =================================================================
    
    # Default LLM settings
    llm_default_model: str = Field(default="gpt-4o", description="Default model for all agents")
    llm_base_url: Optional[str] = Field(default=None, description="Base URL for OpenAI-compatible API")
    
    # Azure OpenAI configuration (default for all agents unless overridden)
    llm_use_azure: bool = Field(default=False, description="Use Azure OpenAI by default")
    llm_azure_deployment: Optional[str] = Field(default=None, description="Azure deployment name")
    llm_azure_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint URL")
    llm_azure_api_version: Optional[str] = Field(default=None, description="Azure API version")
    llm_azure_api_key: str = Field(default=None, description="Environment variable for Azure OpenAI API key")
    
    # Prompt templates configuration
    llm_prompt_templates_dir: Optional[str] = Field(default=None, description="Directory containing prompt templates")
    
    # Agent-specific LLM overrides (using Dict for dynamic agent names)
    llm_agents: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Per-agent LLM configuration overrides"
    )

    # =================================================================
    # Data Sources Configuration (flat)
    # =================================================================
    
    # Kubernetes
    kubernetes_context: Optional[str] = Field(default=None, description="Kubernetes context to use")
    kubernetes_namespace: str = Field(default="default", description="Default Kubernetes namespace")
    
    # Prometheus
    prometheus_endpoint: Optional[str] = Field(default=None, description="Prometheus endpoint URL")
    prometheus_credentials_type: Literal["env", "keychain", "encrypted_file"] = Field(
        default="env", description="Prometheus credentials type"
    )
    prometheus_username_env: Optional[str] = Field(default=None, description="Environment variable for Prometheus username")
    prometheus_password_env: Optional[str] = Field(default=None, description="Environment variable for Prometheus password")
    prometheus_credentials_file: Optional[str] = Field(default=None, description="Path to Prometheus credentials file")
    prometheus_timeout_seconds: int = Field( default=10, ge=1, description="Timeout for Prometheus requests in seconds")
    
    # Elasticsearch
    elasticsearch_endpoint: Optional[str] = Field(default=None, description="Elasticsearch endpoint URL")
    elasticsearch_credentials_type: Literal["env", "keychain", "encrypted_file"] = Field(
        default="env", description="Elasticsearch credentials type"
    )
    elasticsearch_username_env: Optional[str] = Field(default=None, description="Environment variable for Elasticsearch username")
    elasticsearch_password_env: Optional[str] = Field(default=None, description="Environment variable for Elasticsearch password")
    elasticsearch_credentials_file: Optional[str] = Field(default=None, description="Path to Elasticsearch credentials file")

    # =================================================================
    # UI Configuration (flat)
    # =================================================================
    
    ui_confirmation_level: Literal["verbose", "normal", "minimal"] = Field(
        default="normal", description="Level of confirmation prompts"
    )
    ui_agent_visibility: bool = Field(default=False, description="Show agent execution details")

    # =================================================================
    # Session Configuration (flat)
    # =================================================================
    
    session_auto_save_interval: int = Field(
        default=300, ge=0, description="Auto-save interval in seconds (0 to disable)"
    )
    session_default_time_window: str = Field(
        default="2h", description="Default time window for queries"
    )

    # =================================================================
    # Encryption Configuration (flat)
    # =================================================================
    
    encryption_algorithm: Literal["Fernet"] = Field(
        default="Fernet", description="Encryption algorithm to use"
    )
    encryption_pbkdf2_iterations: int = Field(
        default=100000, ge=10000, description="PBKDF2 iterations for key derivation"
    )
    encryption_salt_size: int = Field(
        default=32, ge=16, description="Salt size in bytes"
    )

    # =================================================================
    # Sampling Configuration (flat)
    # =================================================================
    
    # Log sampling
    sampling_logs_default_sample_size: int = Field(
        default=200, ge=1, description="Default log sample size"
    )
    sampling_logs_always_include_levels: List[str] = Field(
        default_factory=lambda: ["ERROR", "FATAL", "CRITICAL"],
        description="Log levels to always include in samples"
    )
    
    # Metric sampling
    sampling_metrics_default_resolution: str = Field(
        default="1m", description="Default metric resolution"
    )
    sampling_metrics_auto_adjust: bool = Field(
        default=True, description="Auto-adjust metric resolution based on time range"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include YAML support."""
        yaml_settings = YamlConfigSettingsSource(settings_cls)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_settings,
            file_secret_settings,
        )
    
    # =================================================================
    # Helper Methods for Backward Compatibility
    # =================================================================
    
    def get_agent_llm_config(self, agent_name: str) -> Dict[str, Any]:
        """Get LLM configuration for a specific agent.
        
        Returns a dictionary with agent-specific overrides merged with defaults.
        """
        # Start with defaults
        config = {
            "model": self.llm_default_model,
            "base_url": self.llm_base_url,
            "api_key_env": self.llm_api_key_env,
            "use_azure": self.llm_use_azure,
            "azure_deployment": self.llm_azure_deployment,
            "azure_endpoint": self.llm_azure_endpoint,
            "azure_api_version": self.llm_azure_api_version,
        }
        
        # Override with agent-specific config if present
        if agent_name in self.llm_agents:
            config.update(self.llm_agents[agent_name])
        
        return config
    
    def get_kubernetes_config(self) -> Dict[str, Any]:
        """Get Kubernetes configuration."""
        return {
            "context": self.kubernetes_context,
            "namespace": self.kubernetes_namespace,
        }
    
    def get_prometheus_config(self) -> Dict[str, Any]:
        """Get Prometheus configuration."""
        return {
            "endpoint": self.prometheus_endpoint,
            "credentials": {
                "type": self.prometheus_credentials_type,
                "username_env": self.prometheus_username_env,
                "password_env": self.prometheus_password_env,
                "file_path": self.prometheus_credentials_file,
            }
        }
    
    def get_elasticsearch_config(self) -> Dict[str, Any]:
        """Get Elasticsearch configuration."""
        return {
            "endpoint": self.elasticsearch_endpoint,
            "credentials": {
                "type": self.elasticsearch_credentials_type,
                "username_env": self.elasticsearch_username_env,
                "password_env": self.elasticsearch_password_env,
                "file_path": self.elasticsearch_credentials_file,
            }
        }
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Get UI configuration."""
        return {
            "confirmation_level": self.ui_confirmation_level,
            "agent_visibility": self.ui_agent_visibility,
        }
    
    def get_session_config(self) -> Dict[str, Any]:
        """Get session configuration."""
        return {
            "auto_save_interval": self.session_auto_save_interval,
            "default_time_window": self.session_default_time_window,
        }
    
    def get_encryption_config(self) -> Dict[str, Any]:
        """Get encryption configuration."""
        return {
            "algorithm": self.encryption_algorithm,
            "pbkdf2_iterations": self.encryption_pbkdf2_iterations,
            "salt_size": self.encryption_salt_size,
        }
    
    def get_sampling_config(self) -> Dict[str, Any]:
        """Get sampling configuration."""
        return {
            "logs": {
                "default_sample_size": self.sampling_logs_default_sample_size,
                "always_include_levels": self.sampling_logs_always_include_levels,
            },
            "metrics": {
                "default_resolution": self.sampling_metrics_default_resolution,
                "auto_adjust": self.sampling_metrics_auto_adjust,
            }
        }


def load_config() -> Config:
    """
    Load configuration from all sources with proper precedence.

    Precedence (highest to lowest):
    1. Environment variables (ALETHEIA_*)
    2. Project config (./.aletheia/config.yaml)
    3. User config (~/.aletheia/config.yaml)
    4. System config (/etc/aletheia/config.yaml)
    5. User .env (~/.aletheia/.env)
    6. Project .env (./.env)
    7. Project defaults (./.env.defaults)
    8. Default values

    Returns:
        Config: The loaded and validated configuration

    Examples:
        Basic usage:
        >>> config = load_config()
        >>> print(config.llm_default_model)
        'gpt-4o'

        Environment variable override (flat structure):
        # export ALETHEIA_LLM_DEFAULT_MODEL=gpt-4
        >>> config = load_config()
        >>> print(config.llm_default_model)
        'gpt-4'

        Using .env file (create .env in project root):
        # .env
        ALETHEIA_LLM_DEFAULT_MODEL=gpt-4o-mini
        ALETHEIA_LLM_API_KEY_ENV=OPENAI_API_KEY
        OPENAI_API_KEY=sk-your-key-here

        Using Azure OpenAI via .env:
        # .env
        ALETHEIA_LLM_USE_AZURE=true
        ALETHEIA_LLM_AZURE_DEPLOYMENT=gpt-4o
        ALETHEIA_LLM_AZURE_ENDPOINT=https://your-resource.openai.azure.com/
        AZURE_OPENAI_API_KEY=your-azure-key

        Agent-specific configuration via environment variables:
        # export ALETHEIA_LLM_AGENTS__DATA_FETCHER__MODEL=gpt-4o-mini
        >>> config = load_config()
        >>> agent_config = config.get_agent_llm_config("data_fetcher")
        >>> print(agent_config["model"])
        'gpt-4o-mini'

        Accessing configuration with helper methods:
        >>> config = load_config()
        >>> kubernetes_config = config.get_kubernetes_config()
        >>> print(kubernetes_config["namespace"])
        'default'
    """
    return Config()
