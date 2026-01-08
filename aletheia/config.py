"""
Configuration management for Aletheia.

Implements multi-level configuration loading with precedence:
1. Explicit values passed to Settings (highest priority)
2. Environment variables (ALETHEIA_*)
3. YAML config file ({user_config_path}/config.yaml)
4. Default values (lowest priority)

Uses platformdirs for standard config directory location.
"""

from enum import Enum
from pathlib import Path
from typing import Literal

import platformdirs
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


def get_config_dir() -> Path:
    """Get the standard configuration directory for Aletheia.

    Returns:
        Path: Platform-specific configuration directory
            - Linux: ~/.config/aletheia
            - macOS: ~/Library/Application Support/aletheia
            - Windows: %LOCALAPPDATA%\\aletheia
    """
    return platformdirs.user_config_path("aletheia")


class CodeAnalyzerType(Enum):
    """Code analyzer options."""

    CLAUDE = "claude"
    COPILOT = "copilot"


class Config(BaseSettings):
    """Complete configuration schema for Aletheia with flat structure."""

    model_config = SettingsConfigDict(
        # Load from YAML config file
        yaml_file=str(get_config_dir() / "config.yaml"),
        # Environment variable prefix
        env_prefix="ALETHEIA_",
        # Case-insensitive environment variables
        case_sensitive=False,
        # Ignore extra fields (like OPENAI_API_KEY that aren't part of config schema)
        extra="ignore",
    )

    # =================================================================
    # Skills configuration
    # =================================================================
    skills_directory: str = Field(
        default_factory=lambda: str(get_config_dir() / "skills"),
        description="Directory containing skill YAML files",
    )

    # =================================================================
    # Commands configuration
    # =================================================================
    commands_directory: str = Field(
        default_factory=lambda: str(get_config_dir() / "commands"),
        description="Directory containing custom command markdown files",
    )
    # =================================================================
    # LLM Configuration (flat)
    # =================================================================

    # Default LLM settings
    llm_default_model: str = Field(
        default="gpt-4o", description="Default model for all agents"
    )
    # UNUSED - Commented out (not used in codebase)
    # llm_base_url: Optional[str] = Field(default=None, description="Base URL for OpenAI-compatible API")
    # llm_use_azure: bool = Field(default=True, description="Use Azure OpenAI by default")
    # llm_prompt_templates_dir: Optional[str] = Field(default=None, description="Directory containing prompt templates")
    # llm_agents: Dict[str, Dict[str, Any]] = Field(
    #     default_factory=dict,
    #     description="Per-agent LLM configuration overrides"
    # )

    cost_per_input_token: float = Field(default=0.0, description="Cost per input token")
    cost_per_output_token: float = Field(
        default=0.0, description="Cost per output token"
    )

    code_analyzer: str = Field(
        default="", description="Code analyzer to use (claude, copilot)"
    )

    llm_temperature: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Default temperature for LLM responses"
    )

    # =================================================================
    # Data Sources Configuration (flat)
    # =================================================================

    # UNUSED - Kubernetes configuration (commented out, not used in codebase)
    # kubernetes_context: Optional[str] = Field(default=None, description="Kubernetes context to use")
    # kubernetes_namespace: str = Field(default="default", description="Default Kubernetes namespace")

    # Prometheus
    prometheus_endpoint: str | None = Field(
        default=None, description="Prometheus endpoint URL"
    )
    prometheus_credentials_type: Literal["env", "keychain", "encrypted_file"] = Field(
        default="env", description="Prometheus credentials type"
    )
    prometheus_timeout_seconds: int = Field(
        default=10, ge=1, description="Timeout for Prometheus requests in seconds"
    )
    # UNUSED - Prometheus credentials (commented out, not used in codebase)
    # prometheus_username_env: Optional[str] = Field(default=None, description="Environment variable for Prometheus username")
    # prometheus_password_env: Optional[str] = Field(default=None, description="Environment variable for Prometheus password")
    # prometheus_credentials_file: Optional[str] = Field(default=None, description="Path to Prometheus credentials file")
    # prometheus_credentials_bearer: Optional[str] = Field(default=None, description="Environment variable for Prometheus bearer token")

    # UNUSED - Elasticsearch configuration (commented out, not used in codebase)
    # elasticsearch_endpoint: Optional[str] = Field(default=None, description="Elasticsearch endpoint URL")
    # elasticsearch_credentials_type: Literal["env", "keychain", "encrypted_file"] = Field(
    #     default="env", description="Elasticsearch credentials type"
    # )
    # elasticsearch_username_env: Optional[str] = Field(default=None, description="Environment variable for Elasticsearch username")
    # elasticsearch_password_env: Optional[str] = Field(default=None, description="Environment variable for Elasticsearch password")
    # elasticsearch_credentials_file: Optional[str] = Field(default=None, description="Path to Elasticsearch credentials file")

    # =================================================================
    # UNUSED CONFIGURATION (commented out for future use)
    # =================================================================

    # UI Configuration
    # ui_confirmation_level: Literal["verbose", "normal", "minimal"] = Field(
    #     default="normal", description="Level of confirmation prompts"
    # )
    # ui_agent_visibility: bool = Field(default=False, description="Show agent execution details")

    # Session Configuration
    # session_auto_save_interval: int = Field(
    #     default=300, ge=0, description="Auto-save interval in seconds (0 to disable)"
    # )
    # session_default_time_window: str = Field(
    #     default="2h", description="Default time window for queries"
    # )

    # Encryption Configuration
    # encryption_algorithm: Literal["Fernet"] = Field(
    #     default="Fernet", description="Encryption algorithm to use"
    # )
    # encryption_pbkdf2_iterations: int = Field(
    #     default=100000, ge=10000, description="PBKDF2 iterations for key derivation"
    # )
    # encryption_salt_size: int = Field(
    #     default=32, ge=16, description="Salt size in bytes"
    # )

    # Sampling Configuration
    # sampling_logs_default_sample_size: int = Field(
    #     default=200, ge=1, description="Default log sample size"
    # )
    # sampling_logs_always_include_levels: List[str] = Field(
    #     default_factory=lambda: ["ERROR", "FATAL", "CRITICAL"],
    #     description="Log levels to always include in samples"
    # )
    # sampling_metrics_default_resolution: str = Field(
    #     default="1m", description="Default metric resolution"
    # )
    # sampling_metrics_auto_adjust: bool = Field(
    #     default=True, description="Auto-adjust metric resolution based on time range"
    # )

    # =================================================================
    # Temp folder
    # =================================================================
    temp_folder: str = Field(
        default="./.aletheia",
        description="Temporary folder for storing intermediate files",
    )

    # =================================================================
    # MCP Servers Configuration (flat)
    # =================================================================
    mcp_servers_yaml: str | None = Field(
        default=None, description="Path to MCP servers YAML configuration file"
    )

    # =================================================================
    # Custom Instructions folder
    # =================================================================
    custom_instructions_dir: str | None = Field(
        default_factory=lambda: str(get_config_dir() / "instructions"),
        description="Directory containing custom instructions for agents",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources with proper precedence.

        Precedence (highest to lowest):
        1. Explicit values passed to Settings (init_settings)
        2. Environment variables (env_settings)
        3. YAML config file (yaml_settings)
        """
        yaml_settings = YamlConfigSettingsSource(settings_cls)
        return (
            init_settings,  # 1. Explicit values (highest)
            env_settings,  # 2. Environment variables
            yaml_settings,  # 3. YAML config file
            # Removed: dotenv_settings, file_secret_settings
        )

    # =================================================================
    # UNUSED HELPER METHODS (commented out - never called in codebase)
    # =================================================================

    # def get_agent_llm_config(self, agent_name: str) -> Dict[str, Any]:
    #     """Get LLM configuration for a specific agent.
    #
    #     Returns a dictionary with agent-specific overrides merged with defaults.
    #     NOTE: This method references non-existent fields (llm_api_key_env, llm_azure_*)
    #     """
    #     # Start with defaults
    #     config = {
    #         "model": self.llm_default_model,
    #         "base_url": self.llm_base_url,
    #         "api_key_env": self.llm_api_key_env,
    #         "use_azure": self.llm_use_azure,
    #         "azure_deployment": self.llm_azure_deployment,
    #         "azure_endpoint": self.llm_azure_endpoint,
    #         "azure_api_version": self.llm_azure_api_version,
    #     }
    #
    #     # Override with agent-specific config if present
    #     if agent_name in self.llm_agents:
    #         config.update(self.llm_agents[agent_name])
    #
    #     return config

    # def get_kubernetes_config(self) -> Dict[str, Any]:
    #     """Get Kubernetes configuration."""
    #     return {
    #         "context": self.kubernetes_context,
    #         "namespace": self.kubernetes_namespace,
    #     }

    # def get_prometheus_config(self) -> Dict[str, Any]:
    #     """Get Prometheus configuration."""
    #     return {
    #         "endpoint": self.prometheus_endpoint,
    #         "credentials": {
    #             "type": self.prometheus_credentials_type,
    #             "username_env": self.prometheus_username_env,
    #             "password_env": self.prometheus_password_env,
    #             "file_path": self.prometheus_credentials_file,
    #         }
    #     }

    # def get_elasticsearch_config(self) -> Dict[str, Any]:
    #     """Get Elasticsearch configuration."""
    #     return {
    #         "endpoint": self.elasticsearch_endpoint,
    #         "credentials": {
    #             "type": self.elasticsearch_credentials_type,
    #             "username_env": self.elasticsearch_username_env,
    #             "password_env": self.elasticsearch_password_env,
    #             "file_path": self.elasticsearch_credentials_file,
    #         }
    #     }

    # def get_ui_config(self) -> Dict[str, Any]:
    #     """Get UI configuration."""
    #     return {
    #         "confirmation_level": self.ui_confirmation_level,
    #         "agent_visibility": self.ui_agent_visibility,
    #     }

    # def get_session_config(self) -> Dict[str, Any]:
    #     """Get session configuration."""
    #     return {
    #         "auto_save_interval": self.session_auto_save_interval,
    #         "default_time_window": self.session_default_time_window,
    #     }

    # def get_encryption_config(self) -> Dict[str, Any]:
    #     """Get encryption configuration."""
    #     return {
    #         "algorithm": self.encryption_algorithm,
    #         "pbkdf2_iterations": self.encryption_pbkdf2_iterations,
    #         "salt_size": self.encryption_salt_size,
    #     }

    # def get_sampling_config(self) -> Dict[str, Any]:
    #     """Get sampling configuration."""
    #     return {
    #         "logs": {
    #             "default_sample_size": self.sampling_logs_default_sample_size,
    #             "always_include_levels": self.sampling_logs_always_include_levels,
    #         },
    #         "metrics": {
    #             "default_resolution": self.sampling_metrics_default_resolution,
    #             "auto_adjust": self.sampling_metrics_auto_adjust,
    #         }
    #     }


def load_config() -> Config:
    """
    Load configuration from all sources with proper precedence.

    Precedence (highest to lowest):
    1. Explicit values passed to Settings
    2. Environment variables (ALETHEIA_*)
    3. YAML config file (user_config_path/aletheia/config.yaml)
    4. Default values

    Config file location (using platformdirs):
    - Linux: ~/.config/aletheia/config.yaml
    - macOS: ~/Library/Application Support/aletheia/config.yaml
    - Windows: %LOCALAPPDATA%\\aletheia\\config.yaml

    Returns:
        Config: The loaded and validated configuration

    Examples:
        Basic usage:
        >>> config = load_config()
        >>> print(config.llm_default_model)
        'gpt-4o'

        Environment variable override:
        >>> import os
        >>> os.environ['ALETHEIA_LLM_DEFAULT_MODEL'] = 'gpt-4'
        >>> config = load_config()
        >>> print(config.llm_default_model)
        'gpt-4'

        YAML configuration file:
        Create config.yaml in your config directory:
        # Linux: ~/.config/aletheia/config.yaml
        # macOS: ~/Library/Application Support/aletheia/config.yaml
        # Windows: %LOCALAPPDATA%\\aletheia\\config.yaml

        llm_default_model: gpt-4o-mini
        llm_temperature: 0.5
        prometheus_endpoint: https://prometheus.example.com
        skills_directory: /custom/path/to/skills

        Directory configuration:
        >>> config = load_config()
        >>> print(config.skills_directory)
        '/home/user/.config/aletheia/skills'  # On Linux
        >>> print(config.custom_instructions_dir)
        '/home/user/.config/aletheia/instructions'  # On Linux

        Overriding defaults via environment:
        >>> os.environ['ALETHEIA_SKILLS_DIRECTORY'] = '/my/custom/skills'
        >>> config = load_config()
        >>> print(config.skills_directory)
        '/my/custom/skills'
    """
    return Config()
