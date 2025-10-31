"""Semantic Kernel plugin for Kubernetes operations.

This plugin exposes Kubernetes operations as kernel functions that can be
automatically invoked by SK agents using FunctionChoiceBehavior.Auto().

The plugin provides simplified async functions for:
- Fetching logs from pods
- Listing pods in namespaces
- Getting pod status information
"""

from typing import Annotated

from semantic_kernel.functions import kernel_function

from aletheia.utils.logging import log_debug, log_error
from aletheia.config import Config
from aletheia.session import Session, SessionDataType
from aletheia.plugins.loader import PluginInfoLoader


class PCAPFilePlugin:
    """Semantic Kernel plugin for PCAP file operations."""

    def __init__(self, config: Config, session: Session):
        """Initialize the PCAPFilePlugin.

        Args:
            config: Configuration object for the plugin
            session: Session object for managing state
        """
        self.name = "PCAPFilePlugin"
        self.session = session
        self.config = config
        loader = PluginInfoLoader()
        self.instructions = loader.load("pcap_file_plugin")

    @kernel_function(description="Read a pcap file and return packet details as CSV (verbose mode).")
    async def read_pcap_from_file(
        self,
        file_path: Annotated[str, "Path to the pcap file"]
    ) -> str:
        """Read a pcap file and return packet details as CSV (verbose mode)."""
        try:
            log_debug(f"PCAPFilePlugin::read_pcap_from_file:: Reading PCAP file: {file_path}")
            from scapy.all import rdpcap, IP, TCP, UDP, ICMP, Ether
            import datetime
            import os
            if not os.path.exists(file_path):
                return f"Error: File '{file_path}' does not exist."
            packets = rdpcap(file_path)
            if not packets:
                return "No packets found in the PCAP file."

            # Prepare CSV header
            csv_lines = [
                '"packet_num","timestamp","src_ip","protocol","dst_ip","length","info","src_port","dst_port","flags"'
            ]

            def packet_to_csv(packet, packet_num):
                timestamp = getattr(packet, 'time', None)
                if timestamp:
                    try:
                        ts_float = float(timestamp)
                        ts_str = datetime.datetime.fromtimestamp(ts_float).strftime('%Y-%m-%d %H:%M:%S.%f')
                    except Exception:
                        ts_str = str(timestamp)
                else:
                    ts_str = ''
                length = str(len(packet))
                src_ip = dst_ip = src_port = dst_port = protocol = flags = info = ''

                if packet.haslayer(IP):
                    ip = packet[IP]
                    src_ip = ip.src
                    dst_ip = ip.dst
                    protocol_num = ip.proto
                    protocol = {6: 'TCP', 17: 'UDP', 1: 'ICMP'}.get(protocol_num, str(protocol_num))

                    if packet.haslayer(TCP):
                        tcp = packet[TCP]
                        src_port = str(tcp.sport)
                        dst_port = str(tcp.dport)
                        flags = tcp.sprintf('%TCP.flags%')
                        info = f"{src_port} → {dst_port} [{flags}] Seq={tcp.seq} Ack={tcp.ack} Win={tcp.window} Len={len(tcp.payload)}"
                        if hasattr(tcp, 'options') and tcp.options:
                            opts = []
                            for opt in tcp.options:
                                if isinstance(opt, tuple):
                                    if opt[0] == 'MSS':
                                        opts.append(f"MSS={opt[1]}")
                                    elif opt[0] == 'SAckOK':
                                        opts.append("SACK_PERM")
                                    elif opt[0] == 'Timestamp':
                                        opts.append(f"TSval={opt[1][0]} TSecr={opt[1][1]}")
                                    elif opt[0] == 'WScale':
                                        opts.append(f"WS={opt[1]}")
                            if opts:
                                info += ' ' + ' '.join(opts)
                    elif packet.haslayer(UDP):
                        udp = packet[UDP]
                        src_port = str(udp.sport)
                        dst_port = str(udp.dport)
                        info = f"{src_port} → {dst_port} Len={udp.len}"
                    elif packet.haslayer(ICMP):
                        icmp = packet[ICMP]
                        protocol = 'ICMP'
                        info = f"type={icmp.type} code={icmp.code}"
                elif packet.haslayer(Ether):
                    eth = packet[Ether]
                    src_ip = eth.src
                    dst_ip = eth.dst
                    protocol = 'Ethernet'
                    info = f"type={eth.type}"

                return f'"{packet_num}","{ts_str}","{src_ip}","{protocol}","{dst_ip}","{length}","{info}","{src_port}","{dst_port}","{flags}"'

            log_debug(f"PCAPFilePlugin::read_pcap_from_file:: returning {len(packets)} packets.")
            for i, packet in enumerate(packets, 1):
                csv_lines.append(packet_to_csv(packet, i))

            # save log lines to session folder
            saved = ""
            filename = os.path.basename(file_path)
            if self.session:
                saved = self.session.save_data(SessionDataType.TCPDUMP, f"{filename}_tcpdump", "\n".join(csv_lines))
                log_debug(f"PCAPFilePlugin::read_pcap_from_file:: Saved dump to {saved}")

            return '\n'.join(csv_lines)
        except Exception as e:
            log_error(f"Error reading pcap file {file_path}: {e}")
            return f"Error reading pcap file: {e}"