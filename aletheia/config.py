"""
Configuration management for Aletheia.

Implements multi-level configuration loading with precedence:
1. Environment variables (highest priority)
2. Project config (./.aletheia/config.yaml)
3. User config (~/.aletheia/config.yaml)
4. System config (/etc/aletheia/config.yaml)
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class CredentialsConfig(BaseModel):
    """Configuration for credentials management."""

    type: Literal["env", "keychain", "encrypted_file"] = "env"
    username_env: Optional[str] = None
    password_env: Optional[str] = None
    file_path: Optional[str] = None


class KubernetesConfig(BaseModel):
    """Kubernetes data source configuration."""

    context: Optional[str] = None
    namespace: str = "default"


class ElasticsearchConfig(BaseModel):
    """Elasticsearch data source configuration."""

    endpoint: Optional[str] = None
    credentials: CredentialsConfig = Field(default_factory=CredentialsConfig)


class PrometheusConfig(BaseModel):
    """Prometheus data source configuration."""

    endpoint: Optional[str] = None
    credentials: CredentialsConfig = Field(default_factory=CredentialsConfig)


class DataSourcesConfig(BaseModel):
    """Configuration for all data sources."""

    kubernetes: KubernetesConfig = Field(default_factory=KubernetesConfig)
    elasticsearch: ElasticsearchConfig = Field(default_factory=ElasticsearchConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)


class AgentLLMConfig(BaseModel):
    """LLM configuration for a specific agent."""

    model: str = "gpt-4o"
    base_url: Optional[str] = None
    
    # Azure OpenAI configuration
    use_azure: bool = False
    azure_deployment: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_api_version: Optional[str] = None


class LLMConfig(BaseModel):
    """LLM configuration for all agents."""

    default_model: str = "gpt-4o"
    base_url: Optional[str] = None
    api_key_env: str = "OPENAI_API_KEY"
    agents: Dict[str, AgentLLMConfig] = Field(default_factory=dict)
    
    # Azure OpenAI configuration (default for all agents unless overridden)
    use_azure: bool = False
    azure_deployment: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_api_version: Optional[str] = None

    def get_agent_config(self, agent_name: str) -> AgentLLMConfig:
        """Get LLM configuration for a specific agent."""
        if agent_name in self.agents:
            return self.agents[agent_name]
        return AgentLLMConfig(model=self.default_model)


class UIConfig(BaseModel):
    """User interface configuration."""

    confirmation_level: Literal["verbose", "normal", "minimal"] = "normal"
    default_mode: Literal["guided", "conversational"] = "guided"
    agent_visibility: bool = False


class SessionConfig(BaseModel):
    """Session management configuration."""

    auto_save_interval: int = Field(default=300, ge=0)
    default_time_window: str = "2h"


class EncryptionConfig(BaseModel):
    """Encryption configuration."""

    algorithm: Literal["Fernet"] = "Fernet"
    pbkdf2_iterations: int = Field(default=100000, ge=10000)
    salt_size: int = Field(default=32, ge=16)


class LogSamplingConfig(BaseModel):
    """Log sampling configuration."""

    default_sample_size: int = Field(default=200, ge=1)
    always_include_levels: List[str] = Field(
        default_factory=lambda: ["ERROR", "FATAL", "CRITICAL"]
    )


class MetricSamplingConfig(BaseModel):
    """Metric sampling configuration."""

    default_resolution: str = "1m"
    auto_adjust: bool = True


class SamplingConfig(BaseModel):
    """Sampling configuration for data collection."""

    logs: LogSamplingConfig = Field(default_factory=LogSamplingConfig)
    metrics: MetricSamplingConfig = Field(default_factory=MetricSamplingConfig)


class ConfigSchema(BaseModel):
    """Complete configuration schema for Aletheia."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)


class ConfigLoader:
    """
    Multi-level configuration loader with precedence.

    Loads configuration from multiple sources in order of precedence:
    1. Environment variables (highest)
    2. Project config (./.aletheia/config.yaml)
    3. User config (~/.aletheia/config.yaml)
    4. System config (/etc/aletheia/config.yaml)
    """

    # Configuration file locations in order of precedence (lowest to highest)
    CONFIG_PATHS = [
        Path("/etc/aletheia/config.yaml"),  # System-wide
        Path.home() / ".aletheia" / "config.yaml",  # User-specific
        Path.cwd() / ".aletheia" / "config.yaml",  # Project-specific
    ]

    def __init__(self):
        """Initialize the configuration loader."""
        self._config: Optional[ConfigSchema] = None

    def load(self) -> ConfigSchema:
        """
        Load configuration from all sources with proper precedence.

        Returns:
            ConfigSchema: The merged configuration
        """
        # Start with default configuration
        config_dict: Dict[str, Any] = {}

        # Load from files in order of precedence (lowest to highest)
        for config_path in self.CONFIG_PATHS:
            if config_path.exists():
                file_config = self._load_yaml_file(config_path)
                config_dict = self._deep_merge(config_dict, file_config)

        # Apply environment variable overrides (highest precedence)
        config_dict = self._apply_env_overrides(config_dict)

        # Validate and create schema
        self._config = ConfigSchema(**config_dict)
        return self._config

    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.

        Args:
            path: Path to the YAML file

        Returns:
            Dict containing the configuration
        """
        try:
            with open(path, "r") as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except Exception as e:
            # Log warning but don't fail - config file might be malformed
            print(f"Warning: Failed to load config from {path}: {e}")
            return {}

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with override taking precedence.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration.

        Environment variables follow the pattern: ALETHEIA_<SECTION>_<KEY>
        Example: ALETHEIA_LLM_DEFAULT_MODEL=gpt-4

        Args:
            config: Base configuration dictionary

        Returns:
            Configuration with environment overrides applied
        """
        env_prefix = "ALETHEIA_"

        # Common environment variable mappings
        env_mappings = {
            "ALETHEIA_LLM_DEFAULT_MODEL": ("llm", "default_model"),
            "ALETHEIA_LLM_API_KEY_ENV": ("llm", "api_key_env"),
            "ALETHEIA_UI_CONFIRMATION_LEVEL": ("ui", "confirmation_level"),
            "ALETHEIA_UI_DEFAULT_MODE": ("ui", "default_mode"),
            "ALETHEIA_UI_AGENT_VISIBILITY": ("ui", "agent_visibility"),
            "ALETHEIA_SESSION_AUTO_SAVE_INTERVAL": ("session", "auto_save_interval"),
            "ALETHEIA_SESSION_DEFAULT_TIME_WINDOW": ("session", "default_time_window"),
            "ALETHEIA_ENCRYPTION_PBKDF2_ITERATIONS": ("encryption", "pbkdf2_iterations"),
            "ALETHEIA_ENCRYPTION_SALT_SIZE": ("encryption", "salt_size"),
            "ALETHEIA_KUBERNETES_CONTEXT": ("data_sources", "kubernetes", "context"),
            "ALETHEIA_KUBERNETES_NAMESPACE": ("data_sources", "kubernetes", "namespace"),
            "ALETHEIA_ELASTICSEARCH_ENDPOINT": ("data_sources", "elasticsearch", "endpoint"),
            "ALETHEIA_PROMETHEUS_ENDPOINT": ("data_sources", "prometheus", "endpoint"),
        }

        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(config, path, self._convert_env_value(value))

        return config

    def _set_nested_value(
        self, config: Dict[str, Any], path: tuple, value: Any
    ) -> None:
        """
        Set a nested value in a dictionary using a path tuple.

        Args:
            config: Configuration dictionary to modify
            path: Tuple of keys representing the path
            value: Value to set
        """
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string to appropriate Python type.

        Args:
            value: String value from environment variable

        Returns:
            Converted value (int, bool, or str)
        """
        # Convert boolean strings
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Try to convert to int
        try:
            return int(value)
        except ValueError:
            pass

        # Return as string
        return value

    def get_config(self) -> ConfigSchema:
        """
        Get the loaded configuration.

        Returns:
            ConfigSchema: The loaded configuration

        Raises:
            RuntimeError: If configuration has not been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def reload(self) -> ConfigSchema:
        """
        Reload configuration from all sources.

        Returns:
            ConfigSchema: The reloaded configuration
        """
        self._config = None
        return self.load()
