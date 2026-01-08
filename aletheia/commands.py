"""
Docstring for aletheia.commands
"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from rich.markdown import Markdown

from aletheia import __version__
from aletheia.agents.client import LLMClient

if TYPE_CHECKING:
    from aletheia.config import Config

logger = logging.getLogger(__name__)


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
                for command_name, command_path in sorted(custom_commands.items()):
                    console.print(f"  /{command_name} - (from {command_path.name})")
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
        Help command to display available commands.
        :param console: Description
        """
        completion_usage = kwargs.get("completion_usage")
        config = kwargs.get("config")
        if (
            completion_usage
            and completion_usage.input_token_count
            and completion_usage.output_token_count
        ):
            input_token = completion_usage.input_token_count
            output_token = completion_usage.output_token_count
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


COMMANDS["help"] = Help()
COMMANDS["version"] = Version()
COMMANDS["info"] = INFO()
COMMANDS["cost"] = CostInfo()


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


def get_custom_commands(config: "Config") -> dict[str, Path]:
    """
    Discover custom command files in config directory.

    Returns dict mapping command name to file path.
    """
    commands_dir = ensure_commands_directory(config)
    custom_commands = {}

    if not commands_dir.exists():
        logger.debug(f"Commands directory does not exist: {commands_dir}")
        return custom_commands

    # Find all .md files in the commands directory
    for md_file in commands_dir.glob("*.md"):
        # Extract command name from filename (without .md extension)
        command_name = md_file.stem

        # Validate command name (alphanumeric, hyphens, underscores only)
        if re.match(r"^[a-zA-Z0-9_-]+$", command_name):
            custom_commands[command_name] = md_file
        else:
            logger.warning(
                f"Skipping invalid command filename: {md_file.name} "
                f"(command names must be alphanumeric with hyphens/underscores only)"
            )

    logger.debug(
        f"Discovered {len(custom_commands)} custom commands: {list(custom_commands.keys())}"
    )
    return custom_commands


def load_command_content(command_path: Path) -> str:
    """
    Load content from a command markdown file.

    Args:
        command_path: Path to the command file

    Returns:
        Content of the file, or empty string if error occurs
    """
    try:
        content = command_path.read_text(encoding="utf-8")
        logger.debug(f"Loaded command content from: {command_path}")
        return content.strip()
    except Exception as e:
        logger.error(f"Failed to read command file {command_path}: {e}")
        return ""


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

    # Try to find and load custom command
    custom_commands = get_custom_commands(config)
    if command_name not in custom_commands:
        logger.debug(f"No custom command found for: {command_name}")
        return message, False

    # Load command content
    command_path = custom_commands[command_name]
    command_content = load_command_content(command_path)

    # Expand the message
    if additional_text:
        expanded_message = f"{command_content} {additional_text}"
    else:
        expanded_message = command_content

    logger.info(f"Expanded custom command '/{command_name}' from {command_path}")
    return expanded_message, True
