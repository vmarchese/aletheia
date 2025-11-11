from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.base import BasePlugin


class CopilotPlugin:
    """Semantic Kernel plugin for Copilot code operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the CopilotPlugin .

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "CopilotPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("copilot_plugin")        

    #@ai_function(description="Launches Copilot code with -p in non interactive mode on a folder containing the repository to analyze.")
    def code_analyze(
        self,
        prompt: str,
        repo_path: Annotated[str, "Path to the repository to analyze"]
    ) -> str:
        """Launches Copilot code with -p in non interactive mode on a folder containing the repository to analyze."""
        try:
            log_debug(f"CopilotPlugin::code_analyze:: Launching Copilot code on repo: {repo_path}")
            import subprocess

            # Construct the command to run Copilot code
            command = [
                "copilot", 
                "--add-dir", repo_path,
                "-p", prompt]

            # Run the command and capture output
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                log_error(f"Copilot analysis failed: {result.stderr}")
                return f"Error launching copilot: {result.stderr}"

            log_debug("Copilot analysis completed successfully.")
            return result.stdout
        except Exception as e:
            log_error(f"Error launching copilot: {str(e)}")
            return f"Error launching copilot: {e}"

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [self.code_analyze]
