"""Standalone whack-a-mole game controller."""
import colorsys
import random
from dataclasses import dataclass

@dataclass
class Settings:
    round_seconds: float = 30
    target_seconds: float = 1
    countdown_seconds: float = 3
    settle_seconds: float = .2
    flash_seconds: float = .1
    chase_seconds: float = .12
    chase_cycles: int = 2
    threshold: int = 6000
    cooldown_ms: int = 300
    red: tuple = (80, 0, 0)
    yellow: tuple = (80, 80, 0)
    green: tuple = (0, 80, 0)

    def __post_init__(self):
        if not (0 <= self.settle_seconds < self.target_seconds):
            raise ValueError('settle_seconds must be less than target_seconds')
        if min(self.round_seconds, self.target_seconds, self.flash_seconds, self.chase_seconds) <= 0:
            raise ValueError('timings must be positive')
        if self.countdown_seconds < 0 or self.chase_cycles < 1:
            raise ValueError('invalid countdown/chase')

class Game:
    def __init__(self, send, settings=None, rng=None, sound=lambda cue: None):
        self.send, self.cfg = send, settings or Settings()
        self.rng, self.sound = rng or random.Random(), sound
        self.state, self.score, self.active, self.previous = 'idle', 0, None, None
        self.token = 0
        self.flashes = {}
        self.flash_phases = {}
        self.last_frame = -1
        self.last_keepalive = -1

    def light(self, mole, color):
        self.send(f'LIGHT {mole} {color[0]} {color[1]} {color[2]}')

    def initialize(self):
        self.send('SAFE STOP')
        self.send('LEASE ON')
        self.send(f'CONFIG {self.cfg.threshold} {round(self.cfg.settle_seconds*1000)} {self.cfg.cooldown_ms}')
        self.state, self.active = 'idle', None
        self.flashes.clear()
        self.last_frame = -1

    def start(self, now):
        if self.state != 'idle':
            return
        self.state, self.score, self.previous = 'countdown', 0, None
        self.flashes.clear()
        self.deadline = now + self.cfg.countdown_seconds
        self.sound('start')

    def next_target(self, now):
        if self.active is not None:
            self.send(f'MOLE {self.active} DOWN')
            if self.active not in self.flashes:
                self.light(self.active, self.cfg.red)
        choices = [i for i in range(5) if i != self.previous]
        self.active = self.rng.choice(choices)
        self.previous = self.active
        # A new appearance owns its ring, overriding any old green flash.
        self.flashes.pop(self.active, None)
        self.token += 1
        self.raised = now
        self.target_deadline = now + self.cfg.target_seconds
        self.send(f'TARGET {self.active} {self.token}')
        self.light(self.active, self.cfg.yellow)
        self.sound('appear')

    def hit(self, mole, token, now):
        if (self.state != 'playing' or now >= self.round_deadline
                or now >= self.target_deadline or mole != self.active
                or token != self.token or now < self.raised + self.cfg.settle_seconds):
            return
        self.score += 1
        self.flashes[mole] = now
        self.sound('hit')
        self.next_target(now)

    def finish(self, now):
        self.send('SAFE STOP')
        self.send('LEASE ON')
        self.active, self.state = None, 'chase'
        self.flashes.clear()
        self.chase_start = now
        self.last_frame = -1
        self.sound('game_over')
        print(f'Final score: {self.score}')

    def tick(self, now):
        if now-self.last_keepalive >= 1:
            self.send('KEEPALIVE')
            self.last_keepalive = now
        if self.state == 'countdown' and now >= self.deadline:
            self.state = 'playing'
            self.round_deadline = now + self.cfg.round_seconds
            for i in range(5):
                self.light(i, self.cfg.red)
            self.next_target(now)
        if self.state == 'playing':
            if now >= self.round_deadline:
                self.finish(now)
            elif now >= self.target_deadline:
                self.next_target(now)
            else:
                for i, begin in list(self.flashes.items()):
                    phase = int((now-begin)/self.cfg.flash_seconds)
                    if self.flash_phases.get(i) != (begin, phase):
                        self.light(i, self.cfg.green if phase in (0, 2) else self.cfg.red)
                        self.flash_phases[i] = (begin, phase)
                    if phase >= 4:
                        del self.flashes[i]
        if self.state == 'chase':
            frame = int((now-self.chase_start)/self.cfg.chase_seconds)
            if frame >= 5*self.cfg.chase_cycles:
                self.state, self.last_frame = 'idle', -1
            elif frame != self.last_frame:
                for i in range(5):
                    self.light(i, self.cfg.yellow if i == frame % 5 else (0,0,0))
                self.last_frame = frame
        if self.state == 'idle':
            frame = int(now*10)
            if frame != self.last_frame:
                for i in range(5):
                    color = colorsys.hsv_to_rgb((now/10+i/5)%1, 1, .3)
                    self.light(i, tuple(round(c*255) for c in color))
                self.last_frame = frame
