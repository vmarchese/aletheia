"""AWS Plugin for Aletheia using boto3/botocore."""
import os
import tempfile
from typing import Annotated, List

import docker

from agent_framework import ToolProtocol

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session
from aletheia.utils.logging import log_debug, log_error


class DockerScriptPlugin(BasePlugin):
    """Docker Script Plugin for executing scripts."""

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the AWSPlugin.

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

    def sandbox_run(self,
                    script_folder: Annotated[str, "The folder containing the python script"],
                    script: Annotated[str, "The Docker script to execute"]):
        """Executes a python script from a folder"""
        log_debug(f"DockerScriptPlugin::execute_script:: called with script: {script} from folder: {script_folder}")
        client = docker.from_env()
        try:
            # create temp dir and write script to file
            tmpfolder = tempfile.TemporaryDirectory(dir=self.config.temp_folder)
            os.makedirs(tmpfolder.name, exist_ok=True)

            with open(f"{script_folder}/scripts/{script}", 'r', encoding='utf-8') as script_file:
                script = script_file.read()
                with open(f"{tmpfolder.name}/script.py", 'w', encoding='utf-8') as temp_script_file:
                    temp_script_file.write(script)
            
                output = client.containers.run(
                    image="aletheia-script-executor:latest",
                    command=["python", "/scripts/script.py"],
                    volumes={tmpfolder.name: {'bind': '/scripts', 'mode': 'ro'}},
                    detach=False,
                    stdout=True,
                    stderr=True,
                    remove=True
                )
                return output.decode("utf-8") if isinstance(output, bytes) else str(output)
        except (docker.errors.DockerException, OSError, IOError) as e:
            log_error(f"DockerScriptPlugin::execute_script:: Error executing script: {e}")
            return f"Error executing script: {e}"

    def get_tools(self) -> List[ToolProtocol]:
        """Returns the list of tools provided by the DockerScriptPlugin."""
        return [
            self.sandbox_run
        ]
