#!/usr/bin/env python3
"""Snapshot host facts at cabinet launch without exposing the Docker socket."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def output(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


network = output(['ip', '-j', 'address', 'show'])
interfaces = json.loads(network) if network else []
report = {
    'collected_at': datetime.now(timezone.utc).isoformat(),
    'hostname': platform.node(), 'machine_id': read('/etc/machine-id'),
    'boot_id': read('/proc/sys/kernel/random/boot_id'),
    'os': platform.freedesktop_os_release(), 'kernel': platform.release(),
    'architecture': platform.machine(), 'host_python': platform.python_version(),
    'docker_cli': output(['docker', '--version']),
    'docker_engine': output(['docker', 'version', '--format', '{{.Server.Version}}']),
    'packages': {name: output(['dpkg-query', '-W', '-f=${Version}', name])
                 for name in ('openssh-server', 'avahi-daemon', 'systemd', 'docker-ce')},
    'cpu_count': os.cpu_count(),
    'memory_at_launch': read('/proc/meminfo'),
    'uptime_at_launch': read('/proc/uptime'),
    'image_id': sys.argv[2], 'configured_image': sys.argv[3],
    'services_at_launch': {name: output(['systemctl', 'is-active', name])
                           for name in ('docker', 'ssh', 'avahi-daemon')},
    'network': [{'interface': item['ifname'], 'addresses': [address['local'] for address in item.get('addr_info', [])]}
                for item in interfaces if item['ifname'] != 'lo'
                and not item['ifname'].startswith(('docker', 'veth', 'br-'))],
}
path = Path(sys.argv[1])
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(report) + '\n')
os.chmod(temporary, 0o644)
os.replace(temporary, path)
