"""Dynamic loader for user-defined agents.

Discovers and loads agents from configured directories, allowing users
to extend Aletheia with custom agents without modifying core code.

Expected directory structure:
```
user_agents_directory/
  my_agent/
    config.yaml        # Agent configuration (required)
    agent.py           # Agent class definition (required)
    instructions.yaml  # Agent instructions (required)
    plugins/           # Optional: agent-specific plugins
```

The instructions.yaml file must follow the same structure as internal agents:
```yaml
agent:
  name: my_agent
  identity: |
    You are MyAgent, a specialized agent for...
  guidelines: |
    When handling requests, you should...
```
"""

import importlib.util
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from aletheia.agents.agent_config import UserAgentConfig
from aletheia.agents.base import BaseAgent
from aletheia.utils.logging import log_debug, log_error

if TYPE_CHECKING:
    from aletheia.config import Config
    from aletheia.plugins.scratchpad.scratchpad import Scratchpad
    from aletheia.session import Session


class AgentLoadError(Exception):
    """Raised when an agent fails to load."""

    pass


class UserAgentLoader:
    """Discovers and loads user-defined agents from a directory.

    Scans the configured user agents directory for subdirectories containing
    valid agent definitions (config.yaml + agent.py) and loads them dynamically.
    """

    def __init__(self, agents_directory: str | Path):
        """Initialize the loader.

        Args:
            agents_directory: Path to directory containing user agent packages
        """
        self.agents_directory = Path(agents_directory)

    def discover_agents(self) -> list[tuple[Path, UserAgentConfig]]:
        """Discover all valid agent packages in the agents directory.

        Scans for subdirectories containing both config.yaml and agent.py files.

        Returns:
            List of tuples containing (agent_dir, validated_config)
        """
        if not self.agents_directory.exists():
            log_debug(
                f"UserAgentLoader::discover_agents:: "
                f"Agents directory does not exist: {self.agents_directory}"
            )
            return []

        discovered = []
        for agent_dir in self.agents_directory.iterdir():
            if not agent_dir.is_dir():
                continue

            config_path = agent_dir / "config.yaml"
            agent_path = agent_dir / "agent.py"
            instructions_path = agent_dir / "instructions.yaml"

            # All required files must exist
            if not config_path.exists():
                log_debug(
                    f"UserAgentLoader::discover_agents:: "
                    f"Skipping {agent_dir.name}: missing config.yaml"
                )
                continue

            if not agent_path.exists():
                log_debug(
                    f"UserAgentLoader::discover_agents:: "
                    f"Skipping {agent_dir.name}: missing agent.py"
                )
                continue

            if not instructions_path.exists():
                log_debug(
                    f"UserAgentLoader::discover_agents:: "
                    f"Skipping {agent_dir.name}: missing instructions.yaml"
                )
                continue

            # Validate config
            try:
                agent_config = UserAgentConfig.from_yaml(config_path)
            except (ValidationError, Exception) as e:
                log_error(
                    f"UserAgentLoader::discover_agents:: "
                    f"Invalid config in {agent_dir.name}: {e}"
                )
                continue

            # Check if agent is enabled
            if not agent_config.agent.enabled:
                log_debug(
                    f"UserAgentLoader::discover_agents:: "
                    f"Agent {agent_config.agent.name} is disabled"
                )
                continue

            discovered.append((agent_dir, agent_config))
            log_debug(
                f"UserAgentLoader::discover_agents:: "
                f"Discovered agent: {agent_config.agent.name}"
            )

        return discovered

    def load_agent_class(self, agent_dir: Path, class_name: str) -> type[BaseAgent]:
        """Dynamically load an agent class from agent.py.

        Args:
            agent_dir: Path to the agent directory
            class_name: Name of the class to load from agent.py

        Returns:
            The agent class (not instantiated)

        Raises:
            AgentLoadError: If the class cannot be loaded
        """
        agent_path = agent_dir / "agent.py"
        module_name = f"user_agent_{agent_dir.name}"

        try:
            # Add agent directory to path for local imports
            if str(agent_dir) not in sys.path:
                sys.path.insert(0, str(agent_dir))

            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, agent_path)
            if spec is None or spec.loader is None:
                raise AgentLoadError(f"Cannot create module spec for {agent_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Get the class
            if not hasattr(module, class_name):
                raise AgentLoadError(f"Class '{class_name}' not found in {agent_path}")

            agent_class = getattr(module, class_name)

            # Verify it's a BaseAgent subclass
            if not issubclass(agent_class, BaseAgent):
                raise AgentLoadError(
                    f"Class '{class_name}' must inherit from BaseAgent"
                )

            return cast(type[BaseAgent], agent_class)

        except AgentLoadError:
            raise
        except Exception as e:
            raise AgentLoadError(f"Failed to load agent class: {e}") from e

    def instantiate_agent(
        self,
        agent_dir: Path,
        agent_config: UserAgentConfig,
        config: "Config",
        session: "Session",
        scratchpad: "Scratchpad",
        additional_middleware: Sequence[Any] | None = None,
    ) -> BaseAgent:
        """Load and instantiate a user agent.

        Args:
            agent_dir: Path to the agent directory
            agent_config: Validated agent configuration
            config: Aletheia configuration
            session: Current session
            scratchpad: Shared scratchpad
            additional_middleware: Optional middleware list

        Returns:
            Instantiated agent

        Raises:
            AgentLoadError: If agent cannot be loaded or instantiated
        """
        agent_def = agent_config.agent

        # Load the class
        agent_class = self.load_agent_class(agent_dir, agent_def.class_name)

        # Instantiate with standard parameters
        try:
            kwargs: dict[str, Any] = {
                "name": agent_def.name,
                "config": config,
                "description": agent_def.description,
                "session": session,
                "scratchpad": scratchpad,
                "prompts_dir": agent_dir.parent,  # Parent dir so AgentInfo can find name/instructions.yaml
            }
            if additional_middleware is not None:
                kwargs["additional_middleware"] = additional_middleware

            agent = agent_class(**kwargs)
            log_debug(
                f"UserAgentLoader::instantiate_agent:: "
                f"Successfully loaded user agent: {agent_def.name}"
            )
            return agent
        except Exception as e:
            raise AgentLoadError(
                f"Failed to instantiate agent '{agent_def.name}': {e}"
            ) from e


def load_user_agents(
    agents_directory: str | Path,
    config: "Config",
    session: "Session",
    scratchpad: "Scratchpad",
    additional_middleware: Sequence[Any] | None = None,
) -> tuple[list[Any], list[BaseAgent]]:
    """Load all user agents from a directory.

    Convenience function that discovers and loads all valid user agents.

    Args:
        agents_directory: Path to user agents directory
        config: Aletheia configuration
        session: Current session
        scratchpad: Shared scratchpad
        additional_middleware: Optional middleware list

    Returns:
        Tuple of (tools_list, agent_instances) matching _build_plugins signature
    """
    loader = UserAgentLoader(agents_directory)
    discovered = loader.discover_agents()

    tools = []
    agent_instances = []

    for agent_dir, agent_config in discovered:
        log_debug(
            f"UserAgentLoader::load_user_agents:: "
            f"Loading agent: {agent_config.agent.name}"
        )
        try:
            agent = loader.instantiate_agent(
                agent_dir=agent_dir,
                agent_config=agent_config,
                config=config,
                session=session,
                scratchpad=scratchpad,
                additional_middleware=additional_middleware,
            )
            agent_instances.append(agent)
            tools.append(agent.agent.as_tool())
        except AgentLoadError as e:
            log_error(f"UserAgentLoader::load_user_agents:: {e}")
            # Continue loading other agents

    return tools, agent_instances
