"""plugin for Git operations.

This plugin exposes Git operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides annotated functions for:
- Running git blame on specific lines
- Finding files in repositories
- Extracting code context around specific lines
- Getting commit information
"""

import os
import re
import subprocess
from typing import Annotated

import structlog
from agent_framework import FunctionTool

from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.session import Session
from aletheia.utils.command import sanitize_command

logger = structlog.get_logger(__name__)


class GitPlugin(BasePlugin):
    """plugin for Git operations.

    This plugin provides kernel functions for common Git operations used
    in code inspection and analysis, allowing SK agents to automatically
    invoke Git operations via function calling.

    All functions use Annotated type hints to provide SK with parameter
    descriptions for the LLM to understand how to call them.

    Attributes:
        repositories: List of repository paths to search
    """

    def __init__(self, session: Session):
        """Initialize the Git plugin.

        Args:
            repositories: Optional list of repository paths to search.
                         Can be set later via set_repositories().
        """
        self.name = "GitPlugin"
        self.session = session
        loader = PluginInfoLoader()
        self.instructions = loader.load("git")

    def git_clone_repo(
        self,
        repo_url: Annotated[
            str, "The URL of the git repository to clone (https or ssh)"
        ],
        ref: Annotated[
            str,
            "Optional branch or tag to clone. If omitted, clones the default branch.",
        ] = "",
    ) -> Annotated[
        str, "The path to the cloned repository, or error message if failed."
    ]:
        """
        Clones a git repository by URL into /data/src/<repo_name>.
        If ref is provided, checks out the specified branch or tag.
        Returns the path to the cloned repo or an error message.
        """
        logger.debug(
            f"GitPlugin::git_clone_repo:: called with repo_url={repo_url}, ref={ref}"
        )
        # Extract repo name from URL
        match = re.search(r"([^/]+?)(?:\.git)?$", repo_url)
        if not match:
            return "Error: Could not extract repository name from URL."
        repo_name = match.group(1)
        dest_dir = f"{self.session.session_path}/data/src/{repo_name}"

        # Prepare git clone command
        if ref:
            clone_cmd = ["git", "clone", "--branch", ref, repo_url, dest_dir]
        else:
            clone_cmd = ["git", "clone", repo_url, dest_dir]

        try:
            if os.path.exists(dest_dir):
                return f"Repository already exists at {dest_dir}"
            result = subprocess.run(
                sanitize_command(clone_cmd),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                return f"Error cloning repo: {result.stderr.strip()}"
            return dest_dir
        except (OSError, subprocess.SubprocessError) as e:
            return f"Exception during git clone: {e}"

    def get_tools(self) -> list[FunctionTool]:
        """Get the list of tools provided by this plugin."""
        return [self.git_clone_repo]
