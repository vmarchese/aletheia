"""SysDiag Plugin Module
provides df, free, ps, iotop, ss,...
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


class SysDiagPlugin(BasePlugin):
    """plugin for security operations."""

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the SecurityPlugin.
        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "SysDiagPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("sysdiag")
        self.scratchpad = scratchpad

    def _run_remote_command(
        self,
        user: str,
        remote_server: str,
        command: list,
        save_key: str = None,
        log_prefix: str = "",
    ) -> str:
        """Helper to run  security commands and handle output, errors, and saving."""
        try:
            logger.debug(
                f"{log_prefix} Preparing to run remote command [{' '.join(command)}] on {remote_server} as {user}"
            )
            rcmd = ["ssh", f"{user}@{remote_server}"]
            rcmd.extend(command)
            logger.debug(f"{log_prefix} Running command: [{' '.join(rcmd)}]")
            process = subprocess.run(
                args=sanitize_command(rcmd), capture_output=True, check=True
            )
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({"error": " ".join(rcmd) + f" failed: {error_msg}"})
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                logger.debug(f"{log_prefix} Saved output to {saved}")
            return output
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"{log_prefix} Error launching command : {str(e)}")
            return f"Error launching command: {e}"

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

    def scp(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        source_path: Annotated[str, "Source file path"],
        destination: Annotated[str, "Destination file path"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """Securely copy files between hosts on a network using scp command.
        Args:
         remote_server: Remote server hostname or IP
         source_path: Source file path on the remote server
         destination: Destination file path on the local machine
        Returns:
            Output of the scp command.
        """
        command = ["scp", f"{user}@{remote_server}:{source_path}", destination]
        return self._run_command(command, log_prefix="SysDiagPlugin::scp::")

    def df(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get disk space usage using df command.
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["df", "-hT"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="disk_usage",
            log_prefix="SysDiagPlugin::df::",
        )

    def inodes(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get inode usage using df command.
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["df", "-hi"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="inode_usage",
            log_prefix="SysDiagPlugin::inodes::",
        )

    def system_load(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get system load using ps command.
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["ps", "-eo", "pid,ppid,cmd,%cpu,%mem", "--sort=-%cpu"]
        psout = self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="system_load",
            log_prefix="SysDiagPlugin::system_load::",
        )
        command = ["uptime"]
        uptimeout = self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="system_load",
            log_prefix="SysDiagPlugin::system_load::",
        )
        return (
            f"Uptime Information:\n{uptimeout}\n\nTop Processes by CPU Usage:\n{psout}"
        )

    def memory_load(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get Memory load using ps command.
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["ps", "-eo", "pid,ppid,cmd,%cpu,%mem", "--sort=-%mem"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="memory_load",
            log_prefix="SysDiagPlugin::memory_load::",
        )

    def iostat(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get IO statistics using iostat command
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["iostat", "-xz", "1", "3"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="io_stat",
            log_prefix="SysDiagPlugin::io_stat::",
        )

    def ss(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get Network statistics using ss command
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["ss", "-tunap"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="ss",
            log_prefix="SysDiagPlugin::ss::",
        )

    def journalctl(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get Systemd journal logs using journalctl command
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["journalctl", "-p", "0..3", "-n", "200"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="journalctl",
            log_prefix="SysDiagPlugin::journalctl::",
        )

    def systemctl_failed(
        self,
        remote_server: Annotated[str, "Remote server hostname or IP"],
        user: Annotated[str, "Username for remote host"] = "root",
    ) -> str:
        """
        Get failed systemd services using systemctl command
        Args:
         remote_server: Remote server hostname or IP
         user: Username for remote host
        """
        command = ["systemctl", "list-units", "--failed"]
        return self._run_remote_command(
            command=command,
            user=user,
            remote_server=remote_server,
            save_key="systemctl_failed",
            log_prefix="SysDiagPlugin::systemctl_failed::",
        )

    def get_tools(self) -> list[FunctionTool]:
        """Returns a list of tools provided by the SecurityPlugin."""
        return [
            self.scp,
            self.df,
            self.inodes,
            self.system_load,
            self.memory_load,
            self.iostat,
            self.ss,
            self.journalctl,
            self.systemctl_failed,
        ]
