"""Bounded serial loop, reconnect and best-effort shutdown."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from game import Game, Settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--sounds', type=Path)
    args = parser.parse_args()
    import serial
    cfg = Settings(**json.loads(args.config.read_text())) if args.config else Settings()
    players = []
    def sound(cue):
        players[:] = [p for p in players if p.poll() is None]
        path = args.sounds / (cue+'.wav') if args.sounds else None
        if path and path.is_file() and len(players) < 8:
            try:
                players.append(subprocess.Popen(['aplay','-q',str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            except OSError:
                pass
    link = None
    try:
        while True:
            try:
                link = serial.Serial(args.port, 115200, timeout=.01, write_timeout=.2)
                # Opening USB may reset Mega; wait for matching ready identity.
                limit = time.monotonic()+10
                while time.monotonic() < limit:
                    if link.readline().decode(errors='replace').strip() == 'READY STANDALONE_V1':
                        break
                else:
                    raise OSError('No standalone READY; check firmware/board, no motion sent')
                def send(command):
                    link.write((command+'\n').encode())
                game = Game(send, cfg, sound=sound)
                game.initialize()
                while True:
                    now = time.monotonic()
                    # Timer wins over packets received at/after round end.
                    game.tick(now)
                    line = link.readline().decode(errors='replace').strip()
                    parts = line.split()
                    if parts == ['START']:
                        game.start(time.monotonic())
                    elif len(parts) == 4 and parts[0] == 'HIT':
                        try:
                            game.hit(int(parts[1]), int(parts[2]), time.monotonic())
                        except ValueError:
                            pass
                    elif line.startswith('ERROR') or line == 'LEASE EXPIRED':
                        raise OSError(line)
            except (serial.SerialException, OSError) as error:
                print(f'Controller unavailable: {error}; retrying with a fresh idle session')
                if link:
                    try:
                        link.write(b'SAFE STOP\n')
                    except (serial.SerialException, OSError):
                        pass
                    link.close()
                    link = None
                time.sleep(2)
    finally:
        if link:
            try:
                link.write(b'SAFE STOP\n')
            finally:
                link.close()
        for process in players:
            if process.poll() is None:
                process.terminate()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
