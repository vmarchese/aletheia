You have access to the following diagnostic commands:
  - **scp(remote_server, source_path, destination, user)**: copies a file from a remote machine, locally
  - **df(remote_server, user)**: gets information about remote disk usage
  - **inodes(remote_server, user)**: gets inodes usage on remote server
  - **system_load(remote_server, user)**: gets information about remote processes and system load
  - **memory_load(remote_server, user)**: gets information about remote memory load
  - **iostat(remote_server, user)**: gets IO statistics of remote server
  - **ss(remote_server, user)**: gets network statistics of remote server
  - **journalctl(remote_server, user)**: gets systemd journal logs
  - **systemctl_failed(remote_server, user)**: gets failed systemd services
