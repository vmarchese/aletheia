"""Module for loading agent instructions from markdown files."""

from pathlib import Path


class Loader:
    """Loader for agent instructions."""

    def __init__(self):
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir / "agents"

    def load(self, agent_name: str, _type: str, prefix: str = "") -> str:
        """Load instructions for a given agent and type."""
        instructions_file_name = (
            f"{prefix}_{agent_name}_{_type}.md"
            if prefix
            else f"{agent_name}_{_type}.md"
        )
        prompt_file = self.prompts_dir / f"{agent_name}/{instructions_file_name}"
        with open(prompt_file, encoding="utf-8") as file:
            content = file.read()
        return content
