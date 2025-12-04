"""
Docstring for aletheia.commands
"""
from rich.markdown import Markdown

from aletheia import __version__
from aletheia.agents.client import LLMClient


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
        for command in COMMANDS.values():
            console.print(f"/{command.name} - {command.description}")


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
        console.print("Aletheia is an AI-powered tool for investigating and diagnosing issues in software systems.")
        console.print(f"LLM Provider: {llm_client.provider}")
        console.print(f"LLM Model:    {llm_client.model}")


class AgentsInfo(Command):
    """
    prints information about loaded agents.
    """
    def __init__(self, agents):
        super().__init__("agents", "Show information about loaded agents")
        self.agents = agents

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
        if completion_usage and completion_usage.input_token_count and completion_usage.output_token_count:
            input_token = completion_usage.input_token_count
            output_token = completion_usage.output_token_count
            total_tokens = input_token + output_token
            total_cost = (input_token * config.cost_per_input_token) + (output_token * config.cost_per_output_token)
            cost_table = "| Metric | Total | Input | Output |\n"
            cost_table += "|--------|-------|-------|--------|\n"
            cost_table += f"| Tokens | {total_tokens} | {input_token} | {output_token} |\n"
            cost_table += f"| Cost (€) | €{total_cost:.6f} | €{input_token * config.cost_per_input_token:.6f} | €{output_token * config.cost_per_output_token:.6f} |\n"
            console.print(Markdown(cost_table))


COMMANDS["help"] = Help()
COMMANDS["version"] = Version()
COMMANDS["info"] = INFO()
COMMANDS["cost"] = CostInfo()
