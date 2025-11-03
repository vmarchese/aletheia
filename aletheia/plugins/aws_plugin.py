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

    async def _run_aws_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
        """Helper to run AWS CLI commands and handle output, errors, and saving."""
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
            log_error(f"{log_prefix} Error launching aws cli: {str(e)}")
            return f"Error launching aws cli: {e}"

    @kernel_function(description="Gets AWS profiles available in the system.")
    async def aws_profiles(self) -> str:
        """Launches aws configure list-profiles."""
        command = ["aws", "configure", "list-profiles"]
        return await self._run_aws_command(command, save_key="profiles", log_prefix="AWSPlugin::aws_profiles::")

    @kernel_function(description="Gets EC2 instances in the requested profile")
    async def aws_ec2_instances(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-instances for the given profile."""
        command = ["aws", "ec2", "describe-instances", "--profile", profile]
        return await self._run_aws_command(command, save_key="ec2_describe_instances", log_prefix="AWSPlugin::aws_ec2_instances::")

    @kernel_function(description="Gets Route Tables the requested profile")
    async def aws_ec2_route_tables(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-route-tables for the given profile."""
        command = ["aws", "ec2", "describe-route-tables", "--profile", profile]
        return await self._run_aws_command(command, save_key="ec2_describe_route_tables", log_prefix="AWSPlugin::aws_ec2_route_tables::")

    @kernel_function(description="Gets ELBV2  Load Balancers for the requested profile")
    async def aws_elbv2_load_balancers(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-load-balancers for the given profile."""
        command = ["aws", "elbv2", "describe-load-balancers", "--profile", profile]
        return await self._run_aws_command(command, save_key="elbv2_describe_load_balancers", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    @kernel_function(description="Gets Listeners for the requested ELBV2 Load Balancer ARN and profile")
    async def aws_elbv2_listeners(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-listeners for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-listeners", "--load-balancer-arn", arn, "--profile", profile]
        return await self._run_aws_command(command, save_key="elbv2_describe_listeners", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    @kernel_function(description="Gets the Listener attributes for the requested ELBV2 Listener ARN and profile")
    async def aws_elbv2_listener_attributes(
        self,
        arn: Annotated[str, "The Listener ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-listener attributes for the given profile and listener ARN."""
        command = ["aws", "elbv2", "describe-listener-attributes", "--listener-arn", arn, "--profile", profile]
        return await self._run_aws_command(command, save_key="elbv2_describe_listener_attributes", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    @kernel_function(description="Gets Target groups for the requested ELBV2 Load Balancer ARN and profile")
    async def aws_elbv2_target_groups(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-target-groups for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-target-groups", "--load-balancer-arn", arn, "--profile", profile]
        return await self._run_aws_command(command, save_key="elbv2_describe_target_groups", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    @kernel_function(description="Gets the Target Groups attributes for the requested ELBV2 Target Group ARN and profile")
    async def aws_elbv2_target_group_attributes(
        self,
        arn: Annotated[str, "The Target Group ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-target-group attributes for the given profile and target group ARN."""
        command = ["aws", "elbv2", "describe-target-group-attributes", "--target-group-arn", arn, "--profile", profile]
        return await self._run_aws_command(command, save_key="elbv2_describe_target_group_attributes", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    @kernel_function(description="Gets the VPCs for a profile")
    async def aws_ec2_vpcs(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-vpcs for the given profile."""
        command = ["aws", "ec2", "describe-vpcs", "--profile", profile]
        return await self._run_aws_command(command, save_key="ec2_describe_vpcs", log_prefix="AWSPlugin::aws_vpcs::")

    @kernel_function(description="Gets the VPC endpoints for a profile")
    async def aws_ec2_vpc_endpoints(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-vpc-endpoints for the given profile."""
        command = ["aws", "ec2", "describe-vpc-endpoints", "--profile", profile]
        return await self._run_aws_command(command, save_key="ec2_describe_vpc_endpoints", log_prefix="AWSPlugin::aws_vpc_endpoints::")
