#!/usr/bin/env python3
"""Local root helper with a fixed host administration surface."""
from collections import deque
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import platform
import shutil
import shlex
import re
import socketserver
import subprocess
import threading
import time
import uuid

ROOT = Path('/etc/mole-cabinet')
SOCKET = Path('/run/mole-host-agent/control.sock')
JOBS = {}
LOCK = threading.Lock()
SERVICES = ('mole-cabinet', 'docker', 'ssh', 'avahi-daemon', 'mole-host-agent', 'NetworkManager', 'unattended-upgrades', 'mole-cabinet-install-update')


def command(args, timeout=10, limit=65536):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": None, "stdout": "", "stderr": str(error), "error": str(error)}
    return {'exit_code': result.returncode, 'stdout': result.stdout[-limit:], 'stderr': result.stderr[-8192:],
            'stdout_truncated': len(result.stdout) > limit, 'stderr_truncated': len(result.stderr) > 8192}


def json_command(args):
    result = command(args)
    try:
        return json.loads(result['stdout'])
    except ValueError:
        return result


def text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def information():
    disks = []
    for row in (text('/proc/mounts') or '').splitlines():
        fields = row.split()
        if len(fields) < 3 or not fields[0].startswith('/dev/'):
            continue
        try:
            use = shutil.disk_usage(fields[1])
            disks.append({'device': fields[0], 'mount': fields[1], 'filesystem': fields[2],
                          'total_bytes': use.total, 'free_bytes': use.free})
        except OSError:
            pass
    temperatures = [{'name': text(path.parent / 'type'), 'millidegrees_c': text(path)}
                    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp')]
    return {'observed_at': datetime.now(timezone.utc).isoformat(),
            'agent': {'version': '3.0.1', 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'installation': json.loads(text(ROOT / 'install-info.json') or '{}')},
            'reboot_required': Path('/var/run/reboot-required').exists(),
            'upgradable_packages_from_local_cache': command(['apt', 'list', '--upgradable'], timeout=10),
            'hostname': platform.node(), 'os': platform.freedesktop_os_release(),
            'kernel': platform.release(), 'architecture': platform.machine(),
            'machine_id': text('/etc/machine-id'), 'boot_id': text('/proc/sys/kernel/random/boot_id'),
            'uptime': text('/proc/uptime'), 'load_average': os.getloadavg(),
            'memory': text('/proc/meminfo'), 'cpu_counters': text('/proc/stat'),
            'network_counters': text('/proc/net/dev'), 'audio_cards': text('/proc/asound/cards'),
            'pressure': {name: text('/proc/pressure/' + name) for name in ('cpu', 'memory', 'io')},
            'cpu': json_command(['lscpu', '-J']),
            'storage': disks, 'block_devices': json_command(['lsblk', '-J', '-o', 'NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL']),
            'network': json_command(['ip', '-j', 'address']), 'routes': json_command(['ip', '-j', 'route']),
            'usb': command(['lsusb']), 'pci': command(['lspci']), 'temperatures': temperatures,
            'disk_counters': text('/proc/diskstats'),
            'hardware_monitors': [{'device': text(sensor.parent / 'name'), 'sensor': sensor.name, 'value': text(sensor)}
                                   for sensor in Path('/sys/class/hwmon').glob('hwmon*/*_input')],
            'processes': command(['ps', '-eo', 'pid,ppid,comm,%cpu,%mem,etime']),
            'services': {service: command(['systemctl', 'show', service, '--property=ActiveState,SubState,Result,NRestarts'], timeout=2)
                         for service in SERVICES},
            'containers': command(['docker', 'ps', '-a', '--format', '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}']),
            'images': command(['docker', 'images', '--digests', '--format', '{{json .}}']),
            'docker_version': json_command(['docker', 'version', '--format', '{{json .}}']),
            'game_container': json_command(['docker', 'inspect', '--format',
                     '{"name":{{json .Name}},"image":{{json .Image}},"state":{{json .State}},"restart_count":{{json .RestartCount}}}', 'mole-game'])}



HOST_SETTINGS = ('IMAGE', 'SERIAL_DEVICE', 'STATUS_BIND', 'STATUS_PORT')

def configuration():
    result = {}
    for row in (text(ROOT / 'cabinet.conf') or '').splitlines():
        if '=' not in row or row.lstrip().startswith('#'):
            continue
        name, value = row.split('=', 1)
        if name.strip() in HOST_SETTINGS:
            fields = shlex.split(value)
            result[name.strip()] = fields[0] if fields else ''
    return result


def configure(settings):
    if not isinstance(settings, dict) or not settings or not set(settings) <= set(HOST_SETTINGS):
        raise ValueError('Unsupported host settings')
    for name, value in settings.items():
        if name == 'IMAGE' and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9./:_@-]{0,255}', value)):
            raise ValueError('Invalid image reference')
        if name == 'SERIAL_DEVICE' and (not isinstance(value, str) or value and not re.fullmatch(r'/dev/(tty(?:ACM|USB)[0-9]+|serial/by-id/[A-Za-z0-9_.:+-]+)', value)):
            raise ValueError('Invalid serial device path')
        if name == 'STATUS_PORT' and (type(value) is not int or not 1 <= value <= 65535):
            raise ValueError('Invalid status port')
        if name == 'STATUS_BIND':
            if not isinstance(value, str):
                raise ValueError('Invalid status bind address')
            import ipaddress
            ipaddress.ip_address(value)
    path = ROOT / 'cabinet.conf'
    rows = path.read_text().splitlines()
    seen = set()
    for index, row in enumerate(rows):
        name = row.split('=', 1)[0].strip()
        if name in settings:
            rows[index] = f'{name}={shlex.quote(str(settings[name]))}'
            seen.add(name)
    rows.extend(f'{name}={shlex.quote(str(value))}' for name, value in settings.items() if name not in seen)
    path.with_suffix('.conf.api-backup').write_text(path.read_text())
    os.chmod(path.with_suffix('.conf.api-backup'), 0o600)
    temporary = path.with_suffix('.tmp')
    temporary.write_text('\n'.join(rows) + '\n')
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return {'exit_code': 0, 'configuration': configuration(), 'apply': 'POST host restart_game'}

def execute(action, payload):
    if action == 'update_installation':
        if not (ROOT / 'install-info.json').is_file():
            raise ValueError('Installer repository metadata is unavailable')
        unit = 'mole-cabinet-install-update-' + uuid.uuid4().hex[:12]
        result = command(['systemd-run', '--unit=' + unit, '--property=Type=oneshot', '--property=RemainAfterExit=yes',
                          '/usr/bin/python3', '/usr/local/lib/mole-cabinet/update-installation'])
        result['service_job'] = unit
        return result
    if action == 'os_update':
        if payload.get('confirm') != 'UPDATE OS':
            raise ValueError('confirm must be UPDATE OS')
        result = command(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'update'], timeout=300)
        if result['exit_code'] == 0:
            return command(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get',
                            '-o', 'Dpkg::Options::=--force-confold', 'upgrade', '-y'], timeout=1800)
        return result
    if action in ('reboot', 'poweroff'):
        # Give the HTTP caller time to receive its operation ID.
        time.sleep(2)
        return command(['systemctl', action])
    if action in ('update', 'restart_game'):
        return command(['systemctl', 'restart', 'mole-cabinet'], timeout=650)
    if action == 'configuration':
        return configure(payload.get('settings'))
    if action == 'hostname':
        hostname = payload.get('hostname', '')
        if (not isinstance(hostname, str) or not 1 <= len(hostname) <= 63
                or not hostname[0].isalnum() or not hostname[-1].isalnum()
                or any(not (c.isascii() and (c.isalnum() or c == '-')) for c in hostname)):
            raise ValueError('Invalid hostname')
        old = platform.node()
        result = command(['hostnamectl', 'set-hostname', hostname])
        if result['exit_code'] == 0:
            hosts = Path('/etc/hosts')
            lines = []
            for row in hosts.read_text().splitlines():
                fields = row.split()
                if fields and fields[0] == '127.0.1.1':
                    row = '127.0.1.1\t' + ' '.join(hostname if value == old else value for value in fields[1:])
                lines.append(row)
            hosts.write_text('\n'.join(lines) + '\n')
            command(['systemctl', 'restart', 'avahi-daemon'])
        return result
    raise ValueError('Unsupported host action')




def log_arguments(query):
    values = parse_qs(query)
    if not set(values) <= {'limit', 'since', 'until'} or any(len(value) != 1 for value in values.values()):
        raise ValueError('Unsupported log query')
    limit = int(values.get('limit', ['200'])[0])
    if not 1 <= limit <= 2000:
        raise ValueError('Log limit must be 1..2000')
    journal = ['-n', str(limit), '--no-pager', '-o', 'short-iso']
    docker = ['--tail', str(limit)]
    for name in ('since', 'until'):
        if name in values:
            value = datetime.fromisoformat(values[name][0].replace('Z', '+00:00'))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(timezone.utc)
            journal.extend(['--' + name, value.strftime('%Y-%m-%d %H:%M:%S UTC')])
            docker.extend(['--' + name, value.isoformat()])
    return journal, docker

def save_jobs():
    path = ROOT / 'host-jobs.json'
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as file:
        json.dump(JOBS, file)
        file.flush()
        os.fsync(file.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)

def job_worker(identity, action, payload):
    with LOCK:
        JOBS[identity]['status'] = 'RUNNING'
    try:
        with LOCK:
            save_jobs()
        result = execute(action, payload)
        status = ('RUNNING' if result.get('service_job') else 'DONE') if result['exit_code'] == 0 else 'ERROR'
    except Exception as error:
        result, status = {'error': str(error)}, 'ERROR'
    with LOCK:
        JOBS[identity].update(status=status, result=result, finished_at=time.time())
        try:
            save_jobs()
        except OSError as error:
            JOBS[identity]['storage_error'] = str(error)


def refresh_jobs():
    with LOCK:
        tracked = [(identity, job['result']['service_job']) for identity, job in JOBS.items()
                   if job.get('result', {}).get('service_job') and job['status'] == 'RUNNING']
    for identity, unit in tracked:
        result = command(['systemctl', 'show', unit, '--property=LoadState,ActiveState,SubState,Result,ExecMainStatus'], timeout=2)
        fields = dict(row.split('=', 1) for row in result['stdout'].splitlines() if '=' in row)
        state = 'RUNNING'
        if fields.get('LoadState') == 'not-found':
            state = 'INTERRUPTED'
        elif fields.get('ActiveState') == 'failed' or fields.get('Result', 'success') != 'success':
            state = 'ERROR'
        elif fields.get('SubState') == 'exited':
            state = 'DONE'
        with LOCK:
            JOBS[identity]['execution_service'] = fields or result
            JOBS[identity]['status'] = state
            if state != 'RUNNING':
                JOBS[identity]['finished_at'] = time.time()
            save_jobs()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            if path == '/host':
                self.respond(200, information())
            elif path == '/configuration':
                self.respond(200, configuration())
            elif path == '/packages':
                self.respond(200, command(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'], limit=2000000))
            elif path == '/logs':
                journal, docker = log_arguments(urlsplit(self.path).query)
                self.respond(200, {'system': command(['journalctl', *journal], limit=2000000),
                                   'journal': command(['journalctl', '-u', 'mole-cabinet', '-u', 'mole-host-agent', *journal], limit=2000000),
                                   'container': command(['docker', 'logs', *docker, 'mole-game'], limit=2000000),
                                   'kernel': command(['journalctl', '-k', *journal], limit=2000000),
                                   'installation': {job['result']['service_job']: command(['journalctl', '-u', job['result']['service_job'], *journal], limit=2000000)
                                       for job in list(JOBS.values())[-5:] if job.get('result', {}).get('service_job')}})
            elif path == '/jobs':
                refresh_jobs()
                with LOCK:
                    self.respond(200, list(JOBS.values()))
            else:
                self.respond(404, {'error': 'Not found'})
        except Exception as error:
            self.respond(503, {'error': str(error)})

    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 4096:
                raise ValueError('Invalid request size')
            self.connection.settimeout(5)
            payload = json.loads(self.rfile.read(size))
            action = payload.get('action')
            if self.path != '/actions' or action not in ('update', 'restart_game', 'reboot', 'poweroff', 'hostname', 'configuration', 'os_update', 'update_installation'):
                raise ValueError('Unsupported host action')
            refresh_jobs()
            with LOCK:
                if any(job['status'] in ('QUEUED', 'RUNNING') for job in JOBS.values()):
                    self.respond(409, {'error': 'Host action already running'})
                    return
                identity = uuid.uuid4().hex
                JOBS[identity] = {'id': identity, 'action': action, 'status': 'QUEUED', 'created_at': time.time()}
                for old in list(JOBS)[:-100]:
                    del JOBS[old]
                try:
                    save_jobs()
                except OSError:
                    del JOBS[identity]
                    raise
                result = dict(JOBS[identity])
            self.respond(202, result)
            threading.Thread(target=job_worker, args=(identity, action, payload), daemon=True).start()
        except (ValueError, AttributeError, OSError) as error:
            self.respond(400, {'error': str(error)})


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    try:
        if (ROOT / 'host-jobs.json').exists():
            JOBS.update(json.loads((ROOT / 'host-jobs.json').read_text()))
            for job in JOBS.values():
                if job['status'] in ('QUEUED', 'RUNNING') and not job.get('result', {}).get('service_job'):
                    job.update(status='INTERRUPTED', finished_at=time.time())
            save_jobs()
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f'HOST JOB HISTORY ERROR: {error}', flush=True)
        JOBS.clear()
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    SOCKET.unlink(missing_ok=True)
    with Server(str(SOCKET), Handler) as server:
        os.chmod(SOCKET, 0o600)
        server.serve_forever()


if __name__ == '__main__':
    main()
