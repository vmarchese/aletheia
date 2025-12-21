You have access to the AWS cli to fetch resources on AWS:

#### General
- **aws_profiles()**: gets the configured profiles
- **aws_sts_caller_identity(profile)**: gets the caller identity for a profile

#### EC2
- **aws_ec2_instances(profile)**: gets the EC2 instances for the given profiles
- **aws_ec2_route_tables(profile)**: gets the EC2 route tables
- **aws_ec2_vpcs(profile)**: gets the VPCs for a profile
- **aws_ec2_vpc_endpoints(profile)**: gets the VPC endpoints for a profile
- **aws_ec2_describe_eni_security_groups(profile,private_ip)**: gets the security group for the given private ip address and profile if present
- **aws_ec2_describe_security_group_inbound_rules(profile,group_id)**: describe the security group inbound rules for a security group and a profile
- **aws_ec2_describe_security_group_outbound_rules(profile,group_id)**: describe the security group outbound rules for a security group and a profile

#### S3
- **aws_s3_buckets(profile)**: lists the S3 buckets for a profile
- **aws_s3_cp( bucket, key, profile)**: retrieves an object named key, file or connection log from a bucket S3 for a profile

#### Elastic load balancer
- **aws_elbv2_load_balancers(profile)**: gets the ELBV2 (Elastic Load Balancer V2) load balancers
- **aws_elbv2_load_balancer_attributes(arn,profile)**: gets the ELBV2 (Elastic Load Balancer V2) attributes 
- **aws_elbv2_listeners(arn,profile)**: gets the listeners for an ELBV2 (Elastic Load Balancer V2) ARN
- **aws_elbv2_listener_attributes(arn,profile)**: gets the listener attributres for an ELBV2 (Elastic Load Balancer V2) Listener ARN
- **aws_elbv2_target_groups(arn,profile)**: gets the target groups for an ELBV2 (Elastic Load Balancer V2) ARN
- **aws_elbv2_target_group_attributes(arn,profile)**: gets the target group attributes for an ELBV2 (Elastic Load Balancer V2) target group ARN
- **aws_elbv2_get_connection_logs(bucket, caller_identity, cutoff_date, region, profile)**: Gets the connection logs files in a bucket more recent than a cutoff date for a profile and saves them locally.  The default cutoff date is None.  
- **aws_elbv2_list_connection_logs(bucket, caller_identity, cutoff_date, region, profile)**: Lists the connection logs files in a bucket more recent than a cutoff date for a profile and saves them locally.  The default cutoff date is None.  
- **aws_elbv2_security_groups(arn,profile)**: gets the ELBV2 (Elastic Load Balancer V2) security groups 