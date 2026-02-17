"""
Docstring for aletheia.commands
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml
from pydantic import BaseModel, Field
from rich.markdown import Markdown

from aletheia import __version__
from aletheia.agents.client import LLMClient

if TYPE_CHECKING:
    from aletheia.config import Config

logger = structlog.get_logger(__name__)


COMMANDS = {}


class Command:
    """
    Base class for commands.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def execute(self, console, *args, **kwargs):
        """
        Execute the command.
        """


class CustomCommand(BaseModel):
    """Custom command loaded from markdown file with frontmatter."""

    name: str = Field(..., description="Display name of the command")
    description: str = Field(
        ..., description="Brief description of what the command does"
    )
    instructions: str = Field(..., description="The actual command instructions/prompt")
    file_path: Path = Field(..., description="Path to the command file")


class Help(Command):
    """
    Help command to display available commands.
    """

    def __init__(self):
        super().__init__("help", "Show this help message")

    def execute(self, console, *args, **kwargs):
        """
        Help command to display available commands.
        :param console: Description
        """
        # Display built-in commands
        console.print("\n[bold cyan]Built-in Commands:[/bold cyan]")
        for command in COMMANDS.values():
            console.print(f"  /{command.name} - {command.description}")

        # Display custom commands if any exist
        config = kwargs.get("config")
        if config:
            custom_commands = get_custom_commands(config)
            if custom_commands:
                console.print("\n[bold cyan]Custom Commands:[/bold cyan]")
                for command_name, command in sorted(custom_commands.items()):
                    console.print(
                        f"  /{command_name} - {command.name}: {command.description}"
                    )
            else:
                console.print(
                    f"\n[dim]No custom commands found in {config.commands_directory}[/dim]"
                )
        console.print()


class Version(Command):
    """
    prints the current version of Aletheia.
    """

    def __init__(self):
        super().__init__("version", "Show the current version of Aletheia")

    def execute(self, console, *args, **kwargs):
        """
        Help command to display available commands.
        :param console: Description
        """
        console.print(f"Aletheia version: {__version__}")


class INFO(Command):
    """
    prints the current version of Aletheia.
    """

    def __init__(self):
        super().__init__("info", "Show information about Aletheia")

    def execute(self, console, *args, **kwargs):
        """
        Help command to display available commands.
        :param console: Description
        """
        llm_client = LLMClient()
        console.print(
            "Aletheia is an AI-powered tool for investigating and diagnosing issues in software systems."
        )
        console.print(f"LLM Provider: {llm_client.provider}")
        console.print(f"LLM Model:    {llm_client.model}")


class AgentsInfo(Command):
    """
    prints information about loaded agents.
    """

    def __init__(self, agents):
        super().__init__("agents", "Show information about loaded agents")
        self.agents = agents

    def get_agents_names(self):
        """
        Returns the names of the loaded agents.
        :return: List of agent names
        """
        return [agent.name for agent in self.agents]

    def execute(self, console, *args, **kwargs):
        """
        Help command to display available commands.
        :param console: Description
        """
        console.print("Loaded Agents:")
        for agent in self.agents:
            console.print(f"- {agent.name}: {agent.description}")


class CostInfo(Command):
    """
    prints information about cost.
    """

    def __init__(self):
        super().__init__("cost", "Show information about cost")

    def execute(self, console, *args, **kwargs):
        """
        Display cost information for token usage.
        :param console: Console for output
        """
        completion_usage = kwargs.get("completion_usage")
        config = kwargs.get("config")
        if (
            completion_usage
            and completion_usage.get("input_token_count")
            and completion_usage.get("output_token_count")
        ):
            input_token = completion_usage.get("input_token_count", 0)
            output_token = completion_usage.get("output_token_count", 0)
            total_tokens = input_token + output_token
            total_cost = (input_token * config.cost_per_input_token) + (
                output_token * config.cost_per_output_token
            )
            cost_table = "| Metric | Total | Input | Output |\n"
            cost_table += "|--------|-------|-------|--------|\n"
            cost_table += (
                f"| Tokens | {total_tokens} | {input_token} | {output_token} |\n"
            )
            cost_table += f"| Cost (€) | €{total_cost:.6f} | €{input_token * config.cost_per_input_token:.6f} | €{output_token * config.cost_per_output_token:.6f} |\n"
            console.print(Markdown(cost_table))
        else:
            console.print("No usage data available yet. Send a message first.")


class Reload(Command):
    """Reload skills and custom commands from disk."""

    def __init__(self):
        super().__init__("reload", "Reload skills and custom commands")

    def execute(self, console, *args, **kwargs):
        """Reload skills for all agents and report results."""
        config = kwargs.get("config")
        orchestrator = kwargs.get("orchestrator")

        # Custom commands are always loaded fresh - just confirm count
        custom_count = 0
        if config:
            custom_commands = get_custom_commands(config)
            custom_count = len(custom_commands)

        console.print(
            f"Custom commands: {custom_count} loaded (always fresh from disk)"
        )

        # Reload skills for orchestrator and sub-agents
        if orchestrator:
            skill_count = orchestrator.reload_skills()
            console.print(f"Orchestrator skills: {skill_count} reloaded")

            for agent in getattr(orchestrator, "sub_agent_instances", []):
                if hasattr(agent, "reload_skills"):
                    agent_skill_count = agent.reload_skills()
                    console.print(
                        f"Agent '{agent.name}' skills: {agent_skill_count} reloaded"
                    )

            console.print("Reload complete.")
        else:
            console.print("No active orchestrator - create a session first.")


COMMANDS["help"] = Help()
COMMANDS["version"] = Version()
COMMANDS["info"] = INFO()
COMMANDS["cost"] = CostInfo()
COMMANDS["reload"] = Reload()


# =================================================================
# Custom Command Discovery and Loading
# =================================================================


def ensure_commands_directory(config: "Config") -> Path:
    """
    Ensure the commands directory exists, creating it if necessary.

    Args:
        config: Aletheia configuration

    Returns:
        Path to the commands directory
    """
    commands_dir = Path(config.commands_directory)

    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Commands directory ensured at: {commands_dir}")
    except Exception as e:
        logger.warning(f"Could not create commands directory {commands_dir}: {e}")

    return commands_dir


def parse_command_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter from command markdown content.

    Args:
        content: Full markdown file content

    Returns:
        Tuple of (frontmatter dict, instructions content)

    Example:
        >>> content = "---\\nname: Test\\n---\\nInstructions"
        >>> meta, instructions = parse_command_frontmatter(content)
        >>> meta
        {'name': 'Test'}
        >>> instructions
        'Instructions'
    """
    # Match YAML frontmatter pattern: ---\n...yaml...\n---\n
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        # No frontmatter found - backward compatibility
        return {}, content

    try:
        frontmatter = yaml.safe_load(match.group(1))
        instructions = match.group(2).strip()
        return frontmatter if frontmatter else {}, instructions
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        return {}, content  # Fallback to treating entire content as instructions


def get_custom_commands(config: "Config") -> dict[str, CustomCommand]:
    """
    Discover and load custom command files in config directory.

    Returns dict mapping command name to CustomCommand object.
    """
    commands_dir = ensure_commands_directory(config)
    custom_commands = {}

    if not commands_dir.exists():
        logger.debug(f"Commands directory does not exist: {commands_dir}")
        return custom_commands

    # Find and load all .md files
    for md_file in commands_dir.glob("*.md"):
        command_name = md_file.stem

        # Validate command name (alphanumeric, hyphens, underscores only)
        if not re.match(r"^[a-zA-Z0-9_-]+$", command_name):
            logger.warning(
                f"Skipping invalid command filename: {md_file.name} "
                f"(command names must be alphanumeric with hyphens/underscores only)"
            )
            continue

        # Load command
        command = load_custom_command(command_name, md_file)
        if command:
            custom_commands[command_name] = command

    logger.debug(
        f"Discovered {len(custom_commands)} custom commands: {list(custom_commands.keys())}"
    )
    return custom_commands


def load_custom_command(command_name: str, command_path: Path) -> CustomCommand | None:
    """
    Load a custom command from a markdown file with frontmatter support.

    Args:
        command_name: The command name (from filename)
        command_path: Path to the command markdown file

    Returns:
        CustomCommand object if successful, None if error occurs

    Backward Compatibility:
        - Files with frontmatter: Use frontmatter name/description
        - Plain markdown files: Use filename as name, empty description
    """
    try:
        content = command_path.read_text(encoding="utf-8").strip()
        frontmatter, instructions = parse_command_frontmatter(content)

        # Extract metadata with fallbacks for backward compatibility
        name = frontmatter.get("name", command_name.replace("_", " ").title())
        description = frontmatter.get("description", f"(from {command_path.name})")

        if not instructions:
            logger.warning(f"Command {command_name} has no instructions content")
            return None

        return CustomCommand(
            name=name,
            description=description,
            instructions=instructions,
            file_path=command_path,
        )

    except Exception as e:
        logger.error(f"Failed to load command from {command_path}: {e}")
        return None


def expand_custom_command(message: str, config: "Config") -> tuple[str, bool]:
    """
    Expand custom command in message if found.

    Args:
        message: User input message
        config: Aletheia configuration

    Returns:
        Tuple of (expanded_message, was_expanded)
        - expanded_message: The message with command expanded
        - was_expanded: True if a custom command was found and expanded
    """
    # Check if message starts with /
    if not message.strip().startswith("/"):
        return message, False

    # Extract command name (everything between / and first space, or end of string)
    parts = message.strip()[1:].split(maxsplit=1)
    command_name = parts[0]
    additional_text = parts[1] if len(parts) > 1 else ""

    # Check if it's a built-in command (don't expand those)
    if command_name in COMMANDS:
        logger.debug(f"Command '{command_name}' is a built-in command, not expanding")
        return message, False

    # Try to find custom command
    custom_commands = get_custom_commands(config)
    if command_name not in custom_commands:
        logger.debug(f"No custom command found for: {command_name}")
        return message, False

    # Get command instructions (not full content!)
    command = custom_commands[command_name]
    instructions = command.instructions

    # Expand the message
    if additional_text:
        expanded_message = f"{instructions} {additional_text}"
    else:
        expanded_message = instructions

    logger.info(
        f"Expanded custom command '/{command_name}' ({command.name}) from {command.file_path}"
    )
    return expanded_message, True
