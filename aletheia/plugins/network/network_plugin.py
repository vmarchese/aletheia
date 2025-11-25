"""NetworkPlugin: A plugin to perform various network-related operations such as
nslookup, dig, ping, traceroute, ifconfig, netstat, and whois.
"""
import json
import subprocess
import ipaddress
from typing import Annotated, List

from agent_framework import ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.plugins.base import BasePlugin
from aletheia.utils.command import sanitize_command


class NetworkPlugin(BasePlugin):
    """plugin for network operations."""
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
            log_debug(f"{log_prefix} Running command: [{' '.join(command)}]")
            process = subprocess.run(args=sanitize_command(command), capture_output=True, check=False)
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
        except (OSError, subprocess.SubprocessError) as e:
            log_error(f"{log_prefix} Error launching command : {str(e)}")
            return f"Error launching command: {e}"

    def is_ip_in_cidr(
            self,
            ip_address: Annotated[str, "The IP address to check"]) -> bool:
        """Check if the given IP address is within the specified CIDR block."""
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

    def dig(
            self,
            domain: Annotated[str, "The domain name to look up"],
            query_type: Annotated[str, "The type of DNS record to query"] = "A",
            dns_server: Annotated[str, "The DNS server to use"] = None) -> str:
        """Perform an dig for the given domain name."""
        command = ["dig"]
        if dns_server:
            command.extend(["@"+dns_server])
        command.append(domain)
        command.extend(["-t", query_type])

        return self._run_net_command(command, save_key="dig", log_prefix="NetworkPlugin::dig::")

    def ping(
            self,
            target: Annotated[str, "The host to ping"]):
        """Ping the specified host a given number of times."""
        command = ["ping", "-c", "3", target]
        return self._run_net_command(command, save_key="ping", log_prefix="NetworkPlugin::ping::")

    def traceroute(self, target: str) -> str:
        """Perform a traceroute to the specified target."""
        command = ["traceroute", "-w", "2", target]
        return self._run_net_command(command, save_key="traceroute", log_prefix="NetworkPlugin::traceroute::")

    def ifconfig(self) -> str:
        """Perform a ifconfig to get network interfaces."""
        command = ["ifconfig"]
        return self._run_net_command(command, save_key="ifconfig", log_prefix="NetworkPlugin::ifconfig::")

    def netstat(self) -> str:
        """Check network statistics."""
        command = ["netstat", "-n", "-p", "TCP"]
        return self._run_net_command(command, save_key="netstat", log_prefix="NetworkPlugin::netstat::")

    def whois(self,
              target: Annotated[str, "The host to lookup"]):
        """Perform a whois lookup for the given target."""
        command = ["whois", target]
        return self._run_net_command(command, save_key="whois", log_prefix="NetworkPlugin::whois::")

    def openssl_sclient(self,
                        target: Annotated[str, "The host to connect to"],
                        port: Annotated[int, "The port to connect to"] = 443) -> str:
        """Perform an openssl s_client connection to the given target and port."""
        command = ["openssl", "s_client", "-connect", f"{target}:{port}"]
        return self._run_net_command(command, save_key="openssl_sclient", log_prefix="NetworkPlugin::openssl_sclient::")

    def get_tools(self) -> List[ToolProtocol]:
        """Get the list of tools provided by this plugin."""
        return [
            self.is_ip_in_cidr,
            self.nslookup,
            self.dig,
            self.ping,
            self.traceroute,
            self.ifconfig,
            self.netstat,
            self.whois,
            self.openssl_sclient
        ]
