"""Cabinet lifecycle and API operations; HTTP remains available during faults."""
from collections import deque
from contextlib import nullcontext
import json
import os
from pathlib import Path
import queue
import shutil
import threading
import time
import uuid

from app import host_bridge
from app.audio_cues import AudioCues
from app.control_state import read, write
from app.diagnostics import application_info, diagnostics, read_json
from app.firmware import connect_verified, history_path
from app.mole_game import MoleGame, GameState, PLAYER_IDS, PLAYER_INDEX, MOLE_ID_BY_NAME, RGB


class Cabinet:
    def __init__(self, controller_factory, port, stopped):
        self.factory, self.port, self.stopped = controller_factory, port, stopped
        self.arduino = self.game = self.audio = None
        self.phase = 'STARTING'
        self.maintenance = False
        self.fault = None
        self.started_at = time.monotonic()
        self.recent_errors = deque(maxlen=50)
        self.operations = {}
        self.lock = threading.RLock()
        self.actions = queue.Queue(maxsize=16)
        self.worker = None
        self.last_keepalive = self.last_probe = 0
        self.last_attempt = 0
        self.health_failures = 0
        self.health_retry_at = 0
        self._health_probe = None
        self._last_probe_report = None
        self._repair_queued = False
        self._next_fault_flash = 0
        self._fault_red = False
        self.hardware_recovery = None
        self.state_directory = Path(os.environ.get('GAME_LOG_PATH', '/data/game-events.jsonl')).parent
        self.pending_admin_state = None
        try:
            self.settings = read(self.state_directory / 'runtime-settings.json', {})
            self._apply_settings(self.settings)
        except Exception as error:
            self.settings = {}
            self.fault = {'message': f'Invalid saved configuration: {error}', 'timestamp': time.time()}
            self.phase = 'FAULT'
    def _apply_settings(self, settings):
        fields = {'AUDIO_VOLUME_PERCENT': (0, 400), 'FAILURE_SECONDS': (0, 120), 'VICTORY_SECONDS': (0, 120), 'IDLE_FRAME_SECONDS': (0.5, 60)}
        for name, value in settings.items():
            if name in fields:
                if isinstance(value, bool) or not fields[name][0] <= float(value) <= fields[name][1]:
                    raise ValueError(f'Invalid {name}')
            elif name in ('AUDIO_ENABLED', 'LOG_RAW_ACCEL', 'LOG_HEARTBEAT', 'LOG_RAINBOW_COMMANDS', 'FIRMWARE_AUTO_FLASH'):
                if str(value) not in ('0', '1'):
                    raise ValueError(f'Invalid {name}')
            elif name == 'AUDIO_DEVICE':
                if not isinstance(value, str) or len(value) > 128 or any(ord(c) < 32 for c in value):
                    raise ValueError('Invalid audio device')
            else:
                raise ValueError(f'Unsupported setting: {name}')
        for name, value in settings.items():
            os.environ[name] = str(value)

    def configuration(self):
        names = ('FAILURE_SECONDS', 'VICTORY_SECONDS', 'IDLE_FRAME_SECONDS', 'AUDIO_ENABLED', 'AUDIO_DEVICE',
                 'LOG_RAW_ACCEL', 'LOG_HEARTBEAT', 'LOG_RAINBOW_COMMANDS', 'FIRMWARE_AUTO_FLASH', 'AUDIO_VOLUME_PERCENT')
        defaults = ('15', '45', '2', '1', 'usb', '0', '0', '0', '1', '100')
        return {name: os.environ.get(name, default) for name, default in zip(names, defaults)}

    def start(self):
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
        if not self.fault:
            self.submit('recover', {})

    def submit(self, action, payload):
        supported = ('repair_hardware', 'recover', 'maintenance', 'resume', 'badge', 'reset_game', 'restore_state', 'configure', 'firmware_retry',
                     'host_update', 'host_restart_game', 'host_reboot', 'host_poweroff', 'host_hostname', 'host_configuration', 'host_os_update', 'host_update_installation', 'audio')
        if action == 'recover' and self.phase == 'READY' and not self.maintenance:
            raise ValueError('Enter maintenance mode before reconnecting a running game')
        if action not in supported:
            raise ValueError('Unsupported action')
        if action in ('reset_game', 'restore_state', 'configure', 'firmware_retry', 'audio') or action.startswith('host_'):
            if not self.maintenance:
                raise ValueError('Enter maintenance mode first')
        identity = uuid.uuid4().hex
        record = {'id': identity, 'action': action, 'status': 'QUEUED', 'created_at': time.time()}
        with self.lock:
            self.actions.put_nowait((identity, action, payload))
            self.operations[identity] = record
            for old in list(self.operations)[:-100]:
                if self.operations[old]['status'] not in ('QUEUED', 'RUNNING'):
                    del self.operations[old]
        return dict(record)

    def _worker(self):
        while not self.stopped.is_set():
            try:
                identity, action, payload = self.actions.get(timeout=0.2)
            except queue.Empty:
                continue
            with self.lock:
                self.operations[identity]['status'] = 'RUNNING'
            try:
                result = self._act(action, payload)
                with self.lock:
                    self.operations[identity].update(status='DONE', result=result, finished_at=time.time())
            except Exception as error:
                with self.lock:
                    self.operations[identity].update(status='ERROR', error=str(error), finished_at=time.time())
                self.record_error(str(error))
                if action in ('recover', 'resume', 'firmware_retry'):
                    self.latch_fault(str(error))
            finally:
                self.actions.task_done()

    def record_error(self, message):
        with self.lock:
            self.recent_errors.append({'timestamp': time.time(), 'message': message})
        print(f'CABINET ERROR: {message}')

    def _halt(self, preserve_game=False):
        if self.game:
            self.game.log_state('CONTROLLER_STOPPING')
            if not preserve_game:
                self.game._stopping = True
        if self.arduino:
            self.arduino.event_handler = None
            self.arduino._command_failure = None
            if self.arduino.running:
                try:
                    self.arduino.submit_command('SAFE STOP', origin='admin')
                    self.arduino.wait_until_idle(timeout=3)
                except Exception as error:
                    self.record_error(f'Safe stop failed: {error}')
        if self.audio:
            self.audio.stop_show()

    def latch_fault(self, message):
        if self.fault is not None:
            return
        self.fault = {'message': message, 'timestamp': time.time(), 'hardware_report': self._last_probe_report}
        self.phase = 'FAULT'
        try:
            history = read(self.state_directory / 'fault-history.json', [])
            write(self.state_directory / 'fault-history.json', (history + [self.fault])[-50:])
        except Exception as error:
            self.record_error(f'Fault history could not be saved: {error}')
        preserve_game = '5 consecutive health failures' in message
        if preserve_game and self.game:
            self.game._hardware_paused = True
        self._halt(preserve_game=preserve_game)
        if self.game:
            self.game.log_state('FAULT_ENTERED')
        self._next_fault_flash = 0
        self.record_error(message)

    def _connect(self, force_flash=False, admin_state=None):
        self.last_attempt = time.monotonic()
        self.phase = 'CONNECTING'
        self._halt()
        if self.arduino:
            self.arduino.close()
        self.arduino = None
        self.game = None
        self.arduino = connect_verified(self.factory, port=self.port, baud=115200,
                        on_status=lambda phase, info: setattr(self, 'phase', phase), force_flash=force_flash)
        if self.arduino.protocol_version < 2:
            raise RuntimeError('Firmware does not support correlated command receipts')
        for attempt in range(5):
            self.arduino.submit_command('HEALTH' if attempt == 0 else 'HEALTH RECOVER', origin='health', quiet=True)
            self.arduino.wait_until_idle()
            report = self.arduino.get_diagnostics()['hardware_health']
            if report and report['mcp_ready'] and report['sensor_mask'] == 31:
                break
            if attempt == 4:
                self._last_probe_report = report
                raise RuntimeError(f'Required hardware not ready after 5 checks: {report}')
            if self.stopped.wait(3):
                raise RuntimeError('Controller stopped during health retries')
        self.arduino.submit_command('LEASE ON', origin='health', quiet=True)
        self.arduino.wait_until_idle()
        # LEASE ON's ACK does not update the cached HEALTH report. Refresh it
        # before publishing READY, or tick() can fault on the pre-lease snapshot.
        self.arduino.submit_command('HEALTH', origin='health', quiet=True)
        self.arduino.wait_until_idle()
        report = self.arduino.get_diagnostics()['hardware_health']
        if not report or not report['mcp_ready'] or report['sensor_mask'] != 31 or not report['lease_enabled']:
            raise RuntimeError(f'Hardware or controller lease not ready: {report}')
        self.fault = None
        self.health_failures = 0
        self._health_probe = None
        self.health_retry_at = time.monotonic() + 10
        self._repair_queued = False
        self._new_game(admin_state=admin_state)
        self.phase = 'MAINTENANCE' if self.maintenance else 'READY'
        return {'connected': True, 'firmware': self.arduino.firmware_identity}

    def _new_game(self, admin_state=None):
        if self.audio:
            self.audio.close()
        self.audio = AudioCues()
        config = self.configuration()
        self.game = MoleGame(self.arduino, state_log_path=os.environ.get('GAME_LOG_PATH') or None,
                    audio=self.audio, failure_seconds=config['FAILURE_SECONDS'], victory_seconds=config['VICTORY_SECONDS'],
                    idle_frame_seconds=config['IDLE_FRAME_SECONDS'], stop_requested=lambda: self.stopped.is_set() or self.maintenance or self.fault is not None)
        if self.maintenance:
            self.game._stopping = True
            self.game.state.status = 'MAINTENANCE'
        else:
            self.game.initialize_hardware()
            if admin_state is not None:
                self.game.apply_admin_state(admin_state)
            self.arduino.event_handler = self.game.handle_arduino_event

    def _resume_game_hardware(self):
        # Preserve the live game and serial connection. This is not a restart.
        if self.game:
            showing = getattr(self.game, '_show_active', False)
            with (nullcontext() if showing else self.game._event_lock):
                self.arduino.submit_command('LIGHTS OFF', origin='game')
                self.arduino.submit_command('PLAYER_LIGHTS OFF', origin='game')
                state = self.game.state
                for player in state.completed_players:
                    self.arduino.submit_command(f'PLAYER_LIGHT {PLAYER_INDEX[player]} GREEN', origin='game')
                if showing:
                    for identity in self.game._show_raised:
                        self.arduino.submit_command(f'MOLE {identity} UP', origin='game')
                        self.arduino.submit_command(f'LIGHT {identity} 255 0 0', origin='game')
                    self.arduino.submit_command('SENSORS DISABLE', origin='game')
                    self.game._show_settle_until = time.monotonic() + self.game.FAILURE_SETTLE_SECONDS
                elif state.active_player:
                    self.arduino.submit_command(f'PLAYER_LIGHT {PLAYER_INDEX[state.active_player]} YELLOW', origin='game')
                    struck = set(state.whack_order[:state.hit_progress])
                    for mole, color in state.bug_colors.items():
                        if mole in struck:
                            continue
                        identity = MOLE_ID_BY_NAME[mole]
                        r, g, b = RGB[color]
                        self.arduino.submit_command(f'MOLE {identity} UP', origin='game')
                        self.arduino.submit_command(f'LIGHT {identity} {r} {g} {b}', origin='game')
                    self.game._resume_hit_detection()
                self.arduino.wait_until_idle()
                self.game._stopping = False
                self.arduino.event_handler = self.game.handle_arduino_event
                self.game.log_state('HARDWARE_RECOVERED_GAME_PRESERVED')
        self.fault = None
        self.health_failures = 0
        self._health_probe = None
        self.health_retry_at = time.monotonic() + 10
        self.phase = 'MAINTENANCE' if self.maintenance else 'READY'
        if self.game:
            self.game._hardware_paused = False

    def _act(self, action, payload):
        if action == 'repair_hardware':
            self.phase = 'RECOVERING'
            self.hardware_recovery = {'status': 'RUNNING', 'attempts': 0}
            try:
                for attempt in range(1, 4):
                    self.hardware_recovery['attempts'] = attempt
                    self.arduino.submit_command('SENSORS DISABLE', origin='health', quiet=True)
                    self.arduino.submit_command('HEALTH RECOVER', origin='health', quiet=True)
                    self.arduino.wait_until_idle()
                    report = self.arduino.get_diagnostics()
                    self.hardware_recovery['hardware_report'] = report.get('hardware_health')
                    if self._hardware_healthy(report):
                        self._resume_game_hardware()
                        self.hardware_recovery['status'] = 'RECOVERED'
                        return {'recovered': True, 'game_preserved': True}
                    if attempt < 3 and self.stopped.wait(3):
                        break
                self.hardware_recovery['status'] = 'FAILED'
                raise RuntimeError('Hardware recovery failed; inspect connections and power')
            except Exception as error:
                self.hardware_recovery.update(status='FAILED', error=str(error))
                raise
            finally:
                self._repair_queued = False
                if self.fault:
                    self.phase = 'FAULT'
        if action == 'recover':
            if self.fault and self.game and self.arduino and self.arduino.running and not self.maintenance:
                return self._act('repair_hardware', payload)
            return self._connect()
        if action == 'maintenance':
            self.maintenance = True
            self._halt()
            self.phase = 'MAINTENANCE'
            return {'maintenance': True}
        if action == 'resume':
            self.maintenance = False
            requested_state = self.pending_admin_state
            self.pending_admin_state = None
            return self._connect(admin_state=requested_state)
        if action == 'badge':
            if not self.game or self.phase != 'READY' or self.maintenance or self.fault:
                raise ValueError('Game is not ready')
            player = payload.get('player')
            if player not in PLAYER_IDS:
                raise ValueError('Invalid player')
            self.game.handle_rfid(player)
            return self.game.get_state_dict()
        if action == 'reset_game':
            if payload.get('confirm') != 'RESET GAME':
                raise ValueError('confirm must be RESET GAME')
            self._halt()
            self.pending_admin_state = None
            self._new_game()
            return self.game.get_state_dict()
        if action == 'restore_state':
            if payload.get('confirm') != 'RESTORE GAME':
                raise ValueError('confirm must be RESTORE GAME')
            state = MoleGame.validate_admin_state(payload.get('state'))
            if self.game is None:
                self._new_game()
            self.pending_admin_state = state
            self.game.apply_admin_state(state, hardware=False)
            return {'staged': True, 'apply': 'POST /resume', 'state': self.game.get_state_dict()}
        if action == 'configure':
            settings = payload.get('settings')
            if not isinstance(settings, dict):
                raise ValueError('settings must be an object')
            candidate = {**self.settings, **settings}
            self._apply_settings(candidate)
            write(self.state_directory / 'runtime-settings.json', candidate)
            self.settings = candidate
            if self.audio and 'AUDIO_VOLUME_PERCENT' in settings:
                self.audio.volume_percent = float(settings['AUDIO_VOLUME_PERCENT'])
            return self.configuration()
        if action == 'firmware_retry':
            if payload.get('confirm') != 'FLASH MEGA':
                raise ValueError('confirm must be FLASH MEGA')
            write(history_path(), {})
            return self._connect(force_flash=True)
        if action == 'audio':
            if 'volume_percent' in payload:
                self._act('configure', {'settings': {'AUDIO_VOLUME_PERCENT': payload['volume_percent']}})
                return self.audio.get_diagnostics() if self.audio else {'enabled': False, 'volume_percent': float(payload['volume_percent'])}
            if not self.audio or not self.audio.enabled:
                raise ValueError('Audio is disabled or unavailable')
            cue = payload.get('cue')
            if cue == 'MAX_VOLUME':
                result = self.audio.maximize_volume()
                if result['status'] == 'ERROR':
                    raise RuntimeError(result['error'])
            elif cue == 'STOP':
                self.audio.stop_show()
            elif cue in self.audio.get_diagnostics()['available_cues']:
                self.audio.play(cue)
            else:
                raise ValueError('Unknown audio cue')
            return self.audio.get_diagnostics()
        if action.startswith('host_'):
            return host_bridge.request('POST', '/actions', {**payload, 'action': action[5:]})
        raise ValueError('Unsupported action')

    def serial(self, command):
        if not self.arduino or not self.arduino.running:
            raise RuntimeError('Arduino connection is unavailable')
        # Reads/diagnostics can run in game mode; raw hardware changes require maintenance.
        if not self.maintenance and command.upper() not in ('PING', 'STATUS', 'HEALTH', 'RFID STATUS', 'HEARTBEAT ON', 'HEARTBEAT OFF'):
            raise ValueError('Raw hardware commands require maintenance mode')
        return self.arduino.submit_command(command, origin='admin')

    def health(self):
        reasons = []
        degraded = []
        if not self.arduino or not self.arduino.running:
            reasons.append('SERIAL_DISCONNECTED')
        else:
            report = self.arduino.get_diagnostics()
            hardware = report['hardware_health']
            if hardware and not hardware['rfid_ready']:
                degraded.append('RFID_NOT_READY')
            if not hardware or not hardware['mcp_ready'] or hardware['sensor_mask'] != 31:
                (reasons if self.health_failures >= 5 or self.phase != 'READY' else degraded).append('REQUIRED_HARDWARE_UNAVAILABLE')
            if hardware and not hardware['lease_enabled']:
                (reasons if self.health_failures >= 5 or self.phase != 'READY' else degraded).append('CONTROLLER_LEASE_INACTIVE')
            if report.get('health_command_status') not in (None, 'OK'):
                (reasons if self.health_failures >= 5 or self.phase != 'READY' else degraded).append('HARDWARE_HEALTH_COMMAND_FAILED')
            if report['health_age_seconds'] is None or report['health_age_seconds'] > 20:
                (reasons if self.health_failures >= 5 or self.phase != 'READY' else degraded).append('HARDWARE_HEALTH_STALE')
            if not all(report[name] for name in ('reader_alive', 'writer_alive', 'event_worker_alive')):
                reasons.append('WORKER_STOPPED')
        if self.fault:
            reasons.append('FAULT_LATCHED')
        if self.audio and self.configuration()['AUDIO_ENABLED'] == '1' and not self.audio.enabled:
            degraded.append('AUDIO_UNAVAILABLE')
        if self.health_failures and self.health_failures < 5:
            degraded.append('HEALTH_RETRY_PENDING')
        ready = not reasons and self.phase == 'READY' and not self.maintenance
        return {'status': 'ok' if ready else 'maintenance' if self.maintenance and not reasons else 'fault',
                'ready': ready, 'phase': self.phase, 'maintenance': self.maintenance, 'reasons': reasons, 'degraded': degraded, 'fault': self.fault}

    def _hardware_healthy(self, report):
        hardware = report.get('hardware_health')
        return bool(hardware and hardware['mcp_ready'] and hardware['sensor_mask'] == 31
                    and hardware['lease_enabled'] and report.get('health_command_status') in (None, 'OK')
                    and report.get('health_age_seconds') is not None and report['health_age_seconds'] <= 20)

    def _poll_health(self, now):
        if self.phase not in ('READY', 'MAINTENANCE', 'FAULT'):
            return
        if self._health_probe is not None:
            receipt = self.arduino.command_receipts(self._health_probe)
            if receipt and receipt['status'] not in ('QUEUED', 'SENT'):
                self._health_probe = None
                report = self.arduino.get_diagnostics()
                self._last_probe_report = report.get('hardware_health')
                if receipt['status'] == 'OK' and self._hardware_healthy(report):
                    self.health_failures = 0
                    self.health_retry_at = now + 10
                else:
                    self.health_failures += 1
                    self.health_retry_at = now + 3
                    self.record_error(f'Health check failed ({self.health_failures}/5): {self._last_probe_report}')
                    if self.health_failures >= 5 and self.phase == 'READY':
                        self.latch_fault('Required hardware lost after 5 consecutive health failures')
                        if not self._repair_queued:
                            self._repair_queued = True
                            self.submit('repair_hardware', {})
        if self._health_probe is None and now >= self.health_retry_at:
            receipt = self.arduino.submit_command('HEALTH', origin='health', quiet=True)
            self._health_probe = receipt['id']
            self.last_probe = now

    def _flash_fault(self, now):
        if self.phase not in ('FAULT', 'RECOVERING') or now < self._next_fault_flash:
            return
        commands = getattr(self.arduino, 'command_queue', None)
        if commands is not None and commands.unfinished_tasks:
            return
        self._fault_red = not self._fault_red
        color = '255 0 0' if self._fault_red else '0 0 0'
        for mole in range(5):
            self.arduino.submit_command(f'LIGHT {mole} {color}', origin='fault', quiet=True)
        self.arduino.submit_command(f'PLAYER_LIGHTS {color}', origin='fault', quiet=True)
        self._next_fault_flash = now + 0.5

    def tick(self):
        controller = self.arduino
        if controller and controller.running:
            now = time.monotonic()
            try:
                if now - self.last_keepalive >= 1:
                    controller.submit_command('KEEPALIVE', origin='health', quiet=True)
                    self.last_keepalive = now
                self._poll_health(now)
                self._flash_fault(now)
            except RuntimeError as error:
                self.latch_fault(str(error))
            if controller.event_failure or controller._command_failure:
                self.latch_fault(controller.event_failure or controller._command_failure)
            if self.phase == 'READY' and self.health()['reasons']:
                self.latch_fault('; '.join(self.health()['reasons']))
        elif self.phase == 'READY':
            reason = getattr(controller, 'failure_reason', None) or 'Arduino disconnected'
            self.latch_fault(reason)
            self.pending_admin_state = None
            if self.game:
                self.game.state = GameState()
                self.game.log_state('CONTROLLER_LOST_GAME_RESET')
            if reason == 'Unexpected Arduino reset':
                self.maintenance = False
                self.submit('recover', {})
        if self.game and self.game.persistence_error:
            self.latch_fault(f'Persistence failure: {self.game.persistence_error}')
        if self.phase == 'READY' and self.game:
            try:
                self.game.tick_idle()
            except Exception as error:
                self.latch_fault(str(error))

    def get_state_dict(self):
        state = self.game.get_state_dict() if self.game else {'status': 'UNAVAILABLE', 'solve_state': None, 'completed_players': [], 'active_player': None,
                                                            'hit_progress': 0, 'ticket_dispensed': False, 'tickets_dispensed': 0}
        return {**state, 'controller': self.health()}

    def get_diagnostics(self):
        if self.game and self.arduino:
            report = diagnostics(self.game, self.started_at)
        else:
            report = {'application': application_info(), 'host': read_json('/run/mole-host-info.json'),
                      'firmware': {'expected': read_json(Path(os.environ.get('FIRMWARE_DIR', '/opt/mole-firmware')) / 'manifest.json')},
                      'game': self.get_state_dict()}
        return {**report, 'controller': self.health(), 'recent_errors': list(self.recent_errors),
                'configuration': self.configuration(),
                'active_configuration': {'failure_seconds': self.game.failure_seconds,
                                         'victory_seconds': self.game.victory_seconds,
                                         'idle_frame_seconds': self.game.idle_frame_seconds} if self.game else None,
                'firmware_history': read_json(history_path()) or {},
                'operations': list(self.operations.values()),
                'operation_queue_depth': self.actions.qsize(),
                'control_worker_alive': bool(self.worker and self.worker.is_alive()),
                'pending_admin_restore': self.pending_admin_state is not None,
                'health_monitor': {'normal_interval_seconds': 10, 'retry_interval_seconds': 3, 'failure_limit': 5, 'consecutive_failures': self.health_failures, 'probe_pending': self._health_probe is not None, 'last_hardware_report': self._last_probe_report},
                'hardware_recovery': self.hardware_recovery,
                'fault_history': read_json(self.state_directory / 'fault-history.json') or []}

    def close(self):
        self.maintenance = True
        self._halt()
        if self.arduino:
            self.arduino.close()
        if self.audio:
            self.audio.close()
