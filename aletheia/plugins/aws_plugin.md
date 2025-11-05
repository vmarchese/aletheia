You have access to the AWS cli to fetch resources on AWS:

- **aws_profiles()**: gets the configured profiles from the system
- **aws_ec2_instances(profile)**: gets the EC2 instances for the given profiles
- **aws_ec2_route_tables(profile)**: gets the EC2 route tables
- **aws_ec2_vpcs(profile)**: gets the VPCs for a profile
- **aws_ec2_vpc_endpoints(profile)**: gets the VPC endpoints for a profile
- **aws_elbv2_load_balancers(profile)**: gets the ELBV2 (Elastic Load Balancer V2) load balancers
- **aws_elbv2_load_balancer_attributes(profile)**: gets the ELBV2 (Elastic Load Balancer V2) attributes
- **aws_elbv2_listeners(arn,profile)**: gets the listeners for an ELBV2 (Elastic Load Balancer V2) ARN
- **aws_elbv2_listener_attributes(arn,profile)**: gets the listener attributres for an ELBV2 (Elastic Load Balancer V2) Listener ARN
- **aws_elbv2_target_groups(arn,profile)**: gets the target groups for an ELBV2 (Elastic Load Balancer V2) ARN
- **aws_elbv2_target_group_attributes(arn,profile)**: gets the target group attributes for an ELBV2 (Elastic Load Balancer V2) target group ARN
- **aws_sts_caller_identity(profile)**: gets the caller identity for a profile
- **aws_s3_buckets(profile)**: gets the S3 buckets for a profile
- **aws_s3_cp( bucket, key, profile)**: Gets an object named key or file from a bucket S3 for a profile
- **aws_elbv2_connection_logs(bucket, caller_identity, cutoff_date, region, profile)**: gets the list of connection logs files in a bucket more recent than a cutoff date for a profile. The default cutoff date is None 