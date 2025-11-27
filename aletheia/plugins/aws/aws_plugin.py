"""AWS Plugin for Aletheia using boto3/botocore."""
import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional

import boto3
from botocore.exceptions import ProfileNotFound

from agent_framework import ToolProtocol

from aletheia.config import Config
from aletheia.plugins.base import BasePlugin
from aletheia.plugins.loader import PluginInfoLoader
from aletheia.plugins.scratchpad.scratchpad import Scratchpad
from aletheia.session import Session, SessionDataType
from aletheia.utils.logging import log_debug, log_error


class AWSPlugin(BasePlugin):
    """AWS Plugin for Aletheia using boto3/botocore instead of AWS CLI."""

    def __init__(self, config: Config, session: Session, scratchpad: Scratchpad):
        """Initialize the AWSPlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
            scratchpad: Scratchpad object for writing journal entries
        """
        self.session = session
        self.config = config
        self.name = "AWSPlugin"
        loader = PluginInfoLoader()
        self.instructions = loader.load("aws")
        self.scratchpad = scratchpad

        # Cache for boto3 sessions per profile
        self._sessions: Dict[str, boto3.Session] = {}

    def _get_session(self, profile: str = "default") -> boto3.Session:
        """Get or create a boto3 Session for the specified profile.

        Args:
            profile: AWS profile name

        Returns:
            boto3.Session configured for the profile
        """
        if profile not in self._sessions:
            try:
                self._sessions[profile] = boto3.Session(profile_name=profile)
            except ProfileNotFound as e:
                log_error(f"AWS profile '{profile}' not found: {e}")
                raise
        return self._sessions[profile]

    def _handle_aws_error(self, error: Exception, operation: str) -> str:
        """Handle AWS-related errors and return a JSON error response.

        Args:
            error: The exception that occurred
            operation: Name of the operation that failed

        Returns:
            JSON string with error details
        """
        error_msg = f"{operation} failed: {str(error)}"
        log_error(f"AWSPlugin::{operation}:: {error_msg}")

        return json.dumps(
            {"error": error_msg, "type": type(error).__name__, "operation": operation}
        )

    def _save_response(
        self, data: Any, save_key: str, log_prefix: str = ""
    ) -> Optional[str]:
        """Save response data to session if session is available.

        Args:
            data: Data to save (will be JSON serialized)
            save_key: Key to save the data under
            log_prefix: Prefix for log messages

        Returns:
            Path where data was saved, or None if session unavailable
        """
        if self.session:
            json_data = json.dumps(data, indent=2, default=str)
            saved_path = self.session.save_data(SessionDataType.INFO, save_key, json_data)
            log_debug(f"{log_prefix} Saved output to {saved_path}")
            return str(saved_path)
        return None

    def aws_profiles(self) -> str:
        """Get AWS profiles available in the system.

        Returns:
            JSON string with list of profile names
        """
        try:
            # Read profiles from ~/.aws/config and ~/.aws/credentials
            profiles = boto3.Session().available_profiles
            self._save_response(profiles, "profiles", "AWSPlugin::aws_profiles::")
            return json.dumps(profiles)
        except Exception as e:
            return self._handle_aws_error(e, "aws_profiles")

    def aws_ec2_instances(self, profile: Annotated[str, "The AWS profile"] = "default") -> str:
        """Get EC2 instances for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with EC2 instances description
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            response = ec2_client.describe_instances()
            self._save_response(
                response, "ec2_describe_instances", "AWSPlugin::aws_ec2_instances::"
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_ec2_instances")

    def aws_ec2_route_tables(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get Route Tables for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with route tables description
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            response = ec2_client.describe_route_tables()
            self._save_response(
                response,
                "ec2_describe_route_tables",
                "AWSPlugin::aws_ec2_route_tables::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_ec2_route_tables")

    def aws_elbv2_load_balancers(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get ELBV2 Load Balancers for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with load balancers description
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_load_balancers()
            self._save_response(
                response,
                "elbv2_describe_load_balancers",
                "AWSPlugin::aws_elbv2_load_balancers::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_load_balancers")

    def aws_elbv2_load_balancer_attributes(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get attributes for the specified ELBV2 Load Balancer.

        Args:
            arn: Load Balancer ARN
            profile: AWS profile name

        Returns:
            JSON string with load balancer attributes
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_load_balancer_attributes(
                LoadBalancerArn=arn
            )
            self._save_response(
                response,
                "elbv2_describe_load_balancer_attributes",
                "AWSPlugin::aws_elbv2_load_balancer_attributes::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_load_balancer_attributes")

    def aws_elbv2_security_groups(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get security groups for the specified ELBV2 Load Balancer.

        Args:
            arn: Load Balancer ARN
            profile: AWS profile name

        Returns:
            JSON string with security group IDs
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_load_balancers(LoadBalancerArns=[arn])
            security_groups = []
            if response.get("LoadBalancers"):
                security_groups = response["LoadBalancers"][0].get("SecurityGroups", [])

            self._save_response(
                security_groups,
                "elbv2_security_groups",
                "AWSPlugin::aws_elbv2_security_groups::",
            )
            return json.dumps(security_groups)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_security_groups")

    def aws_elbv2_listeners(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get Listeners for the specified ELBV2 Load Balancer.

        Args:
            arn: Load Balancer ARN
            profile: AWS profile name

        Returns:
            JSON string with listeners description
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_listeners(LoadBalancerArn=arn)
            self._save_response(
                response,
                "elbv2_describe_listeners",
                "AWSPlugin::aws_elbv2_listeners::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_listeners")

    def aws_elbv2_listener_attributes(
        self,
        arn: Annotated[str, "The Listener ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get attributes for the specified ELBV2 Listener.

        Args:
            arn: Listener ARN
            profile: AWS profile name

        Returns:
            JSON string with listener attributes
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_listener_attributes(ListenerArn=arn)
            self._save_response(
                response,
                "elbv2_describe_listener_attributes",
                "AWSPlugin::aws_elbv2_listener_attributes::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_listener_attributes")

    def aws_elbv2_target_groups(
        self,
        arn: Annotated[str, "The Load Balancer ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get Target Groups for the specified ELBV2 Load Balancer.

        Args:
            arn: Load Balancer ARN
            profile: AWS profile name

        Returns:
            JSON string with target groups description
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_target_groups(LoadBalancerArn=arn)
            self._save_response(
                response,
                "elbv2_describe_target_groups",
                "AWSPlugin::aws_elbv2_target_groups::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_target_groups")

    def aws_elbv2_target_group_attributes(
        self,
        arn: Annotated[str, "The Target Group ARN"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Get attributes for the specified ELBV2 Target Group.

        Args:
            arn: Target Group ARN
            profile: AWS profile name

        Returns:
            JSON string with target group attributes
        """
        try:
            session = self._get_session(profile)
            elbv2_client = session.client("elbv2")

            response = elbv2_client.describe_target_group_attributes(
                TargetGroupArn=arn
            )
            self._save_response(
                response,
                "elbv2_describe_target_group_attributes",
                "AWSPlugin::aws_elbv2_target_group_attributes::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_target_group_attributes")

    def aws_ec2_vpcs(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get VPCs for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with VPCs description
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            response = ec2_client.describe_vpcs()
            self._save_response(
                response, "ec2_describe_vpcs", "AWSPlugin::aws_ec2_vpcs::"
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_ec2_vpcs")

    def aws_ec2_vpc_endpoints(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get VPC endpoints for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with VPC endpoints description
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            response = ec2_client.describe_vpc_endpoints()
            self._save_response(
                response,
                "ec2_describe_vpc_endpoints",
                "AWSPlugin::aws_ec2_vpc_endpoints::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_ec2_vpc_endpoints")

    def aws_sts_caller_identity(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get the caller identity for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with caller identity information
        """
        try:
            session = self._get_session(profile)
            sts_client = session.client("sts")

            response = sts_client.get_caller_identity()
            self._save_response(
                response,
                "sts_get_caller_identity",
                "AWSPlugin::aws_sts_caller_identity::",
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_sts_caller_identity")

    def aws_s3_buckets(
        self, profile: Annotated[str, "The AWS profile"] = "default"
    ) -> str:
        """Get S3 Buckets for the given profile.

        Args:
            profile: AWS profile name

        Returns:
            JSON string with S3 buckets list
        """
        try:
            session = self._get_session(profile)
            s3_client = session.client("s3")

            response = s3_client.list_buckets()
            self._save_response(
                response, "s3_list_buckets", "AWSPlugin::aws_s3_buckets::"
            )
            return json.dumps(response, default=str)
        except Exception as e:
            return self._handle_aws_error(e, "aws_s3_buckets")

    def aws_elbv2_list_connection_logs(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        caller_identity: Annotated[str, "The STS caller identity account ID"],
        cutoff_date: Annotated[
            str, "The cutoff date in YYYY-MM-DDTHH:mm:ss format"
        ] = "",
        region: Annotated[str, "The AWS region"] = "eu-central-1",
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """List ELBV2 Connection Logs from S3 bucket.

        Args:
            bucket: S3 Bucket name
            caller_identity: STS caller identity account ID
            cutoff_date: Cutoff date in YYYY-MM-DDTHH:mm:ss format
            region: AWS region
            profile: AWS profile name

        Returns:
            JSON string with list of S3 object keys
        """
        try:
            log_debug(
                f"AWSPlugin::aws_elbv2_list_connection_logs:: Starting with bucket: {bucket}, "
                f"cutoff_date: {cutoff_date}, profile: {profile}"
            )

            # Set default cutoff_date to now - 1 day if not provided
            if not cutoff_date or cutoff_date.strip() == "":
                log_debug(
                    "AWSPlugin::aws_elbv2_list_connection_logs:: No cutoff_date provided, "
                    "defaulting to 24 hours ago"
                )
                cutoff_dt = datetime.utcnow() - timedelta(days=1)
                cutoff_date = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Calculate path prefix from cutoff date
            date_parts = cutoff_date.split("T")
            if len(date_parts) != 2:
                return json.dumps(
                    {"error": "cutoff_date must be in YYYY-MM-DDTHH:mm:ss format"}
                )

            date_segment = date_parts[0].replace("-", "/")
            log_debug(
                f"AWSPlugin::aws_elbv2_list_connection_logs:: Using cutoff_date: {cutoff_date}"
            )
            log_debug(
                f"AWSPlugin::aws_elbv2_list_connection_logs:: Using date_segment: {date_segment}"
            )

            prefix = f"AWSLogs/{caller_identity}/elasticloadbalancing/{region}/{date_segment}/"

            session = self._get_session(profile)
            s3_client = session.client("s3")

            # List objects with prefix
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

            # Filter by LastModified >= cutoff_date
            cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%dT%H:%M:%S")
            cutoff_dt = cutoff_dt.replace(tzinfo=None)  # Make naive for comparison

            keys = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    last_modified = obj["LastModified"].replace(tzinfo=None)
                    if last_modified >= cutoff_dt:
                        keys.append(obj["Key"])

            if not keys:
                log_debug(
                    "AWSPlugin::aws_elbv2_list_connection_logs:: No log files found."
                )
                return json.dumps({"keys": [], "message": "No log files found."})

            self._save_response(
                keys, "s3_list_connection_logs", "AWSPlugin::aws_elbv2_list_connection_logs::"
            )
            return json.dumps({"keys": keys, "count": len(keys)})

        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_list_connection_logs")

    def aws_elbv2_get_connection_logs(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        caller_identity: Annotated[str, "The STS caller identity account ID"],
        cutoff_date: Annotated[
            str, "The cutoff date in YYYY-MM-DDTHH:mm:ss format"
        ] = "",
        region: Annotated[str, "The AWS region"] = "eu-central-1",
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Download ELBV2 Connection Logs from S3 bucket.

        Args:
            bucket: S3 Bucket name
            caller_identity: STS caller identity account ID
            cutoff_date: Cutoff date in YYYY-MM-DDTHH:mm:ss format
            region: AWS region
            profile: AWS profile name

        Returns:
            JSON string with list of downloaded file paths
        """
        try:
            # First, list the objects
            list_result = self.aws_elbv2_list_connection_logs(
                bucket, caller_identity, cutoff_date, region, profile
            )
            list_data = json.loads(list_result)

            if "error" in list_data:
                return list_result

            keys = list_data.get("keys", [])
            if not keys:
                return json.dumps({"downloaded": [], "message": "No log files found."})

            # Download each log file
            session = self._get_session(profile)
            s3_client = session.client("s3")

            dest_dir = self.session.data_dir / "aws_s3_downloads"
            dest_dir.mkdir(parents=True, exist_ok=True)

            downloaded = []
            for key in keys:
                basename_key = key.split("/")[-1]
                destination = dest_dir / basename_key

                log_debug(
                    f"AWSPlugin::aws_elbv2_get_connection_logs:: Downloading "
                    f"s3://{bucket}/{key} to {destination}"
                )

                s3_client.download_file(bucket, key, str(destination))
                downloaded.append(str(destination))

            if self.session:
                self._save_response(
                    downloaded,
                    "s3_downloaded_files",
                    "AWSPlugin::aws_elbv2_get_connection_logs::",
                )

            if self.scratchpad:
                self.scratchpad.write_journal_entry(
                    self.name,
                    f"Downloaded {len(downloaded)} connection log files from bucket {bucket} "
                    f"for profile {profile}.",
                    str(downloaded),
                )

            return json.dumps({"downloaded": downloaded, "count": len(downloaded)})

        except Exception as e:
            return self._handle_aws_error(e, "aws_elbv2_get_connection_logs")

    def aws_s3_cp(
        self,
        bucket: Annotated[str, "The S3 Bucket name"],
        key: Annotated[str, "The S3 Object key"],
        profile: Annotated[str, "The AWS profile"] = "default",
    ) -> str:
        """Download a S3 Object to a local directory.

        Args:
            bucket: S3 Bucket name
            key: S3 Object key
            profile: AWS profile name

        Returns:
            Local file path where the object was downloaded
        """
        try:
            session = self._get_session(profile)
            s3_client = session.client("s3")

            dest_dir = self.session.data_dir / "aws_s3_downloads"
            dest_dir.mkdir(parents=True, exist_ok=True)

            basename_key = key.split("/")[-1]
            destination = dest_dir / basename_key

            log_debug(
                f"AWSPlugin::aws_s3_cp:: Downloading s3://{bucket}/{key} to {destination}"
            )

            s3_client.download_file(bucket, key, str(destination))

            if self.session:
                self.session.save_data(
                    SessionDataType.INFO,
                    "s3_cp",
                    f"Saved s3://{bucket}/{key} to {destination}",
                )

            if self.scratchpad:
                self.scratchpad.write_journal_entry(
                    self.name,
                    f"Copied S3 object s3://{bucket}/{key}",
                    f"Copied S3 object s3://{bucket}/{key} to {destination}.",
                )

            return str(destination)

        except Exception as e:
            return self._handle_aws_error(e, "aws_s3_cp")

    def aws_ec2_describe_eni_security_groups(
        self,
        profile: Annotated[str, "The AWS profile"] = "default",
        private_ip: Annotated[str, "The private IP address of the ENI"] = "",
    ) -> str:
        """Get security groups for a network interface by private IP.

        Args:
            profile: AWS profile name
            private_ip: Private IP address of the ENI

        Returns:
            JSON string with security group IDs and names
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            filters = []
            if private_ip and private_ip.strip():
                filters.append(
                    {"Name": "private-ip-address", "Values": [private_ip.strip()]}
                )

            response = ec2_client.describe_network_interfaces(Filters=filters)

            security_groups = []
            if response.get("NetworkInterfaces"):
                groups = response["NetworkInterfaces"][0].get("Groups", [])
                security_groups = [[g["GroupId"], g["GroupName"]] for g in groups]

            self._save_response(
                security_groups,
                "ec2_describe_eni_security_groups",
                "AWSPlugin::aws_ec2_describe_eni_security_groups::",
            )
            return json.dumps(security_groups)

        except Exception as e:
            return self._handle_aws_error(e, "aws_ec2_describe_eni_security_groups")

    def aws_ec2_describe_security_group_inbound_rules(
        self,
        profile: Annotated[str, "The AWS profile"] = "default",
        group_id: Annotated[str, "The security group ID"] = "",
    ) -> str:
        """Get inbound rules for a security group.

        Args:
            profile: AWS profile name
            group_id: Security group ID

        Returns:
            JSON string with inbound rules
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            group_ids = [group_id.strip()] if group_id and group_id.strip() else []
            response = ec2_client.describe_security_groups(GroupIds=group_ids)

            inbound_rules = []
            if response.get("SecurityGroups"):
                permissions = response["SecurityGroups"][0].get("IpPermissions", [])
                for perm in permissions:
                    rule = [
                        perm.get("IpProtocol"),
                        perm.get("FromPort"),
                        perm.get("ToPort"),
                        [ip_range.get("CidrIp") for ip_range in perm.get("IpRanges", [])],
                        [pair.get("GroupId") for pair in perm.get("UserIdGroupPairs", [])],
                    ]
                    inbound_rules.append(rule)

            self._save_response(
                inbound_rules,
                "ec2_describe_security_group_inbound_rules",
                "AWSPlugin::aws_ec2_describe_security_group_inbound_rules::",
            )
            return json.dumps(inbound_rules)

        except Exception as e:
            return self._handle_aws_error(
                e, "aws_ec2_describe_security_group_inbound_rules"
            )

    def aws_ec2_describe_security_group_outbound_rules(
        self,
        profile: Annotated[str, "The AWS profile"] = "default",
        group_id: Annotated[str, "The security group ID"] = "",
    ) -> str:
        """Get outbound rules for a security group.

        Args:
            profile: AWS profile name
            group_id: Security group ID

        Returns:
            JSON string with outbound rules
        """
        try:
            session = self._get_session(profile)
            ec2_client = session.client("ec2")

            group_ids = [group_id.strip()] if group_id and group_id.strip() else []
            response = ec2_client.describe_security_groups(GroupIds=group_ids)

            outbound_rules = []
            if response.get("SecurityGroups"):
                permissions = response["SecurityGroups"][0].get(
                    "IpPermissionsEgress", []
                )
                for perm in permissions:
                    rule = [
                        perm.get("IpProtocol"),
                        perm.get("FromPort"),
                        perm.get("ToPort"),
                        [ip_range.get("CidrIp") for ip_range in perm.get("IpRanges", [])],
                        [pair.get("GroupId") for pair in perm.get("UserIdGroupPairs", [])],
                    ]
                    outbound_rules.append(rule)

            self._save_response(
                outbound_rules,
                "ec2_describe_security_group_outbound_rules",
                "AWSPlugin::aws_ec2_describe_security_group_outbound_rules::",
            )
            return json.dumps(outbound_rules)

        except Exception as e:
            return self._handle_aws_error(
                e, "aws_ec2_describe_security_group_outbound_rules"
            )

    def get_tools(self) -> List[ToolProtocol]:
        """Returns the list of tools provided by the AWSPlugin."""
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
