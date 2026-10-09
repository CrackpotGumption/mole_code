#!/usr/bin/env python3
"""Run repository/host installer updates in a separate systemd job."""
import json
from pathlib import Path
import subprocess

info = json.loads(Path('/etc/mole-cabinet/install-info.json').read_text())
repository = Path(info['repository']).resolve()
if not (repository / '.git').exists() or not (repository / 'misc/linux_bash_daemon').is_file():
    raise RuntimeError('Recorded cabinet repository is unavailable')
subprocess.run(['runuser', '-u', info['administrator'], '--', 'git', '-C', str(repository), 'pull', '--ff-only'], check=True)
subprocess.run(['bash', str(repository / 'misc/linux_bash_daemon')], check=True)
