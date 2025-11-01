import json
from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader


class AWSPlugin:
    """Semantic Kernel plugin for AWS operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the AWSPlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.session = session
        self.config = config
        self.name = "AWSPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("aws_plugin")

    @kernel_function(description="Gets AWS profiles available in the system.")
    async def aws_profiles(
        self,
    ) -> str:
        """Launches aws configure list-profiles."""
        try:
            log_debug(f"AWSPlugin::aws_profiles:: Launching aws configure list-profiles")
            import subprocess

            # Construct the command to run aws cli
            command = [
                "aws", 
                "configure",
                "list-profiles"]

            # Run the command and capture output
            log_debug(f"AWSPlugin::aws_profiles:: Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True)

            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": f"aws configure list-profiles failed: {error_msg}"
                })

            saved = ""
            description = process.stdout.decode()
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, "profiles", description)
                log_debug(f"AWSPlugin::aws_profiles:: Saved profiles description to {saved}")

            return description
        except Exception as e:
            log_error(f"Error launching aws cli: {str(e)}")
            return f"Error launching aws cli: {e}"

    @kernel_function(description="Gets EC2 instances in the requested profile")
    async def aws_ec2_instances(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-instances for the given profile."""
        try:
            log_debug(f"AWSPlugin::aws_ec2_instances:: Launching aws ec2 describe-instances for profile: {profile}")
            import subprocess

            # Construct the command to run aws cli
            command = [
                "aws", 
                "ec2",
                "describe-instances",
                "--profile",
                profile
            ]

            # Run the command and capture output
            log_debug(f"AWSPlugin::aws_ec2_instances:: Running command: [{' '.join(command)}]")
            process = subprocess.run(args=command, capture_output=True)
            if process.returncode != 0:
                error_msg = process.stderr.decode().strip()
                return json.dumps({
                    "error": ' '.join(command) + f" failed: {error_msg}"
                })            


            saved = ""
            description = process.stdout.decode()
            if self.session:
                saved = self.session.save_data(SessionDataType.INFO, "ec2_describe_instances", description)
                log_debug(f"AWSPlugin::aws_ec2_instances:: Saved EC2 instances description to {saved}")

            return description
        except Exception as e:
            log_error(f"Error launching aws cli: {str(e)}")
            return f"Error launching aws cli: {e}"