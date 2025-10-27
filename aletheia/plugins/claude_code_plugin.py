from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType


class ClaudeCodePlugin:
    """Semantic Kernel plugin for Claude code operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the ClaudeCodePlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config

    @kernel_function(description="Launches claude code with -p in non interactive mode on a folder containing the repository to analyze.")
    async def code_analyze(
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