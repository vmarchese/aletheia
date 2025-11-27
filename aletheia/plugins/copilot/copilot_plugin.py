"""plugin for Copilot code operations."""
from typing import Annotated, List
import subprocess

from agent_framework import ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.utils.command import sanitize_command


class CopilotPlugin:
    """plugin for Copilot code operations."""

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
        self.instructions = loader.load("copilot")

    def code_analyze(
        self,
        prompt: str,
        repo_path: Annotated[str, "Path to the repository to analyze"]
    ) -> str:
        """Launches Copilot code with -p in non interactive mode on a folder containing the repository to analyze."""
        try:
            log_debug(f"CopilotPlugin::code_analyze:: Launching Copilot code on repo: {repo_path}")

            # Construct the command to run Copilot code
            command = [
                "copilot",
                "--add-dir", repo_path,
                "-p", prompt]

            # Run the command and capture output
            result = subprocess.run(sanitize_command(command), capture_output=True, text=True, check=False)

            if result.returncode != 0:
                log_error(f"Copilot analysis failed: {result.stderr}")
                return f"Error launching copilot: {result.stderr}"

            log_debug("Copilot analysis completed successfully.")
            return result.stdout
        except subprocess.CalledProcessError as e:
            log_error(f"Copilot subprocess failed: {e.stderr}")
            return f"Error launching copilot: {e.stderr}"
        except OSError as e:
            log_error(f"OS error when launching copilot: {str(e)}")
            return f"Error launching copilot: {e}"

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [self.code_analyze]
