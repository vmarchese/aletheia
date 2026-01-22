"""Tests for user-defined agent loading functionality."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from aletheia.agents.agent_config import UserAgentConfig
from aletheia.agents.loader import (
    AgentLoadError,
    UserAgentLoader,
)


class TestAgentConfig:
    """Test agent configuration parsing and validation."""

    def test_parse_valid_config(self, tmp_path: Path) -> None:
        """Test parsing a valid agent config.yaml."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """agent:
  name: test_agent
  class: TestAgent
  description: A test agent for testing
  enabled: true
  identity: |
    You are TestAgent.
  guidelines: |
    Follow the rules.
"""
        )

        config = UserAgentConfig.from_yaml(config_file)
        assert config.agent.name == "test_agent"
        assert config.agent.class_name == "TestAgent"
        assert config.agent.description == "A test agent for testing"
        assert config.agent.enabled is True
        assert "TestAgent" in config.agent.identity
        assert "Follow the rules" in config.agent.guidelines

    def test_parse_minimal_config(self, tmp_path: Path) -> None:
        """Test parsing a minimal config with only required fields."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """agent:
  name: minimal_agent
  class: MinimalAgent
  description: Minimal agent
"""
        )

        config = UserAgentConfig.from_yaml(config_file)
        assert config.agent.name == "minimal_agent"
        assert config.agent.class_name == "MinimalAgent"
        assert config.agent.description == "Minimal agent"
        assert config.agent.enabled is True  # Default value
        assert config.agent.identity == ""  # Default value
        assert config.agent.guidelines == ""  # Default value

    def test_parse_disabled_agent(self, tmp_path: Path) -> None:
        """Test parsing a config with enabled=false."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """agent:
  name: disabled_agent
  class: DisabledAgent
  description: This agent is disabled
  enabled: false
"""
        )

        config = UserAgentConfig.from_yaml(config_file)
        assert config.agent.enabled is False

    def test_parse_missing_required_field(self, tmp_path: Path) -> None:
        """Test that missing required fields raise validation error."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """agent:
  name: incomplete_agent
  # missing class and description
"""
        )

        with pytest.raises(ValidationError):
            UserAgentConfig.from_yaml(config_file)

    def test_parse_invalid_yaml(self, tmp_path: Path) -> None:
        """Test handling of invalid YAML syntax."""
        import yaml

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """agent:
  name: bad_yaml
  class: [unclosed
"""
        )

        with pytest.raises(yaml.YAMLError):
            UserAgentConfig.from_yaml(config_file)


class TestUserAgentLoaderDiscovery:
    """Test agent discovery functionality."""

    def test_discover_empty_directory(self, tmp_path: Path) -> None:
        """Test discovery in an empty directory."""
        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert discovered == []

    def test_discover_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test discovery when directory doesn't exist."""
        loader = UserAgentLoader(tmp_path / "nonexistent")
        discovered = loader.discover_agents()
        assert discovered == []

    def test_discover_agent_missing_config(self, tmp_path: Path) -> None:
        """Test that agents without config.yaml are skipped."""
        agent_dir = tmp_path / "incomplete_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("# No config.yaml")

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert discovered == []

    def test_discover_agent_missing_agent_py(self, tmp_path: Path) -> None:
        """Test that agents without agent.py are skipped."""
        agent_dir = tmp_path / "incomplete_agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text(
            """agent:
  name: incomplete
  class: IncompleteAgent
  description: Missing agent.py
"""
        )

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert discovered == []

    def test_discover_valid_agent(self, tmp_path: Path) -> None:
        """Test discovering a valid agent."""
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text(
            """agent:
  name: my_agent
  class: MyAgent
  description: My custom agent
"""
        )
        (agent_dir / "agent.py").write_text(
            """from aletheia.agents.base import BaseAgent

class MyAgent(BaseAgent):
    pass
"""
        )

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert len(discovered) == 1
        agent_path, config = discovered[0]
        assert agent_path == agent_dir
        assert config.agent.name == "my_agent"

    def test_discover_multiple_agents(self, tmp_path: Path) -> None:
        """Test discovering multiple agents."""
        for name in ["agent_a", "agent_b", "agent_c"]:
            agent_dir = tmp_path / name
            agent_dir.mkdir()
            (agent_dir / "config.yaml").write_text(
                f"""agent:
  name: {name}
  class: {name.title().replace('_', '')}
  description: Agent {name}
"""
            )
            (agent_dir / "agent.py").write_text("# placeholder")

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert len(discovered) == 3

    def test_discover_skips_disabled_agents(self, tmp_path: Path) -> None:
        """Test that disabled agents are skipped during discovery."""
        agent_dir = tmp_path / "disabled_agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text(
            """agent:
  name: disabled_agent
  class: DisabledAgent
  description: This agent is disabled
  enabled: false
"""
        )
        (agent_dir / "agent.py").write_text("# placeholder")

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert discovered == []

    def test_discover_skips_files_not_directories(self, tmp_path: Path) -> None:
        """Test that regular files are skipped."""
        (tmp_path / "not_a_directory.txt").write_text("I'm a file")

        agent_dir = tmp_path / "valid_agent"
        agent_dir.mkdir()
        (agent_dir / "config.yaml").write_text(
            """agent:
  name: valid_agent
  class: ValidAgent
  description: A valid agent
"""
        )
        (agent_dir / "agent.py").write_text("# placeholder")

        loader = UserAgentLoader(tmp_path)
        discovered = loader.discover_agents()
        assert len(discovered) == 1


class TestUserAgentLoaderLoading:
    """Test agent class loading functionality."""

    def test_load_valid_agent_class(self, tmp_path: Path) -> None:
        """Test loading a valid agent class."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(
            """from aletheia.agents.base import BaseAgent

class TestAgent(BaseAgent):
    def __init__(self, name, config, description, session, scratchpad, **kwargs):
        super().__init__(
            name=name,
            config=config,
            description=description,
            session=session,
            plugins=[scratchpad],
            **kwargs
        )
"""
        )

        loader = UserAgentLoader(tmp_path)
        agent_class = loader.load_agent_class(agent_dir, "TestAgent")
        assert agent_class.__name__ == "TestAgent"

    def test_load_missing_class(self, tmp_path: Path) -> None:
        """Test error when class name doesn't exist in agent.py."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(
            """from aletheia.agents.base import BaseAgent

class SomeOtherAgent(BaseAgent):
    pass
"""
        )

        loader = UserAgentLoader(tmp_path)
        with pytest.raises(AgentLoadError) as exc_info:
            loader.load_agent_class(agent_dir, "NonExistentAgent")
        assert "not found" in str(exc_info.value)

    def test_load_class_not_subclass_of_base_agent(self, tmp_path: Path) -> None:
        """Test error when class doesn't inherit from BaseAgent."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(
            """class NotAnAgent:
    pass
"""
        )

        loader = UserAgentLoader(tmp_path)
        with pytest.raises(AgentLoadError) as exc_info:
            loader.load_agent_class(agent_dir, "NotAnAgent")
        assert "must inherit from BaseAgent" in str(exc_info.value)

    def test_load_syntax_error_in_agent(self, tmp_path: Path) -> None:
        """Test error handling for syntax errors in agent.py."""
        agent_dir = tmp_path / "test_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text(
            """class BrokenAgent(
    # Missing closing parenthesis
"""
        )

        loader = UserAgentLoader(tmp_path)
        with pytest.raises(AgentLoadError):
            loader.load_agent_class(agent_dir, "BrokenAgent")


class TestConfigIntegration:
    """Test integration with Aletheia config."""

    def test_config_has_user_agents_directory(self) -> None:
        """Test that Config has user_agents_directory field."""
        from aletheia.config import Config

        config = Config()
        assert hasattr(config, "user_agents_directory")
        assert isinstance(config.user_agents_directory, str)

    def test_config_has_user_agents_enabled(self) -> None:
        """Test that Config has user_agents_enabled field."""
        from aletheia.config import Config

        config = Config()
        assert hasattr(config, "user_agents_enabled")
        assert config.user_agents_enabled is True  # Default

    def test_config_has_disabled_agents(self) -> None:
        """Test that Config has disabled_agents field."""
        from aletheia.config import Config

        config = Config()
        assert hasattr(config, "disabled_agents")
        assert isinstance(config.disabled_agents, list)
        assert config.disabled_agents == []  # Default empty list
