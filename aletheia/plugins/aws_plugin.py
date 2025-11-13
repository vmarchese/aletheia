import json
from typing import Annotated, List

from agent_framework import ai_function, ToolProtocol

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad import Scratchpad
from aletheia.plugins.base import BasePlugin


class AWSPlugin(BasePlugin):

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
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
        self.scratchpad = scratchpad

    def _run_aws_command(self, command: list, save_key: str = None, log_prefix: str = "") -> str:
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

#    @ai_function(description="Gets AWS profiles available in the system.")
    def aws_profiles(self) -> str:
        """Launches aws configure list-profiles."""
        command = ["aws", "configure", "list-profiles"]
        return self._run_aws_command(command, save_key="profiles", log_prefix="AWSPlugin::aws_profiles::")

#    @ai_function(description="Gets EC2 instances in the requested profile")
    def aws_ec2_instances(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-instances for the given profile."""
        command = ["aws", "ec2", "describe-instances", "--profile", profile]
        return self._run_aws_command(command, save_key="ec2_describe_instances", log_prefix="AWSPlugin::aws_ec2_instances::")

#    @ai_function(description="Gets Route Tables the requested profile")
    def aws_ec2_route_tables(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-route-tables for the given profile."""
        command = ["aws", "ec2", "describe-route-tables", "--profile", profile]
        return self._run_aws_command(command, save_key="ec2_describe_route_tables", log_prefix="AWSPlugin::aws_ec2_route_tables::")

#    @ai_function(description="Gets ELBV2  Load Balancers for the requested profile")
    def aws_elbv2_load_balancers(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-load-balancers for the given profile."""
        command = ["aws", "elbv2", "describe-load-balancers", "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_load_balancers", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

#    @ai_function(description="Gets the attributes for the requested ELBV2 Load Balancer ARN and profile")
    def aws_elbv2_load_balancer_attributes(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-load-balancer-attributes for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-load-balancer-attributes", "--load-balancer-arn", arn, "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_load_balancer_attributes", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

    def aws_elbv2_security_groups(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-load-balancer-attributes for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-load-balancers", "--load-balancer-arn", arn, "--profile", profile, "--query", "LoadBalancers[0].SecurityGroups", "--output", "json"]
        return self._run_aws_command(command, save_key="elbv2_security_groups", log_prefix="AWSPlugin::aws_elbv2_security_groups::")        

#    @ai_function(description="Gets Listeners for the requested ELBV2 Load Balancer ARN and profile")
    def aws_elbv2_listeners(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-listeners for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-listeners", "--load-balancer-arn", arn, "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_listeners", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

#    @ai_function(description="Gets the Listener attributes for the requested ELBV2 Listener ARN and profile")
    def aws_elbv2_listener_attributes(
        self,
        arn: Annotated[str, "The Listener ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-listener attributes for the given profile and listener ARN."""
        command = ["aws", "elbv2", "describe-listener-attributes", "--listener-arn", arn, "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_listener_attributes", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

#    @ai_function(description="Gets Target groups for the requested ELBV2 Load Balancer ARN and profile")
    def aws_elbv2_target_groups(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-target-groups for the given profile and load balancer ARN."""
        command = ["aws", "elbv2", "describe-target-groups", "--load-balancer-arn", arn, "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_target_groups", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

#    @ai_function(description="Gets the Target Groups attributes for the requested ELBV2 Target Group ARN and profile")
    def aws_elbv2_target_group_attributes(
        self,
        arn: Annotated[str, "The Target Group ARN"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws elbv2 describe-target-group attributes for the given profile and target group ARN."""
        command = ["aws", "elbv2", "describe-target-group-attributes", "--target-group-arn", arn, "--profile", profile]
        return self._run_aws_command(command, save_key="elbv2_describe_target_group_attributes", log_prefix="AWSPlugin::aws_elbv2_load_balancers::")

#    @ai_function(description="Gets the VPCs for a profile")
    def aws_ec2_vpcs(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-vpcs for the given profile."""
        command = ["aws", "ec2", "describe-vpcs", "--profile", profile]
        return self._run_aws_command(command, save_key="ec2_describe_vpcs", log_prefix="AWSPlugin::aws_vpcs::")

#    @ai_function(description="Gets the VPC endpoints for a profile")
    def aws_ec2_vpc_endpoints(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws ec2 describe-vpc-endpoints for the given profile."""
        command = ["aws", "ec2", "describe-vpc-endpoints", "--profile", profile]
        return self._run_aws_command(command, save_key="ec2_describe_vpc_endpoints", log_prefix="AWSPlugin::aws_vpc_endpoints::")

#    @ai_function(description="Gets the caller identity")
    def aws_sts_caller_identity(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws sts get-caller-identity for the given profile."""
        command = ["aws", "sts", "get-caller-identity", "--profile", profile, "--output", "text"]
        return self._run_aws_command(command, save_key="sts_get_caller_identity", log_prefix="AWSPlugin::aws_sts_caller_identity::")

#    @ai_function(description="Gets the S3 Buckets for a profile")
    def aws_s3_buckets(
        self,
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws s3 ls for the given profile."""
        command = ["aws", "s3", "ls", "--profile", profile]
        return self._run_aws_command(command, save_key="s3_ls", log_prefix="AWSPlugin::aws_s3_buckets::")

#    @ai_function(description="Gets the ELBV2 Connection Logs from a bucket for a profile")
    def aws_elbv2_get_connection_logs(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        caller_identity: Annotated[str, "The sts caller identity"],
        cutoff_date: Annotated[str, "The cutoff date in YYYY-MM-DDTHH:mm:ss format"] = "",
        region: Annotated[str, "The AWS region"] = "eu-central-1",
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws s3 ls for the given profile."""

        log_debug(f"AWSPlugin::aws_elbv2_connection_logs:: Starting with bucket: {bucket}, cutoff_date: {cutoff_date}, profile: {profile}")
        # Set default cutoff_date to now - 2 days if not provided
        if cutoff_date is None or cutoff_date.strip() == "":
            log_debug("AWSPlugin::aws_elbv2_connection_logs:: No cutoff_date provided, defaulting to 24 hours ago")
            from datetime import datetime, timedelta
            cutoff_dt = datetime.utcnow() - timedelta(days=1)
            cutoff_date = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")


        # Calculating path prefix from cutoff date
        date_segment = ""
        if cutoff_date:
            date_parts = cutoff_date.split("T")
            if len(date_parts) != 2:
                return "Error: cutoff_date must be in YYYY-MM-DDTHH:mm:ss format"
            date_segment = date_parts[0].replace("-", "/")
            time_segment = date_parts[1].split(":")[0]

        log_debug(f"AWSPlugin::aws_elbv2_connection_logs:: Using cutoff_date: {cutoff_date}")
        log_debug(f"AWSPlugin::aws_elbv2_connection_logs:: Using date_segment: {date_segment}")
        prefix = f"AWSLogs/{caller_identity}/elasticloadbalancing/{region}/{date_segment}/"

        # List s3 objects by last modified date
        command = ["aws", "s3api", "list-objects-v2",
                   "--bucket", bucket,
                   "--prefix", prefix,
                   "--query", f"Contents[?LastModified>=`{cutoff_date}`].Key",
                   "--profile", profile,
                   "--output", "json"]
        # List objects in S3
        s3_keys_json = self._run_aws_command(command, save_key="s3_lsv2", log_prefix="AWSPlugin::aws_elbv2_connection_logs::")
        try:
            keys = json.loads(s3_keys_json)
        except Exception as e:
            log_error(f"AWSPlugin::aws_elbv2_connection_logs:: Failed to parse S3 keys: {e}")
            return s3_keys_json

        if not keys or not isinstance(keys, list):
            log_debug("AWSPlugin::aws_elbv2_connection_logs:: No log files found to download.")
            return json.dumps({"downloaded": [], "message": "No log files found."})

        # Download each log file to aws_s3_downloads
        dest_dir = self.session.data_dir / "aws_s3_downloads"
        downloaded = []
        for key in keys:
            basename_key = key.split("/")[-1]
            destination = f"{dest_dir}/{basename_key}"
            log_debug(f"AWSPlugin::aws_elbv2_connection_logs:: Downloading s3://{bucket}/{key} to {destination}")
            cp_command = [
                "aws", "s3", "cp", f"s3://{bucket}/{key}", destination, "--profile", profile
            ]
            self._run_aws_command(cp_command, save_key="s3_cp", log_prefix="AWSPlugin::aws_elbv2_connection_logs::")
            downloaded.append(destination)

        if self.session:
            saved = self.session.save_data(SessionDataType.INFO, "s3_cp", str(downloaded))
            log_debug(f"AWSPlugin::aws_elbv2_connection_logs:: Saved {str(downloaded)} to {saved}")

        if self.scratchpad:
            self.scratchpad.write_journal_entry(self.name, 
                                                f"Downloaded {len(downloaded)} connection log files from bucket {bucket} for profile {profile}.",
                                                str(downloaded))

        return json.dumps({"downloaded": downloaded, "count": len(downloaded)})

#    @ai_function(description="Retrieves a S3 Object, file or connection log from a bucket for a profile")
    def aws_s3_cp(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        key: Annotated[str, "The S3 Object key"],
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Copies a S3 Object to a local directory."""

        dest_dir = self.session.data_dir / "aws_s3_downloads"
        basename_key = key.split("/")[-1]
        destination = f"{dest_dir}/{basename_key}"
        log_debug(f"AWSPlugin::aws_s3_cp:: Downloading s3://{bucket}/{key} to {destination}")

        command = ["aws", "s3", "cp", f"s3://{bucket}/{key}", destination, "--profile", profile]
        self._run_aws_command(command, save_key="s3_cp", log_prefix="AWSPlugin::aws_s3_cp::")

        if self.session:
            self.session.save_data(SessionDataType.INFO, "s3_cp", f"Saved s3://{bucket}/{key} to {destination}")

        if self.scratchpad:
            self.scratchpad.write_journal_entry(self.name, 
                                                f"Copied S3 object s3://{bucket}/{key}",
                                                f"Copied S3 object s3://{bucket}/{key} to {destination}.")
        return destination

#    @ai_function(description="List the ELBV2 Connection Logs from a bucket for a profile")
    def aws_elbv2_list_connection_logs(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        caller_identity: Annotated[str, "The sts caller identity"],
        cutoff_date: Annotated[str, "The cutoff date in YYYY-MM-DDTHH:mm:ss format"] = "",
        region: Annotated[str, "The AWS region"] = "eu-central-1",
        profile: Annotated[str, "The default profile"] = "default",
    ) -> str:
        """Launches aws s3 ls for the given profile."""

        log_debug(f"AWSPlugin::aws_elbv2_list_connection_logs:: Starting with bucket: {bucket}, cutoff_date: {cutoff_date}, profile: {profile}")
        # Set default cutoff_date to now - 2 days if not provided
        if cutoff_date is None or cutoff_date.strip() == "":
            log_debug("AWSPlugin::aws_elbv2_list_connection_logs:: No cutoff_date provided, defaulting to 24 hours ago")
            from datetime import datetime, timedelta
            cutoff_dt = datetime.utcnow() - timedelta(days=1)
            cutoff_date = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")


        # Calculating path prefix from cutoff date
        date_segment = ""
        if cutoff_date:
            date_parts = cutoff_date.split("T")
            if len(date_parts) != 2:
                return "Error: cutoff_date must be in YYYY-MM-DDTHH:mm:ss format"
            date_segment = date_parts[0].replace("-", "/")
            time_segment = date_parts[1].split(":")[0]

        log_debug(f"AWSPlugin::aws_elbv2_list_connection_logs:: Using cutoff_date: {cutoff_date}")
        log_debug(f"AWSPlugin::aws_elbv2_list_connection_logs:: Using date_segment: {date_segment}")
        prefix = f"AWSLogs/{caller_identity}/elasticloadbalancing/{region}/{date_segment}/"

        # List s3 objects by last modified date
        command = ["aws", "s3api", "list-objects-v2",
                   "--bucket", bucket,
                   "--prefix", prefix,
                   "--query", f"Contents[?LastModified>=`{cutoff_date}`].Key",
                   "--profile", profile,
                   "--output", "json"]
        # List objects in S3
        s3_keys_json = self._run_aws_command(command, save_key="s3_lsv2", log_prefix="AWSPlugin::aws_elbv2_connection_logs::")
        try:
            keys = json.loads(s3_keys_json)
        except Exception as e:
            log_error(f"AWSPlugin::aws_elbv2_connection_logs:: Failed to parse S3 keys: {e}")
            return s3_keys_json

        if not keys or not isinstance(keys, list):
            log_debug("AWSPlugin::aws_elbv2_connection_logs:: No log files found to download.")
            return json.dumps({"downloaded": [], "message": "No log files found."})

        if self.session:
            saved = self.session.save_data(SessionDataType.INFO, "s3_ls", str(keys))
            log_debug(f"AWSPlugin::aws_elbv2_list_connection_logs:: List: {str(keys)} to {saved}")


        return keys

    
    def aws_ec2_describe_eni_security_groups(
        self,
        profile: Annotated[str, "The default profile"] = "default",
        private_ip: Annotated[str, "The private IP address of the ENI"] = ""
    ) -> str:
        """Launches aws ec2 describe-network-interfaces for the given profile and private IP to find security groups."""
        command = ["aws", "ec2", "describe-network-interfaces", "--profile", profile]
        if private_ip and private_ip.strip() != "":
            command += ["--filters", f"Name=private-ip-address,Values={private_ip}"]
        command.extend(["--query", "NetworkInterfaces[0].Groups[*].[GroupId,GroupName]", "--output", "json" ])
        return self._run_aws_command(command, save_key="ec2_describe_eni_security_groups", log_prefix="AWSPlugin::aws_ec2_describe_eni_security_groups::")

    def aws_ec2_describe_security_group_inbound_rules(
        self,
        profile: Annotated[str, "The default profile"] = "default",
        group_id: Annotated[str, "The security group ID"] = ""
    ) -> str:
        """Launches aws ec2 describe-security-groups for the given profile and security group ID."""
        command = ["aws", "ec2", "describe-security-groups", "--profile", profile]
        if group_id and group_id.strip() != "":
            command += ["--group-ids", group_id]
        command.extend(["--query","SecurityGroups[0].IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[].CidrIp,UserIdGroupPairs[].GroupId]", "--output", "json"])
        return self._run_aws_command(command, save_key="ec2_describe_security_group_inbound_rules", log_prefix="AWSPlugin::aws_ec2_describe_security_group_inbound_rules::")


    def aws_ec2_describe_security_group_outbound_rules(
        self,
        profile: Annotated[str, "The default profile"] = "default",
        group_id: Annotated[str, "The security group ID"] = ""
    ) -> str:
        """Launches aws ec2 describe-security-groups for the given profile and security group ID."""
        command = ["aws", "ec2", "describe-security-groups", "--profile", profile]
        if group_id and group_id.strip() != "":
            command += ["--group-ids", group_id]
        command.extend(["--query","SecurityGroups[0].IpPermissionsEgress[*].[IpProtocol,FromPort,ToPort,IpRanges[].CidrIp,UserIdGroupPairs[].GroupId]", "--output", "json"])
        return self._run_aws_command(command, save_key="ec2_describe_security_group_outbound_rules", log_prefix="AWSPlugin::aws_ec2_describe_security_group_outbound_rules::"
    )


    def get_tools(self) -> List[ToolProtocol]:
        return [
            self.aws_profiles,
            self.aws_ec2_instances,
            self.aws_ec2_route_tables,
            self.aws_ec2_describe_eni_security_groups,
            self.aws_ec2_describe_security_group_inbound_rules,
            self.aws_ec2_describe_security_group_outbound_rules,
            self.aws_elbv2_load_balancers,
            self.aws_elbv2_load_balancer_attributes,
            self.aws_elbv2_listeners,
            self.aws_elbv2_listener_attributes,
            self.aws_elbv2_target_groups,
            self.aws_elbv2_target_group_attributes,
            self.aws_elbv2_security_groups,
            self.aws_ec2_vpcs,
            self.aws_ec2_vpc_endpoints,
            self.aws_sts_caller_identity,
            self.aws_s3_buckets,
            self.aws_elbv2_get_connection_logs,
            self.aws_s3_cp,
            self.aws_elbv2_list_connection_logs,
        ]

    
