"""Record the exact application contents in a container build."""
from datetime import datetime, timezone
import json
import os
import subprocess
from app.diagnostics import APP_VERSION, app_source_hash
from pathlib import Path

Path('/app/app/build_info.json').write_text(json.dumps({
    'version': APP_VERSION, 'source_sha256': app_source_hash(),
    'packages': {name: subprocess.run(['dpkg-query', '-W', '-f=${Version}', name],
                                     capture_output=True, text=True, check=True).stdout
                 for name in ('avrdude', 'alsa-utils')},
    'revision': os.environ.get('APP_REVISION') or None,
    'built_at': datetime.now(timezone.utc).isoformat(), 'source': 'Docker image',
}) + '\n')
