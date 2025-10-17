"""
Unit tests for configuration management.

Tests the multi-level configuration system including:
- Configuration schema validation
- Config loading from multiple sources
- Precedence order
- Environment variable overrides
- Deep merging of configurations
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from aletheia.config import (
    ConfigLoader,
    ConfigSchema,
    CredentialsConfig,
    DataSourcesConfig,
    ElasticsearchConfig,
    EncryptionConfig,
    KubernetesConfig,
    LLMConfig,
    LogSamplingConfig,
    MetricSamplingConfig,
    PrometheusConfig,
    SamplingConfig,
    SessionConfig,
    UIConfig,
)


class TestConfigSchema:
    """Test configuration schema validation."""

    def test_default_config(self):
        """Test that default configuration is valid."""
        config = ConfigSchema()

        assert config.llm.default_model == "gpt-4o"
        assert config.llm.api_key_env == "OPENAI_API_KEY"
        assert config.ui.confirmation_level == "normal"
        assert config.ui.default_mode == "guided"
        assert config.session.auto_save_interval == 300
        assert config.encryption.pbkdf2_iterations == 100000

    def test_llm_config(self):
        """Test LLM configuration."""
        config = LLMConfig(
            default_model="gpt-4",
            api_key_env="CUSTOM_API_KEY",
        )

        assert config.default_model == "gpt-4"
        assert config.api_key_env == "CUSTOM_API_KEY"

    def test_llm_agent_config(self):
        """Test per-agent LLM configuration."""
        config = LLMConfig(
            default_model="gpt-4o",
            agents={
                "orchestrator": {"model": "gpt-4o"},
                "data_fetcher": {"model": "gpt-4o-mini"},
            },
        )

        assert config.get_agent_config("orchestrator").model == "gpt-4o"
        assert config.get_agent_config("data_fetcher").model == "gpt-4o-mini"
        # Non-existent agent should use default
        assert config.get_agent_config("unknown").model == "gpt-4o"

    def test_llm_base_url_default(self):
        """Test default base_url configuration."""
        config = LLMConfig(
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1"
        )
        
        assert config.base_url == "https://api.openai.com/v1"
        # Agent without specific base_url gets None (uses SDK default)
        assert config.get_agent_config("unknown").base_url is None

    def test_llm_base_url_agent_specific(self):
        """Test agent-specific base_url configuration."""
        config = LLMConfig(
            default_model="gpt-4o",
            base_url="https://api.openai.com/v1",
            agents={
                "data_fetcher": {
                    "model": "gpt-4o",
                    "base_url": "https://custom-endpoint.example.com/v1"
                },
                "pattern_analyzer": {
                    "model": "gpt-4o-mini"
                    # No base_url - should inherit from default via SK initialization
                }
            }
        )
        
        # Agent with specific base_url
        assert config.get_agent_config("data_fetcher").base_url == "https://custom-endpoint.example.com/v1"
        # Agent without specific base_url gets None (handled by SK initialization)
        assert config.get_agent_config("pattern_analyzer").base_url is None
        # Unknown agent gets None
        assert config.get_agent_config("unknown").base_url is None

    def test_llm_base_url_azure_example(self):
        """Test base_url configuration for Azure OpenAI."""
        config = LLMConfig(
            default_model="gpt-4",
            base_url="https://my-resource.openai.azure.com/openai/deployments/gpt-4"
        )
        
        assert config.base_url == "https://my-resource.openai.azure.com/openai/deployments/gpt-4"

    def test_credentials_config(self):
        """Test credentials configuration."""
        # Environment credentials
        cred1 = CredentialsConfig(
            type="env", username_env="ES_USER", password_env="ES_PASS"
        )
        assert cred1.type == "env"

        # Keychain credentials
        cred2 = CredentialsConfig(type="keychain")
        assert cred2.type == "keychain"

        # File-based credentials
        cred3 = CredentialsConfig(type="encrypted_file", file_path="/path/to/creds")
        assert cred3.type == "encrypted_file"
        assert cred3.file_path == "/path/to/creds"

    def test_data_sources_config(self):
        """Test data sources configuration."""
        config = DataSourcesConfig(
            kubernetes=KubernetesConfig(context="prod-eu", namespace="commerce"),
            elasticsearch=ElasticsearchConfig(
                endpoint="https://es.example.com",
                credentials=CredentialsConfig(
                    type="env", username_env="ES_USER", password_env="ES_PASS"
                ),
            ),
            prometheus=PrometheusConfig(endpoint="https://prom.example.com"),
        )

        assert config.kubernetes.context == "prod-eu"
        assert config.kubernetes.namespace == "commerce"
        assert config.elasticsearch.endpoint == "https://es.example.com"
        assert config.prometheus.endpoint == "https://prom.example.com"

    def test_ui_config(self):
        """Test UI configuration."""
        config = UIConfig(
            confirmation_level="verbose",
            default_mode="conversational",
            agent_visibility=True,
        )

        assert config.confirmation_level == "verbose"
        assert config.default_mode == "conversational"
        assert config.agent_visibility is True

    def test_session_config(self):
        """Test session configuration."""
        config = SessionConfig(auto_save_interval=600, default_time_window="4h")

        assert config.auto_save_interval == 600
        assert config.default_time_window == "4h"

    def test_encryption_config(self):
        """Test encryption configuration."""
        config = EncryptionConfig(
            algorithm="Fernet", pbkdf2_iterations=200000, salt_size=64
        )

        assert config.algorithm == "Fernet"
        assert config.pbkdf2_iterations == 200000
        assert config.salt_size == 64

    def test_encryption_config_validation(self):
        """Test that encryption config validates iterations."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater than or equal to 10000"):
            EncryptionConfig(pbkdf2_iterations=5000)

    def test_sampling_config(self):
        """Test sampling configuration."""
        config = SamplingConfig(
            logs=LogSamplingConfig(
                default_sample_size=500,
                always_include_levels=["ERROR", "CRITICAL", "FATAL"],
            ),
            metrics=MetricSamplingConfig(default_resolution="5m", auto_adjust=False),
        )

        assert config.logs.default_sample_size == 500
        assert "ERROR" in config.logs.always_include_levels
        assert config.metrics.default_resolution == "5m"
        assert config.metrics.auto_adjust is False


class TestConfigLoader:
    """Test configuration loading and precedence."""

    def test_load_default_config(self):
        """Test loading with no config files present."""
        loader = ConfigLoader()
        config = loader.load()

        assert isinstance(config, ConfigSchema)
        assert config.llm.default_model == "gpt-4o"
        assert config.ui.confirmation_level == "normal"

    def test_load_from_yaml_file(self, tmp_path):
        """Test loading configuration from a YAML file."""
        # Create a temporary config file
        config_file = tmp_path / "config.yaml"
        config_data = {
            "llm": {"default_model": "gpt-4", "api_key_env": "MY_API_KEY"},
            "ui": {"confirmation_level": "verbose"},
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Override CONFIG_PATHS to use our temp file
        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [config_file]

        try:
            config = loader.load()

            assert config.llm.default_model == "gpt-4"
            assert config.llm.api_key_env == "MY_API_KEY"
            assert config.ui.confirmation_level == "verbose"
            # Other fields should have defaults
            assert config.ui.default_mode == "guided"
        finally:
            loader.CONFIG_PATHS = original_paths

    def test_config_file_precedence(self, tmp_path):
        """Test that configuration files are loaded in correct precedence order."""
        # Create multiple config files
        system_config = tmp_path / "system.yaml"
        user_config = tmp_path / "user.yaml"
        project_config = tmp_path / "project.yaml"

        # System config (lowest precedence)
        with open(system_config, "w") as f:
            yaml.dump(
                {
                    "llm": {"default_model": "gpt-3.5-turbo"},
                    "ui": {"confirmation_level": "normal"},
                },
                f,
            )

        # User config (medium precedence)
        with open(user_config, "w") as f:
            yaml.dump(
                {"llm": {"default_model": "gpt-4"}, "ui": {"default_mode": "conversational"}},
                f,
            )

        # Project config (high precedence)
        with open(project_config, "w") as f:
            yaml.dump({"llm": {"default_model": "gpt-4o"}}, f)

        # Override CONFIG_PATHS
        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [system_config, user_config, project_config]

        try:
            config = loader.load()

            # Project config should override (highest precedence)
            assert config.llm.default_model == "gpt-4o"
            # User config value should be present (not overridden by project)
            assert config.ui.default_mode == "conversational"
            # System config value should be present (not overridden)
            assert config.ui.confirmation_level == "normal"
        finally:
            loader.CONFIG_PATHS = original_paths

    def test_deep_merge(self):
        """Test deep merging of nested dictionaries."""
        loader = ConfigLoader()

        base = {
            "llm": {"default_model": "gpt-3.5-turbo", "api_key_env": "OPENAI_API_KEY"},
            "ui": {"confirmation_level": "normal"},
        }

        override = {"llm": {"default_model": "gpt-4"}, "session": {"auto_save_interval": 600}}

        result = loader._deep_merge(base, override)

        # Overridden value
        assert result["llm"]["default_model"] == "gpt-4"
        # Preserved from base
        assert result["llm"]["api_key_env"] == "OPENAI_API_KEY"
        assert result["ui"]["confirmation_level"] == "normal"
        # New value from override
        assert result["session"]["auto_save_interval"] == 600

    def test_environment_variable_overrides(self, monkeypatch):
        """Test that environment variables override config files."""
        # Set environment variables
        monkeypatch.setenv("ALETHEIA_LLM_DEFAULT_MODEL", "gpt-4-turbo")
        monkeypatch.setenv("ALETHEIA_UI_CONFIRMATION_LEVEL", "minimal")
        monkeypatch.setenv("ALETHEIA_SESSION_AUTO_SAVE_INTERVAL", "120")
        monkeypatch.setenv("ALETHEIA_UI_AGENT_VISIBILITY", "true")

        loader = ConfigLoader()
        config = loader.load()

        # Environment variables should override defaults
        assert config.llm.default_model == "gpt-4-turbo"
        assert config.ui.confirmation_level == "minimal"
        assert config.session.auto_save_interval == 120
        assert config.ui.agent_visibility is True

    def test_environment_variable_type_conversion(self):
        """Test conversion of environment variable string values."""
        loader = ConfigLoader()

        # Boolean conversions
        assert loader._convert_env_value("true") is True
        assert loader._convert_env_value("True") is True
        assert loader._convert_env_value("yes") is True
        assert loader._convert_env_value("1") is True
        assert loader._convert_env_value("false") is False
        assert loader._convert_env_value("False") is False
        assert loader._convert_env_value("no") is False
        assert loader._convert_env_value("0") is False

        # Integer conversion
        assert loader._convert_env_value("42") == 42
        assert loader._convert_env_value("1000") == 1000

        # String (no conversion)
        assert loader._convert_env_value("gpt-4") == "gpt-4"
        assert loader._convert_env_value("normal") == "normal"

    def test_nested_environment_variables(self, monkeypatch):
        """Test nested environment variable overrides."""
        monkeypatch.setenv("ALETHEIA_KUBERNETES_CONTEXT", "prod-us")
        monkeypatch.setenv("ALETHEIA_KUBERNETES_NAMESPACE", "payments")
        monkeypatch.setenv("ALETHEIA_ELASTICSEARCH_ENDPOINT", "https://es.prod.example.com")

        loader = ConfigLoader()
        config = loader.load()

        assert config.data_sources.kubernetes.context == "prod-us"
        assert config.data_sources.kubernetes.namespace == "payments"
        assert config.data_sources.elasticsearch.endpoint == "https://es.prod.example.com"

    def test_get_config_before_load(self):
        """Test that get_config raises error if load not called."""
        loader = ConfigLoader()

        with pytest.raises(RuntimeError, match="Configuration not loaded"):
            loader.get_config()

    def test_get_config_after_load(self):
        """Test that get_config returns loaded configuration."""
        loader = ConfigLoader()
        loaded_config = loader.load()
        retrieved_config = loader.get_config()

        assert retrieved_config is loaded_config
        assert isinstance(retrieved_config, ConfigSchema)

    def test_reload_config(self, tmp_path, monkeypatch):
        """Test that reload refreshes configuration."""
        config_file = tmp_path / "config.yaml"

        # Initial config
        with open(config_file, "w") as f:
            yaml.dump({"llm": {"default_model": "gpt-3.5-turbo"}}, f)

        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [config_file]

        try:
            config1 = loader.load()
            assert config1.llm.default_model == "gpt-3.5-turbo"

            # Modify config file
            with open(config_file, "w") as f:
                yaml.dump({"llm": {"default_model": "gpt-4"}}, f)

            # Reload
            config2 = loader.reload()
            assert config2.llm.default_model == "gpt-4"
        finally:
            loader.CONFIG_PATHS = original_paths

    def test_malformed_yaml_file(self, tmp_path, capsys):
        """Test that malformed YAML files are handled gracefully."""
        config_file = tmp_path / "bad_config.yaml"

        # Create malformed YAML
        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [[[")

        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [config_file]

        try:
            config = loader.load()

            # Should still load with defaults
            assert config.llm.default_model == "gpt-4o"

            # Should have printed a warning
            captured = capsys.readouterr()
            assert "Warning" in captured.out
            assert str(config_file) in captured.out
        finally:
            loader.CONFIG_PATHS = original_paths

    def test_missing_config_files(self):
        """Test that missing config files don't cause errors."""
        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [
            Path("/nonexistent/system/config.yaml"),
            Path("/nonexistent/user/config.yaml"),
        ]

        try:
            config = loader.load()

            # Should load with defaults
            assert isinstance(config, ConfigSchema)
            assert config.llm.default_model == "gpt-4o"
        finally:
            loader.CONFIG_PATHS = original_paths

    def test_complete_config_example(self, tmp_path):
        """Test loading a complete configuration example."""
        config_file = tmp_path / "complete_config.yaml"

        complete_config = {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY",
                "agents": {
                    "orchestrator": {"model": "gpt-4o"},
                    "data_fetcher": {"model": "gpt-4o-mini"},
                    "pattern_analyzer": {"model": "gpt-4o"},
                    "code_inspector": {"model": "gpt-4o"},
                    "root_cause_analyst": {"model": "o1"},
                },
            },
            "data_sources": {
                "kubernetes": {"context": "prod-eu", "namespace": "default"},
                "elasticsearch": {
                    "endpoint": "https://es.company.com",
                    "credentials": {
                        "type": "env",
                        "username_env": "ES_USERNAME",
                        "password_env": "ES_PASSWORD",
                    },
                },
                "prometheus": {
                    "endpoint": "https://prometheus.company.com",
                    "credentials": {"type": "env"},
                },
            },
            "ui": {
                "confirmation_level": "normal",
                "default_mode": "guided",
                "agent_visibility": False,
            },
            "session": {"auto_save_interval": 300, "default_time_window": "2h"},
            "encryption": {
                "algorithm": "Fernet",
                "pbkdf2_iterations": 100000,
                "salt_size": 32,
            },
            "sampling": {
                "logs": {
                    "default_sample_size": 200,
                    "always_include_levels": ["ERROR", "FATAL", "CRITICAL"],
                },
                "metrics": {"default_resolution": "1m", "auto_adjust": True},
            },
        }

        with open(config_file, "w") as f:
            yaml.dump(complete_config, f)

        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [config_file]

        try:
            config = loader.load()

            # Verify all sections loaded correctly
            assert config.llm.default_model == "gpt-4o"
            assert config.llm.get_agent_config("data_fetcher").model == "gpt-4o-mini"
            assert config.data_sources.kubernetes.context == "prod-eu"
            assert config.data_sources.elasticsearch.endpoint == "https://es.company.com"
            assert config.ui.confirmation_level == "normal"
            assert config.session.auto_save_interval == 300
            assert config.encryption.pbkdf2_iterations == 100000
            assert config.sampling.logs.default_sample_size == 200
        finally:
            loader.CONFIG_PATHS = original_paths


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_precedence_order_integration(self, tmp_path, monkeypatch):
        """Test complete precedence order: env > project > user > system."""
        # Create all config levels
        system_config = tmp_path / "system.yaml"
        user_config = tmp_path / "user.yaml"
        project_config = tmp_path / "project.yaml"

        with open(system_config, "w") as f:
            yaml.dump(
                {
                    "llm": {"default_model": "system-model"},
                    "ui": {"confirmation_level": "verbose"},
                    "session": {"auto_save_interval": 100},
                },
                f,
            )

        with open(user_config, "w") as f:
            yaml.dump(
                {
                    "llm": {"default_model": "user-model"},
                    "ui": {"confirmation_level": "normal"},
                },
                f,
            )

        with open(project_config, "w") as f:
            yaml.dump({"llm": {"default_model": "project-model"}}, f)

        # Set environment variable (highest precedence)
        monkeypatch.setenv("ALETHEIA_LLM_DEFAULT_MODEL", "env-model")

        loader = ConfigLoader()
        original_paths = loader.CONFIG_PATHS
        loader.CONFIG_PATHS = [system_config, user_config, project_config]

        try:
            config = loader.load()

            # Environment should win
            assert config.llm.default_model == "env-model"
            # User should win over system
            assert config.ui.confirmation_level == "normal"
            # System should be used (not overridden)
            assert config.session.auto_save_interval == 100
        finally:
            loader.CONFIG_PATHS = original_paths
