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


def failure_mix(directory, seconds, rng=None):
    """Mix all laugh variants, then repeat randomly for the full failure state."""
    rng = rng or random.Random()
    tracks = {name: read_samples(directory / f'{name}.wav')
              for name in ('failure', 'laugh_1', 'laugh_2', 'laugh_3')}
    mixed = [0] * math.ceil(seconds * SAMPLE_RATE)
    schedule = [('failure', 0), ('laugh_1', 0.1), ('laugh_2', 0.4), ('laugh_3', 0.7)]
    moment = 1.0
    while moment < seconds:
        schedule.append((rng.choice(('laugh_1', 'laugh_2', 'laugh_3')), moment))
        moment += rng.uniform(0.35, 0.8)
    for name, moment in schedule:
        offset = int(moment * SAMPLE_RATE)
        for index, sample in enumerate(tracks[name][:max(0, len(mixed) - offset)]):
            mixed[offset + index] += int(sample * 0.3)
    output = array.array('h', (max(-32768, min(32767, sample)) for sample in mixed))
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
        self._enqueue((cue, None))

    def play_failure(self, seconds):
        # Failure takes precedence over short cues queued immediately before it.
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        with self.process_lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
        self._enqueue(('failure_mix', seconds))

    def _loop(self):
        while not self.stopped.is_set():
            try:
                cue, seconds = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                with tempfile.TemporaryDirectory(prefix='mole-audio-') as folder:
                    if cue == 'failure_mix':
                        path = Path(folder) / 'failure.wav'
                        samples = failure_mix(self.directory, seconds)
                        with wave.open(str(path), 'wb') as target:
                            target.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                            target.writeframes(samples)
                    else:
                        path = self.directory / f'{cue}.wav'
                        read_samples(path)  # Validate replacements before invoking aplay.
                    with self.process_lock:
                        if self.stopped.is_set():
                            continue
                        self.process = subprocess.Popen(['aplay', '-q', '-D', self.device, str(path)],
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        result = self.process.wait(timeout=(seconds or 5) + 5)
                        if result:
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
