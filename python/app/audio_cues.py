"""Optional local ALSA playback with replaceable WAV placeholders."""
import array
import math
import os
from pathlib import Path
import queue
import random
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


class AudioCues(SilentAudio):
    def __init__(self):
        self.directory = Path(os.environ.get('AUDIO_DIR', Path(__file__).parent / 'sounds'))
        self.device = os.environ.get('AUDIO_DEVICE', 'default')
        self.enabled = os.environ.get('AUDIO_ENABLED', '1') != '0' and shutil.which('aplay') is not None
        self.queue = queue.Queue(maxsize=8)
        self.stopped = threading.Event()
        self.process = None
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

    def play(self, cue):
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
                    if cue in ('failure_mix', 'victory_mix') or ':' in cue:
                        path = Path(folder) / 'failure.wav'
                        samples = (reaction_mix(self.directory, seconds, cue.split(':')[1], victory=cue.startswith('victory_'))
                                   if ':' in cue else failure_mix(self.directory, seconds, victory=cue == 'victory_mix'))
                        with wave.open(str(path), 'wb') as target:
                            target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                            target.writeframes(samples)
                    else:
                        path = self.directory / f'{cue}.wav'
                        read_samples(path)  # Validate replacements before invoking aplay.
                    with self.process_lock:
                        if self.stopped.is_set() or generation != self._generation:
                            continue
                        self.process = subprocess.Popen(['aplay', '-q', '-D', self.device, str(path)],
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        result = self.process.wait(timeout=(seconds or 5) + 5)
                        if result and generation == self._generation and not self.stopped.is_set():
                            print(f'Audio playback failed: {cue}; check AUDIO_DEVICE.')
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                    finally:
                        with self.process_lock:
                            self.process = None
            except Exception as error:
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
