"""plugin for Copilot code operations."""

import subprocess
from typing import Annotated

import structlog
from agent_framework import ToolProtocol

from aletheia.config import Config
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session
from aletheia.utils.command import sanitize_command

logger = structlog.get_logger(__name__)


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
        repo_path: Annotated[str, "Path to the repository to analyze"],
    ) -> str:
        """Launches Copilot code with -p in non interactive mode on a folder containing the repository to analyze."""
        try:
            logger.debug(
                f"CopilotPlugin::code_analyze:: Launching Copilot code on repo: {repo_path}"
            )

            # Construct the command to run Copilot code
            command = ["copilot", "--add-dir", repo_path, "-p", prompt]

            # Run the command and capture output
            result = subprocess.run(
                sanitize_command(command), capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                logger.error(f"Copilot analysis failed: {result.stderr}")
                return f"Error launching copilot: {result.stderr}"

            logger.debug("Copilot analysis completed successfully.")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Copilot subprocess failed: {e.stderr}")
            return f"Error launching copilot: {e.stderr}"
        except OSError as e:
            logger.error(f"OS error when launching copilot: {str(e)}")
            return f"Error launching copilot: {e}"

    def get_tools(self) -> list[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [self.code_analyze]
