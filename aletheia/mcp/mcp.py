"""
Module for defining MCP server configurations.
"""
from pathlib import Path
import yaml

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool


class MCPServer:
    """Class representing an MCP server configuration."""
    def __init__(self,
                 name: str,
                 agents: str,
                 description: str,
                 server_type: str,
                 url: str = None,
                 bearer: str = None,
                 command: str = None,
                 args: list[str] = None,
                 env: dict = None):
        self.url = url
        self.bearer = bearer
        self.description = description
        self.name = name
        self.agents = agents
        self.server_type = server_type
        self.command = command
        self.args = args if args is not None else []
        self.env = env if env is not None else {}


def load_mcp_tools(agent: str, yaml_file: str = None) -> list[MCPServer]:
    """Load MCP server configurations from a YAML file.

    Args:
        yaml_file: Path to the YAML file containing MCP server configurations.
    """

    if yaml_file is None:
        package_dir = Path(__file__).parent
        yaml_file = package_dir / "mcp_servers.yaml"

    with open(yaml_file, 'r', encoding="utf-8") as file:
        content = file.read()
        servers_data = yaml.safe_load(content)
        servers = []
        for server_info in servers_data.get("mcp_servers", []):
            allowed_agents = server_info.get("agents", "").split(",")
            if agent not in allowed_agents:
                continue
            server = MCPServer(
                name=server_info.get("name"),
                agents=server_info.get("agents"),
                url=server_info.get("url"),
                description=server_info.get("description"),
                bearer=server_info.get("bearer"),
                server_type=server_info.get("type"),
                command=server_info.get("command"),
                args=server_info.get("args", []),
                env=server_info.get("env", {})
            )
            servers.append(server)

        tools = []
        for server in servers:
            if server.server_type == "stdio":
                tool = MCPStdioTool(
                    name=f"MCP Stdio Tool - {server.name}",
                    description=server.description,
                    command=server.command,
                    args=server.args
                )
                tools.append(tool)
            elif server.server_type == "streamable_http":
                tool = MCPStreamableHTTPTool(
                    name=f"MCP Streamable HTTP Tool - {server.name}",
                    description=server.description,
                    url=server.url,
                    headers={"Authorization": f"Bearer {server.bearer}"} if server.bearer else {}
                )
                tools.append(tool)
        return tools
