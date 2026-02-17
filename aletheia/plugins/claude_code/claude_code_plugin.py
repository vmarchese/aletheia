"""Plugin for Claude code operations."""

import subprocess
from typing import Annotated

import structlog
from agent_framework import FunctionTool

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session
from aletheia.utils.command import sanitize_command

logger = structlog.get_logger(__name__)


class ClaudeCodePlugin(BasePlugin):
    """plugin for Claude code operations."""

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
        self.instructions = loader.load("claude_code")

    def code_analyze(
        self,
        prompt: str,
        repo_path: Annotated[str, "Path to the repository to analyze"],
    ) -> str:
        """Launches claude code with -p in non interactive mode on a folder containing the repository to analyze."""
        try:
            logger.debug(
                f"ClaudeCodePlugin::claude_code_analyze:: Launching claude code on repo: {repo_path}"
            )

            # Construct the command to run claude code
            command = [
                "claude",
                "--output-format",
                "text",
                "--add-dir",
                repo_path,
                "-p",
                prompt,
            ]

            # Run the command and capture output
            result = subprocess.run(
                sanitize_command(command), capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                logger.error(f"Claude code analysis failed: {result.stderr}")
                return f"Error launching claude code: {result.stderr}"

            logger.debug("Claude code analysis completed successfully.")
            return result.stdout
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error(f"Error launching claude code: {str(e)}")
            return f"Error launching claude code: {e}"
        except Exception as e:
            logger.error(f"Unexpected error launching claude code: {str(e)}")
            raise

    def get_tools(self) -> list[FunctionTool]:
        """Get the list of tools provided by this plugin."""
        return [self.code_analyze]
