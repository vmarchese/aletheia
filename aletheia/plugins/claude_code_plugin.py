from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin


class ClaudeCodePlugin(BasePlugin):
    """Semantic Kernel plugin for Claude code operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the ClaudeCodePlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "ClaudeCodePlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("claude_code_plugin")

    #@ai_function(description="Launches claude code with -p in non interactive mode on a folder containing the repository to analyze.")
    def code_analyze(
        self,
        prompt: str,
        repo_path: Annotated[str, "Path to the repository to analyze"]
    ) -> str:
        """Launches claude code with -p in non interactive mode on a folder containing the repository to analyze."""
        try:
            log_debug(f"ClaudeCodePlugin::claude_code_analyze:: Launching claude code on repo: {repo_path}")
            import subprocess

            # Construct the command to run claude code
            command = [
                "claude", 
                "--output-format", "text",
                "--add-dir", repo_path,
                "-p", prompt]

            # Run the command and capture output
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                log_error(f"Claude code analysis failed: {result.stderr}")
                return f"Error launching claude code: {result.stderr}"

            log_debug("Claude code analysis completed successfully.")
            return result.stdout
        except Exception as e:
            log_error(f"Error launching claude code: {str(e)}")
            return f"Error launching claude code: {e}"

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [self.code_analyze]
