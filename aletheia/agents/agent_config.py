"""Configuration schema for user-defined agents.

Defines the Pydantic models for validating agent config.yaml files.

Expected config.yaml structure:
```yaml
agent:
  name: my_agent
  class: MyAgentClass
  description: "Agent description for orchestrator"
  enabled: true
```

Note: Identity and guidelines should be defined in instructions.yaml,
following the same pattern as internal agents.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from aletheia.utils.logging import log_debug


class AgentDefinition(BaseModel):
    """Agent definition within config.yaml."""

    name: str = Field(..., description="Unique agent identifier")
    class_name: str = Field(
        ..., alias="class", description="Python class name in agent.py"
    )
    description: str = Field(..., description="Agent description shown to orchestrator")
    enabled: bool = Field(default=True, description="Whether the agent is enabled")


class UserAgentConfig(BaseModel):
    """Root configuration model for user agent config.yaml."""

    agent: AgentDefinition = Field(..., description="Agent configuration")

    @classmethod
    def from_yaml(cls, config_path: Path) -> "UserAgentConfig":
        """Load and validate configuration from a YAML file.

        Args:
            config_path: Path to the config.yaml file

        Returns:
            Validated UserAgentConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            pydantic.ValidationError: If config validation fails
        """
        with open(config_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        log_debug(
            f"UserAgentConfig::from_yaml:: "
            f"Loaded config from {config_path}: {data}")
        return cls.model_validate(data)
