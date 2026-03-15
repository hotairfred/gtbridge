"""
udp_relay.py — Duplicate UDP traffic to multiple destinations.

Listens on a port and forwards all packets to multiple targets.
Used to split CWSL_DIGI's WSJT-X UDP output to both the RBN Aggregator
and GTBridge simultaneously, preserving the exact frequency data.

Usage: python udp_relay.py [--config udp_relay.json]

Default: listens on 2215, forwards to Aggregator (127.0.0.1:2216)
         and GTBridge (192.168.1.101:2215)
"""

import json
import socket
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "listen_port": 2215,
    "targets": [
        {"host": "127.0.0.1", "port": 2216, "name": "Aggregator"},
        {"host": "192.168.1.101", "port": 2215, "name": "GTBridge"}
    ]
}


def main():
    config_path = 'udp_relay.json'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
    else:
        config = DEFAULT_CONFIG
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Created default config: {config_path}")
        print("Edit targets and restart.")
        return

    listen_port = config['listen_port']
    targets = [(t['host'], t['port']) for t in config['targets']]
    target_names = [t.get('name', f"{t['host']}:{t['port']}") for t in config['targets']]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', listen_port))

    print(f"UDP relay listening on port {listen_port}")
    for name, (host, port) in zip(target_names, targets):
        print(f"  -> {name} ({host}:{port})")

    count = 0
    while True:
        data, addr = sock.recvfrom(65536)
        for target in targets:
            try:
                sock.sendto(data, target)
            except Exception as e:
                pass
        count += 1
        if count % 1000 == 0:
            print(f"Relayed {count} packets")


if __name__ == '__main__':
    main()
