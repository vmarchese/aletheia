"""Docker Script Plugin for Aletheia."""

import json
import os
import tempfile
from typing import Annotated

import docker
import structlog
from agent_framework import FunctionTool

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session

logger = structlog.get_logger(__name__)


class DockerScriptPlugin(BasePlugin):
    """Docker Script Plugin for executing scripts."""

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the DockerScriptPlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
            scratchpad: Scratchpad object for writing journal entries
        """
        self.session = session
        self.config = config
        self.name = "DockerScriptPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("dockerscript")
        self.scratchpad = scratchpad

    def sandbox_run(
        self,
        script_folder: Annotated[str, "The folder containing the python script"],
        script: Annotated[str, "The Docker script to execute"],
        args: Annotated[
            dict | None,
            "Script arguments (simple types: str, int, float, bool) passed as environment variables",
        ] = None,
        data: Annotated[
            dict | None,
            "Complex data structures (lists, nested dicts, etc.) written to /scripts/data.json",
        ] = None,
    ):
        """Executes a python script from a folder with optional arguments.

        Args:
            script_folder: Path to the folder containing the script
            script: Name of the script file to execute
            args: Simple key-value arguments passed as environment variables (keys converted to UPPER_CASE)
            data: Complex data structures written to /scripts/data.json for script access

        Returns:
            String output from the script execution (stdout)

        Example:
            sandbox_run(
                "/path/to/skill",
                "check_ip.py",
                args={"ip_address": "10.0.0.1", "profile": "production"},
                data={"security_groups": [...], "rules": [...]}
            )

        Script Access Pattern:
            # Simple args from environment
            import os
            ip_address = os.environ.get('IP_ADDRESS')
            profile = os.environ.get('PROFILE', 'default')

            # Complex data from JSON file
            import json
            from pathlib import Path
            data_file = Path('/scripts/data.json')
            if data_file.exists():
                with open(data_file, 'r') as f:
                    complex_data = json.load(f)
        """
        logger.debug(
            f"DockerScriptPlugin::sandbox_run:: called with script: {script} from folder: {script_folder}"
        )
        if args:
            logger.debug(f"DockerScriptPlugin::sandbox_run:: args: {args}")
        if data:
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: data keys: {list(data.keys())}"
            )

        client = docker.from_env()
        try:
            # Create temp dir and write script to file
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: Creating base temporary directory in {self.config.temp_folder}"
            )
            tmp = tempfile.mkdtemp(dir=self.config.temp_folder)
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: Created base temporary directory at {tmp}"
            )
            tmpfolder = tempfile.TemporaryDirectory(dir=tmp)
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: Creating temporary folder at {tmpfolder.name}"
            )
            os.makedirs(tmpfolder.name, exist_ok=True)
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: Created temporary folder at {tmpfolder.name}"
            )

            script_path = os.path.join(script_folder, "scripts", script)
            temp_script_path = os.path.join(tmpfolder.name, "script.py")
            with open(script_path, encoding="utf-8") as script_file:
                script_content = script_file.read()
                with open(temp_script_path, "w", encoding="utf-8") as temp_script_file:
                    temp_script_file.write(script_content)
            logger.debug(
                f"DockerScriptPlugin::sandbox_run:: Wrote script to {temp_script_path}"
            )

            # Prepare environment variables for simple args
            env_vars = {}
            if args:
                for key, value in args.items():
                    if isinstance(value, (str, int, float, bool)):
                        env_vars[key.upper()] = str(value)
                    else:
                        logger.debug(
                            f"DockerScriptPlugin::sandbox_run:: Skipping non-simple type for env var: {key} (type: {type(value).__name__})"
                        )

            # Write complex data to JSON file
            if data:
                data_path = f"{tmpfolder.name}/data.json"
                os.makedirs(os.path.dirname(data_path), exist_ok=True)
                with open(data_path, "w", encoding="utf-8") as data_file:
                    json.dump(data, data_file, indent=2)
                logger.debug(
                    f"DockerScriptPlugin::sandbox_run:: Wrote data to {data_path}"
                )

            # Execute container with both mechanisms
            logger.debug(
                "DockerScriptPlugin::sandbox_run:: Executing Docker container for script."
            )
            output = client.containers.run(
                image="aletheia-script-executor:latest",
                command=["python", "/scripts/script.py"],
                environment=env_vars,  # Simple args as env vars
                volumes={tmpfolder.name: {"bind": "/scripts", "mode": "ro"}},
                detach=False,
                stdout=True,
                stderr=True,
                remove=True,
            )
            logger.debug(
                "DockerScriptPlugin::sandbox_run:: Script executed successfully."
            )
            return output.decode("utf-8") if isinstance(output, bytes) else str(output)
        except (docker.errors.DockerException, OSError) as e:
            logger.error(
                f"DockerScriptPlugin::sandbox_run:: Error executing script: {e}"
            )
            return f"Error executing script: {e}"

    def get_tools(self) -> list[FunctionTool]:
        """Returns the list of tools provided by the DockerScriptPlugin."""
        return [self.sandbox_run]
