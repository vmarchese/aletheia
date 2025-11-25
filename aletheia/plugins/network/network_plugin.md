You have access to the network commands

- **is_ip_in_cidr(ip_address, cidr_block)**: returns if the ip address belongs to the CIDR block
- **dig(domain,type,dns_server)**: invokes dig to resolve the record type of the requested domain with a DNS server. Prefer this if available
- **ns_lookup(domain)**: invokes nslookup to resolve the ip of the requested domain. Use this when a DNS server is NOT requested
- **ping(target)**: performs a ping (ICMP) latency check on target
- **traceroute(target)**: performs a traceroute to the target
- **ifconfig()**: get local network interfaces
- **netstat()**: show active sockets/connections on the local machine
- **whois(domain)**: looks up records in the databases maintained by several Network Information Centers (NICs)
- **openssl_sclient(target)**: connects via openssl to a target to check whether the certificate is valid, trusted, and complete.