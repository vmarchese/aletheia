import json
from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.base import BasePlugin


class NetworkPlugin(BasePlugin):

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the NetworkPlugin.
        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "NetworkPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("network_plugin")
        self.scratchpad = scratchpad

    def _run_net_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
        """Helper to run  network commands and handle output, errors, and saving."""
        try:
            import subprocess
            log_debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True)
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": ' '.join(command) + f" failed: {error_msg}"
                })
            output = process.stdout.decode()
            if self.session and save_key:
                saved = self.session.save_data(SessionDataType.INFO, save_key, output)
                log_debug(f"{log_prefix} Saved output to {saved}")
            return output
        except Exception as e:
            log_error(f"{log_prefix} Error launching command : {str(e)}")
            return f"Error launching command: {e}"

    def is_ip_in_cidr(
            self,
            ip_address: Annotated[str, "The IP address to check"]) -> bool:
        """Check if the given IP address is within the specified CIDR block."""
        import ipaddress
        cidr_block = self.session.get_data(SessionDataType.INFO, "cidr_block")
        if not cidr_block:
            log_error("NetworkPlugin::is_ip_in_cidr:: No CIDR block found in session data")
            return False
        try:
            ip = ipaddress.ip_address(ip_address)
            network = ipaddress.ip_network(cidr_block, strict=False)
            return ip in network
        except ValueError as e:
            log_error(f"NetworkPlugin::is_ip_in_cidr:: Invalid IP address or CIDR block: {str(e)}")
            return False

    def nslookup(
            self,
            domain: Annotated[str, "The domain name to look up"]) -> str:
        """Perform an nslookup for the given domain name."""
        command = ["nslookup", domain]
        return self._run_net_command(command, save_key="nslookup", log_prefix="NetworkPlugin::nslookup::")

    def ping(
            self,
            target: Annotated[str, "The host to ping"]):
        """Ping the specified host a given number of times."""
        command = ["ping", "-c", "3", target]
        return self._run_net_command(command, save_key="ping", log_prefix="NetworkPlugin::ping::")


       


    def get_tools(self) -> List[ToolProtocol]:
        return [
            self.is_ip_in_cidr,
            self.nslookup,
            self.ping
        ]

    
