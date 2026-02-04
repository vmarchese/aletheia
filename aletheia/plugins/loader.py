"""Loader for plugin information files."""

from pathlib import Path


class PluginInfoLoader:
    """Loader for plugin information files."""

    def __init__(self):
        package_dir = Path(__file__).parent.parent
        self.prompts_dir = package_dir

    def load(self, plugin_name: str) -> str:
        """Load the plugin information file for the given plugin name."""
        prompt_file = self.prompts_dir / f"plugins/{plugin_name}/instructions.md"
        content = ""
        try:
            with open(prompt_file, encoding="utf-8") as file:
                content = file.read()
        except FileNotFoundError:
            content = ""
        return content
