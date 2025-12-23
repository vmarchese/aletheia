---
name: Check EC2 Route Tables
description: Gets the route tables for EC2 instances in AWS.
---
Use this skill to retrieve the route tables associated with EC2 instances in AWS.
1. Use `aws_profiles()` to find the list of profiles
2. If the user has specified a profile check against the results returned
3. If the user has not specified a profile, ask him which one to use
4. If the profile is there call `aws_ec2_route_tables(profile)`
5. return the ALWAYS THE FULL results in a table