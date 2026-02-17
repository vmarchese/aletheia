"""SecurityPlugin: A plugin to perform various security-related operations such as
nmap, httpx, nikto, testssl, sslscan.
"""

import json
import subprocess
from typing import Annotated

import structlog
from agent_framework import FunctionTool

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session, SessionDataType
from aletheia.utils.command import sanitize_command

logger = structlog.get_logger(__name__)


class SecurityPlugin(BasePlugin):
    """plugin for security operations."""

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the SecurityPlugin.
        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "SecurityPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("security")
        self.scratchpad = scratchpad

        # find httpx ignoring the one in the virtualenv
        try:
            httpx_paths = (
                subprocess.run(
                    ["which", "-a", "httpx"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                .stdout.strip()
                .splitlines()
            )
            self.httpx_path = None
            for path in httpx_paths:
                if "aletheia" not in path:
                    self.httpx_path = path
                    break
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"SecurityPlugin::__init__:: Error finding httpx: {str(e)}")
            self.httpx_path = "httpx"  # fallback to default

    def _run_command(
        self, command: list, save_key: str = None, log_prefix: str = ""
    ) -> str:
        """Helper to run  security commands and handle output, errors, and saving."""
        try:
            logger.debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(
                args=sanitize_command(command), capture_output=True, check=False
            )
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps(
                    {"error": " ".join(command) + f" failed: {error_msg}"}
                )
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                logger.debug(f"{log_prefix} Saved output to {saved}")
            return output
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"{log_prefix} Error launching command : {str(e)}")
            return f"Error launching command: {e}"

    def httpx(
        self, target: Annotated[str, "Target domain or IP for httpx scan"]
    ) -> str:
        """Run httpx against a target to identify live hosts and gather HTTP info."""
        command = [
            self.httpx_path,
            "-silent",
            "-title",
            "-status-code",
            "-tech-detect",
            "-cdn",
            "-ip",
            "-cname",
            "-j",
            "-http2",
            "-u",
            target,
        ]
        return self._run_command(
            command, save_key=f"httpx_{target}", log_prefix="Security::httpx::"
        )

    def sslscan(
        self, target: Annotated[str, "Target domain or IP for sslscan scan"]
    ) -> str:
        """Run sslscan against a target to identify SSL/TLS configuration."""
        command = ["sslscan", "--no-colour", target]
        return self._run_command(
            command, save_key=f"sslscan_{target}", log_prefix="Security::sslscan::"
        )

    def nmap(self, target: Annotated[str, "Target domain or IP for nmap scan"]) -> str:
        """Run nmap against a target to identify open ports and services."""
        command = ["nmap", "-sT", "-sV", target]
        return self._run_command(
            command, save_key=f"nmap_{target}", log_prefix="Security::nmap::"
        )

    def get_tools(self) -> list[FunctionTool]:
        """Returns a list of tools provided by the SecurityPlugin."""
        return [self.httpx, self.sslscan, self.nmap]
