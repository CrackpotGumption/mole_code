"""Optional local ALSA playback with replaceable WAV placeholders."""
import array
import math
import os
from pathlib import Path
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave

SAMPLE_RATE = 22050


class SilentAudio:
    def play(self, cue):
        pass

    def play_failure(self, seconds):
        pass

    def play_failure_hit(self, seconds):
        return min(0.6, seconds)

    def play_victory(self, seconds):
        pass

    def play_victory_hit(self, seconds):
        return min(0.6, seconds)

    def stop_show(self):
        pass

    def close(self):
        pass


def read_samples(path):
    with wave.open(str(path), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError(f'{path}: use mono 16-bit PCM WAV at {SAMPLE_RATE} Hz')
        samples = array.array('h', source.readframes(source.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples


def failure_mix(directory, seconds, rng=None, include_failure=True, victory=False):
    """Space out failure laughs; retain the layered victory celebration."""
    rng = rng or random.Random()
    names = ('cheer', 'whistle', 'kiss') if victory else ('laugh_1', 'laugh_2', 'laugh_3')
    intro = 'victory' if victory else 'failure'
    tracks = {name: read_samples(directory / f'{name}.wav') for name in (intro, *names)}
    mixed = [0] * math.ceil(seconds * SAMPLE_RATE)
    schedule = [(name, 0.1 + index * 0.3) for index, name in enumerate(names)] if victory else []
    if include_failure:
        schedule.insert(0, (intro, 0))
    moment = 1.0 if victory or include_failure else 0.1
    while moment < seconds:
        name = rng.choice(names)
        schedule.append((name, moment))
        moment += (rng.uniform(0.35, 0.8) if victory
                   else len(tracks[name]) / SAMPLE_RATE + rng.uniform(0.4, 0.8))
    for name, moment in schedule:
        offset = int(moment * SAMPLE_RATE)
        for index, sample in enumerate(tracks[name][:max(0, len(mixed) - offset)]):
            mixed[offset + index] += int(sample * 0.3)
    output = array.array('h', (max(-32768, min(32767, sample)) for sample in mixed))
    if sys.byteorder != 'little':
        output.byteswap()
    return output.tobytes()


def reaction_mix(directory, seconds, cue, victory=False):
    reaction = read_samples(directory / f'{cue}.wav')
    total = math.ceil(seconds * SAMPLE_RATE)
    reaction = reaction[:total]
    output = array.array('h', (int(sample * 0.7) for sample in reaction))
    remainder = total - len(output)
    if remainder:
        tail = array.array('h')
        tail.frombytes(failure_mix(directory, remainder / SAMPLE_RATE, include_failure=False, victory=victory))
        if sys.byteorder != 'little':
            tail.byteswap()
        output.extend(tail[:remainder])
    if sys.byteorder != 'little':
        output.byteswap()
    return output.tobytes()


def category_mix(paths, seconds, rng=None, voices=None):
    """Repeat random tracks on 2–3 lanes; concurrency never exceeds lane count."""
    rng = rng or random.Random()
    voices = rng.randint(2, 3) if voices is None else voices
    tracks = [read_samples(path) for path in paths]
    tracks = [track for track in tracks if track]
    total = math.ceil(seconds * SAMPLE_RATE)
    mixed = [0] * total
    if tracks:
        for lane in range(voices):
            offset = int(lane * 0.15 * SAMPLE_RATE)
            while offset < total:
                track = rng.choice(tracks)
                for index, sample in enumerate(track[:total - offset]):
                    mixed[offset + index] += int(sample / max(voices, 1) * 0.8)
                offset += len(track) + int(rng.uniform(0.2, 0.5) * SAMPLE_RATE)
    output = array.array('h', (max(-32768, min(32767, sample)) for sample in mixed))
    if sys.byteorder != 'little':
        output.byteswap()
    return output.tobytes()


def amplify_samples(samples, percent):
    gain = float(percent) / 100
    clipped = 0
    output = array.array('h')
    for sample in samples:
        scaled = round(sample * gain)
        if scaled < -32768 or scaled > 32767:
            clipped += 1
        output.append(max(-32768, min(32767, scaled)))
    return output, clipped


def select_audio_device(requested, root=Path('/proc/asound')):
    """Use ALSA card names so USB selection survives card-number changes."""
    cards = []
    for path in sorted(root.glob('card[0-9]*')):
        try:
            if (path / 'usbid').is_file():
                cards.append({'id': (path / 'id').read_text().strip(),
                              'usb_id': (path / 'usbid').read_text().strip()})
        except OSError:
            continue
    # Docker may omit /proc/asound even while /dev/snd supports ALSA queries.
    if not cards:
        try:
            listing = subprocess.run(['aplay', '-l'], capture_output=True, text=True, timeout=5)
            seen = set()
            for line in listing.stdout.splitlines():
                match = re.match(r'card (\d+): (\S+) \[.*?\], device (\d+):', line)
                if not match:
                    continue
                number, identity, device = match.groups()
                if identity in seen:
                    continue
                info = subprocess.run(['amixer', '-c', identity, 'info'], capture_output=True, text=True, timeout=5)
                sys_path = Path('/sys/class/sound') / f'card{number}' / 'device'
                usb = ('usb' in (line + info.stdout).lower()
                       or any(re.fullmatch(r'usb\d+', part) for part in sys_path.resolve().parts))
                if usb:
                    cards.append({'id': identity, 'usb_id': None, 'device': int(device), 'discovery': 'ALSA'})
                    seen.add(identity)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if requested not in ('default', 'usb'):
        return requested, cards, None
    if len(cards) == 1:
        return f"plughw:CARD={cards[0]['id']},DEV={cards[0].get('device', 0)}", cards, None
    if cards:
        return requested, cards, 'Multiple USB audio cards; configure AUDIO_DEVICE with a specific ALSA card ID'
    return requested, cards, 'No USB audio card detected; built-in output will not be selected'


def maximize_usb_volume(device, cards):
    """Unmute/max only playback controls on the selected USB sound card."""
    card = next((item['id'] for item in cards if f"CARD={item['id']}," in device), None)
    report = {'card': card, 'target_percent': 100, 'controls': [], 'status': 'NOT_USB'}
    if card is None:
        return report
    try:
        def mixer(*args):
            result = subprocess.run(['amixer', '-c', card, *args], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or 'amixer failed')
            return result.stdout
        controls = mixer('scontrols')
        for name, index in re.findall(r"Simple mixer control '(.+)',(\d+)", controls):
            identity = f'{name},{index}'
            before = mixer('sget', identity)
            capabilities = next((line for line in before.splitlines() if 'Capabilities:' in line), '')
            settings = []
            if 'pvolume' in capabilities:
                settings.append('100%')
            if 'pswitch' in capabilities:
                settings.append('unmute')
            if settings:
                after = mixer('sset', identity, *settings)
                report['controls'].append({'name': name, 'index': int(index), 'readback': after})
        report['status'] = 'APPLIED' if report['controls'] else 'NO_PLAYBACK_CONTROLS'
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        report.update(status='ERROR', error=str(error))
    return report


class AudioCues(SilentAudio):
    def __init__(self):
        self.directory = Path(os.environ.get('AUDIO_DIR', Path(__file__).parent / 'sounds'))
        packaged = Path(__file__).parent / 'fx'
        self.fx_directory = Path(os.environ.get('FX_DIR', packaged if packaged.exists() else Path(__file__).resolve().parents[2] / 'fx'))
        self.last_files = []
        self.volume_percent = float(os.environ.get('AUDIO_VOLUME_PERCENT', '100'))
        self.last_clipped_samples = 0
        self.requested_device = os.environ.get('AUDIO_DEVICE', 'usb')
        self.device, self.usb_cards, device_error = select_audio_device(self.requested_device)
        self.enabled = os.environ.get('AUDIO_ENABLED', '1') != '0' and shutil.which('aplay') is not None
        self.queue = queue.Queue(maxsize=8)
        self.stopped = threading.Event()
        self.process = None
        self.last_error = device_error
        if device_error:
            self.enabled = False
            print(f'AUDIO ERROR: {device_error}')
        self.mixer = maximize_usb_volume(self.device, self.usb_cards) if self.enabled else {'status': 'DISABLED'}
        self.last_cue = None
        self.process_lock = threading.Lock()
        self._generation = 0
        if self.enabled:
            self.worker = threading.Thread(target=self._loop, daemon=True)
            self.worker.start()
        else:
            print('Audio disabled or aplay unavailable; game continues without sound.')

    def _enqueue(self, item):
        if self.enabled and not self.stopped.is_set():
            try:
                self.queue.put_nowait(item)
            except queue.Full:
                pass

    def maximize_volume(self):
        self.mixer = maximize_usb_volume(self.device, self.usb_cards)
        return self.mixer

    def category_files(self, category):
        root = getattr(self, 'fx_directory', None)
        if root is None:
            return []
        paths = sorted((root / category).glob('*.wav'))
        if category == 'cheer':
            paths += sorted((root / 'cheers').glob('*.wav'))
        return paths

    def choose_cue(self, cue):
        category = {'mole_hit': 'hit', 'cheer': 'cheer', 'victory': 'victory'}.get(cue)
        files = self.category_files(category) if category else []
        return 'asset:' + str(random.choice(files)) if files else cue

    def play(self, cue):
        original = cue
        cue = self.choose_cue(cue)
        if cue.startswith('asset:'):
            if original == 'cheer':
                # Let the final correct-hit cue finish before cheering.
                with self.process_lock:
                    self._enqueue((cue, None, self._generation))
            else:
                self._replace(cue, None)
            return
        if cue == 'game_start':
            self._replace(cue, None)
        else:
            with self.process_lock:
                self._enqueue((cue, None, self._generation))

    def _replace(self, cue, seconds):
        with self.process_lock:
            self._generation += 1
            while True:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except queue.Empty:
                    break
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self._enqueue((cue, seconds, self._generation))

    def play_failure(self, seconds):
        self._replace('failure_mix', seconds)

    def play_failure_hit(self, seconds):
        files = self.category_files('hit')
        if files:
            path = random.choice(files)
            duration = len(read_samples(path)) / SAMPLE_RATE
            self._replace('fx_reaction:' + str(path), seconds)
            return min(duration, seconds)
        cue = random.choice(('ouch_1', 'ouch_2', 'ouch_3'))
        try:
            duration = len(read_samples(self.directory / f'{cue}.wav')) / SAMPLE_RATE
        except Exception:
            duration = 0.6
        self._replace(f'reaction:{cue}', seconds)
        return min(duration, seconds)

    def play_victory(self, seconds):
        self._replace('victory_mix', seconds)

    def play_victory_hit(self, seconds):
        files = self.category_files('hit')
        if files:
            path = random.choice(files)
            duration = len(read_samples(path)) / SAMPLE_RATE
            self._replace('fx_victory_reaction:' + str(path), seconds)
            return min(duration, seconds)
        try:
            duration = len(read_samples(self.directory / 'encouraging_whistle.wav')) / SAMPLE_RATE
        except Exception:
            duration = 0.6
        self._replace('victory_reaction:encouraging_whistle', seconds)
        return min(duration, seconds)

    def stop_show(self):
        with self.process_lock:
            self._generation += 1
            while True:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except queue.Empty:
                    break
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()

    def _loop(self):
        while not self.stopped.is_set():
            try:
                cue, seconds, generation = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                with tempfile.TemporaryDirectory(prefix='mole-audio-') as folder:
                    custom = None
                    self.last_files = []
                    if cue.startswith('asset:'):
                        path = Path(cue.split(':', 1)[1])
                        self.last_files = [str(path)]
                        read_samples(path)
                    elif cue == 'failure_mix' and self.category_files('laugh'):
                        paths = self.category_files('laugh')
                        voices = random.randint(2, 3)
                        chosen = random.sample(paths, min(voices, len(paths)))
                        self.last_files = [str(path) for path in chosen]
                        custom = category_mix(chosen, seconds, voices=voices)
                    elif cue == 'victory_mix' and self.category_files('victory'):
                        path = random.choice(self.category_files('victory'))
                        self.last_files = [str(path)]
                        read_samples(path)
                    elif cue.startswith(('fx_reaction:', 'fx_victory_reaction:')):
                        path = Path(cue.split(':', 1)[1])
                        self.last_files = [str(path)]
                        reaction = read_samples(path)[:math.ceil(seconds * SAMPLE_RATE)]
                        remaining = max(0, seconds - len(reaction) / SAMPLE_RATE)
                        tail = (category_mix(self.category_files('laugh'), remaining)
                                if cue.startswith('fx_reaction:') else bytes(math.ceil(remaining * SAMPLE_RATE) * 2))
                        if sys.byteorder != 'little':
                            reaction.byteswap()
                        custom = reaction.tobytes() + tail
                    elif cue in ('failure_mix', 'victory_mix') or ':' in cue:
                        path = Path(folder) / 'failure.wav'
                        samples = (reaction_mix(self.directory, seconds, cue.split(':')[1], victory=cue.startswith('victory_'))
                                   if ':' in cue else failure_mix(self.directory, seconds, victory=cue == 'victory_mix'))
                        with wave.open(str(path), 'wb') as target:
                            target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                            target.writeframes(samples)
                    else:
                        path = self.directory / f'{cue}.wav'
                        read_samples(path)  # Validate replacements before invoking aplay.
                    if custom is not None:
                        path = Path(folder) / 'category.wav'
                        with wave.open(str(path), 'wb') as target:
                            target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                            target.writeframes(custom)
                    source_samples = read_samples(path)
                    duration = len(source_samples) / SAMPLE_RATE
                    gained, self.last_clipped_samples = amplify_samples(source_samples, self.volume_percent)
                    if self.volume_percent != 100:
                        path = Path(folder) / 'volume.wav'
                        if sys.byteorder != 'little':
                            gained.byteswap()
                        with wave.open(str(path), 'wb') as target:
                            target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                            target.writeframes(gained.tobytes())
                    with self.process_lock:
                        if self.stopped.is_set() or generation != self._generation:
                            continue
                        self.last_cue = cue
                        self.process = subprocess.Popen(['aplay', '-q', '-D', self.device, str(path)],
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    try:
                        _, stderr = self.process.communicate(timeout=max(seconds or 0, duration) + 5)
                        result = self.process.returncode
                        if result and generation == self._generation and not self.stopped.is_set():
                            self.last_error = f'Audio playback failed: {cue}: {stderr.decode(errors="replace")[-4096:]}'
                            print(self.last_error)
                    except subprocess.TimeoutExpired:
                        self.last_error = f"Audio playback timed out: {cue}"
                        self.process.kill()
                        self.process.communicate()
                    finally:
                        with self.process_lock:
                            self.process = None
            except Exception as error:
                self.last_error = str(error)
                print(f'AUDIO ERROR: {error}')
            finally:
                self.queue.task_done()

    def close(self):
        self.stopped.set()
        with self.process_lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
        if self.enabled:
            self.worker.join(timeout=2)


    def get_diagnostics(self):
        with self.process_lock:
            return {'enabled': self.enabled, 'device': self.device,
                    'requested_device': self.requested_device, 'usb_cards': self.usb_cards, 'mixer': self.mixer,
                    'volume_percent': self.volume_percent, 'last_clipped_samples': self.last_clipped_samples,
                    'queue_depth': self.queue.qsize(), 'last_cue': self.last_cue,
                    'last_error': self.last_error,
                    'playing': self.process is not None and self.process.poll() is None,
                    'worker_alive': self.worker.is_alive() if self.enabled else False,
                    'last_files': self.last_files,
                    'categories': {name: [path.name for path in self.category_files(name)] for name in ('hit', 'laugh', 'cheer', 'victory')},
                    'available_cues': sorted({path.stem for path in self.directory.glob('*.wav')} | {'mole_hit', 'cheer', 'victory'})}
