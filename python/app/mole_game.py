import colorsys
import math
import random
import time
import threading

from dataclasses import dataclass, field

from .bugs import BUGS, Color
from .game import calculate_whack_order
from .state_log import StateLog
from pathlib import Path
from .audio_cues import SilentAudio


# ============================================================
# PLAYERS
# ============================================================

PLAYER_IDS = (
    "001",
    "002",
    "003",
    "004",
    "005",
    "006",
)


PLAYER_INDEX = {
    player_id: index
    for index, player_id in enumerate(PLAYER_IDS)
}


# ============================================================
# STATIC PUZZLES
#
# Badge 001 = Round 1
# Badge 002 = Round 2
# etc.
# ============================================================

STATIC_PUZZLES = {

    # --------------------------------------------------------
    # ROUND 1 / PLAYER 001
    #
    # Expected:
    # NILES -> ROZ -> MARTIN -> DAPHNE
    # --------------------------------------------------------

    "001": {
        "FRASIER": Color.WHITE,
        "NILES": Color.YELLOW,
        "MARTIN": Color.RED,
        "DAPHNE": Color.GREEN,
        "ROZ": Color.BLUE,
    },


    # --------------------------------------------------------
    # ROUND 2 / PLAYER 002
    #
    # Expected:
    # MARTIN -> ROZ -> NILES -> FRASIER
    # --------------------------------------------------------

    "002": {
        "FRASIER": Color.BLUE,
        "NILES": Color.PURPLE,
        "MARTIN": Color.ORANGE,
        "DAPHNE": Color.WHITE,
        "ROZ": Color.GREEN,
    },


    # --------------------------------------------------------
    # ROUND 3 / PLAYER 003
    #
    # Expected:
    # FRASIER -> DAPHNE -> ROZ -> MARTIN
    # --------------------------------------------------------

    "003": {
        "FRASIER": Color.GREEN,
        "NILES": Color.RED,
        "MARTIN": Color.BLUE,
        "DAPHNE": Color.YELLOW,
        "ROZ": Color.PURPLE,
    },


    # --------------------------------------------------------
    # ROUND 4 / PLAYER 004
    #
    # Expected:
    # DAPHNE -> NILES -> ROZ -> FRASIER
    # --------------------------------------------------------

    "004": {
        "FRASIER": Color.PURPLE,
        "NILES": Color.ORANGE,
        "MARTIN": Color.RED,
        "DAPHNE": Color.BLUE,
        "ROZ": Color.GREEN,
    },


    # --------------------------------------------------------
    # ROUND 5 / PLAYER 005
    #
    # Expected:
    # FRASIER -> DAPHNE -> NILES -> MARTIN
    # --------------------------------------------------------

    "005": {
        "FRASIER": Color.YELLOW,
        "NILES": Color.BLUE,
        "MARTIN": Color.PURPLE,
        "DAPHNE": Color.GREEN,
        "ROZ": Color.ORANGE,
    },


    # --------------------------------------------------------
    # ROUND 6 / PLAYER 006
    #
    # Expected:
    # DAPHNE -> FRASIER -> MARTIN -> NILES
    # --------------------------------------------------------

    "006": {
        "FRASIER": Color.GREEN,
        "NILES": Color.PURPLE,
        "MARTIN": Color.BLUE,
        "DAPHNE": Color.YELLOW,
        "ROZ": Color.ORANGE,
    },
}


# ============================================================
# EXPECTED SOLUTIONS
#
# These are used to sanity-check the rules engine.
# If calculate_whack_order() ever produces something different,
# the game will tell us immediately.
# ============================================================

EXPECTED_ORDERS = {
    "001": [
        "NILES",
        "ROZ",
        "MARTIN",
        "DAPHNE",
    ],

    "002": [
        "MARTIN",
        "ROZ",
        "NILES",
        "FRASIER",
    ],

    "003": [
        "FRASIER",
        "DAPHNE",
        "ROZ",
        "MARTIN",
    ],

    "004": [
        "DAPHNE",
        "NILES",
        "ROZ",
        "FRASIER",
    ],

    "005": [
        "FRASIER",
        "DAPHNE",
        "NILES",
        "MARTIN",
    ],

    "006": [
        "DAPHNE",
        "FRASIER",
        "MARTIN",
        "NILES",
    ],
}


# ============================================================
# PHYSICAL MOLE MAPPING
#
# Arduino logical mole IDs:
#
# 0 = Front left
# 1 = Front center
# 2 = Front right
# 3 = Back left
# 4 = Back right
# ============================================================

MOLE_BY_ID = {
    0: "MARTIN",
    1: "DAPHNE",
    2: "NILES",
    3: "FRASIER",
    4: "ROZ",
}


MOLE_ID_BY_NAME = {
    name: mole_id
    for mole_id, name in MOLE_BY_ID.items()
}


# ============================================================
# RGB COLORS
# ============================================================

RGB = {
    Color.WHITE: (
        255,
        255,
        255,
    ),

    Color.RED: (
        255,
        0,
        0,
    ),

    Color.ORANGE: (
        255,
        80,
        0,
    ),

    Color.YELLOW: (
        255,
        255,
        0,
    ),

    Color.GREEN: (
        0,
        255,
        0,
    ),

    Color.BLUE: (
        0,
        0,
        255,
    ),

    Color.PURPLE: (
        160,
        0,
        255,
    ),
}


# ============================================================
# GAME STATE
# ============================================================

@dataclass
class GameState:

    active_player: str | None = None

    completed_players: set[str] = field(
        default_factory=set
    )

    bug_colors: dict[str, Color] = field(
        default_factory=dict
    )

    queen: str | None = None

    whack_order: list[str] = field(
        default_factory=list
    )

    hit_progress: int = 0

    locked: bool = True

    status: str = "WAITING FOR BADGE"

    ticket_dispensed: bool = False
    ticket_status: str = "NOT REQUESTED"
    tickets_dispensed: int = 0


# ============================================================
# GAME
# ============================================================

class MoleGame:

    HIT_Z_THRESHOLD = -9000
    HIT_RELEASE_Z = -6400
    HIT_COOLDOWN = 0.300
    SENSOR_CHANNELS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}

    def __init__(
        self,
        arduino,
        state_path=None,
        state_log_path=None,
        audio=None,
        failure_seconds=15.0,
        victory_seconds=45.0,
        idle_frame_seconds=2.0,
        stop_requested=None,
    ):

        self.arduino = arduino
        self.audio = audio or SilentAudio()
        self.stop_requested = stop_requested or (lambda: False)
        self.failure_seconds = float(failure_seconds)
        self.idle_frame_seconds = float(idle_frame_seconds)
        if not 0.5 <= self.idle_frame_seconds <= 60:
            raise ValueError("IDLE_FRAME_SECONDS must be between 0.5 and 60")
        self.victory_seconds = float(victory_seconds)
        if not 0 <= self.victory_seconds <= 120:
            raise ValueError("VICTORY_SECONDS must be between 0 and 120")
        if not 0 <= self.failure_seconds <= 120:
            raise ValueError("FAILURE_SECONDS must be between 0 and 120")

        self._event_lock = threading.RLock()
        self._stopping = False
        self.state = GameState()
        self._accept_samples_after = float("inf")
        self._hit_latched = set()
        self._last_hit = {}
        self._next_idle_frame = 0.0
        self.persistence_error = None
        log_path = state_log_path or (Path(state_path).with_name('game-events.jsonl') if state_path else None)
        self.state_log = StateLog(log_path)
        self.log_state('SESSION_STARTED_FRESH')

    def log_state(self, event):
        self.state_log.record(event, self.get_state_dict())

    def initialize_hardware(self):
        """Start from base outputs; never load old game or payout state."""
        with self._event_lock:
            self.arduino.send("SENSORS DISABLE")
            self.arduino.send("MOLES ALL DOWN")
            self.arduino.send("LIGHTS OFF")
            self.arduino.send("PLAYER_LIGHTS OFF")
            self.arduino.wait_until_idle()
            self.tick_idle()

    @staticmethod
    def validate_admin_state(payload):
        if not isinstance(payload, dict):
            raise ValueError('state must be an object')
        if 'completed_players' not in payload and 'active_player' not in payload:
            raise ValueError('Provide completed_players or active_player')
        players = payload.get('completed_players', [])
        active = payload.get('active_player')
        progress = payload.get('hit_progress', 0)
        requested = payload.get('ticket_requested', payload.get('ticket_dispensed', False))
        if (not isinstance(players, list) or any(player not in PLAYER_IDS for player in players)
                or len(set(players)) != len(players) or active is not None and active not in PLAYER_IDS
                or active in players or type(progress) is not int or not 0 <= progress <= 4
                or type(requested) is not bool or requested and set(players) != set(PLAYER_IDS)
                or active is None and progress not in (0, 4)):
            raise ValueError('Invalid administrator game state')
        if active is None:
            progress = 0
        if active and progress == 4:
            players = [*players, active]
            active, progress = None, 0
        return {'completed_players': players, 'active_player': active, 'hit_progress': progress,
                'ticket_requested': requested}

    def apply_admin_state(self, payload, hardware=True):
        data = self.validate_admin_state(payload)
        with self._event_lock:
            self.state = GameState(completed_players=set(data['completed_players']), active_player=data['active_player'],
                                   hit_progress=data['hit_progress'], ticket_dispensed=data['ticket_requested'])
            self.state.ticket_status = 'ADMIN RESTORED REQUESTED' if data['ticket_requested'] else 'NOT REQUESTED'
            if self.state.active_player:
                self.assign_colors()
                queen, targets = calculate_whack_order(self.state.bug_colors)
                self.state.queen = queen.name
                self.state.whack_order = [bug.name for bug in targets]
            if hardware:
                self.initialize_hardware()
                for player in sorted(self.state.completed_players):
                    self.arduino.send(f'PLAYER_LIGHT {PLAYER_INDEX[player]} GREEN')
                if self.state.active_player:
                    self.arduino.send(f'PLAYER_LIGHT {PLAYER_INDEX[self.state.active_player]} YELLOW')
                    for name, color in self.state.bug_colors.items():
                        mole = MOLE_ID_BY_NAME[name]
                        if name not in self.state.whack_order[:self.state.hit_progress]:
                            self.arduino.send(f'MOLE {mole} UP')
                            r, g, b = RGB[color]
                            self.arduino.send(f'LIGHT {mole} {r} {g} {b}')
                    self._resume_hit_detection()
                    self.state.locked = False
                    self.state.status = 'PLAYING'
                else:
                    self.state.status = 'GAME COMPLETE' if self.state.completed_players == set(PLAYER_IDS) else 'WAITING FOR BADGE'
                self.arduino.wait_until_idle()
            else:
                self.state.status = 'MAINTENANCE'
            # Restoring progress never triggers ticket payout or a celebration.
            self.log_state('ADMIN_STATE_APPLIED' if hardware else 'ADMIN_STATE_STAGED')

    def tick_idle(self):
        """Animate idle rings and player LEDs without blocking badges or shows."""
        if not self._event_lock.acquire(blocking=False):
            return
        try:
            if (self._stopping or self.stop_requested() or self.persistence_error is not None
                    or self.state.active_player is not None
                    or self.state.status not in ("WAITING FOR BADGE", "GAME COMPLETE")):
                return
            now = time.monotonic()
            if now < self._next_idle_frame:
                return
            commands = getattr(self.arduino, "command_queue", None)
            if commands is not None and commands.unfinished_tasks:
                return
            for mole in range(5):
                rgb = colorsys.hsv_to_rgb((now / 30 + mole / 5) % 1, 1, 1)
                r, g, b = (int(channel * 255) for channel in rgb)
                self.arduino.send(f"LIGHT {mole} {r} {g} {b}", quiet=True)
            # A partially solved session keeps its per-player progress colors.
            # Only a fresh game animates the player strip as one unit.
            if not self.state.completed_players:
                rgb = colorsys.hsv_to_rgb((now / 30) % 1, 1, 1)
                r, g, b = (int(channel * 255) for channel in rgb)
                self.arduino.send(f"PLAYER_LIGHTS {r} {g} {b}", quiet=True)
            self._next_idle_frame = now + self.idle_frame_seconds
        finally:
            self._event_lock.release()


    # ========================================================
    # STARTUP TEST SEQUENCE
    #
    # This does NOT run automatically.
    # app.py decides whether to call it.
    # ========================================================

    def startup_sequence(self):

        print()
        print("==============================")
        print("STARTUP HARDWARE TEST")
        print("==============================")


        self.arduino.send(
            "SENSORS DISABLE"
        )

        self.arduino.send(
            "MOLES ALL DOWN"
        )

        self.arduino.send(
            "LIGHTS OFF"
        )

        self.arduino.send(
            "PLAYER_LIGHTS OFF"
        )


        # Temporary random colors for
        # the hardware startup test.

        startup_colors = list(Color)

        random.shuffle(
            startup_colors
        )


        for mole_id in range(5):

            color = startup_colors[
                mole_id
            ]

            r, g, b = RGB[color]


            self.arduino.send(
                f"LIGHT {mole_id} {r} {g} {b}"
            )


        # Cycle each mole.

        for mole_id in range(5):

            self.arduino.send(
                f"MOLE {mole_id} UP"
            )

            time.sleep(1)


            self.arduino.send(
                f"MOLE {mole_id} DOWN"
            )

            time.sleep(0.5)


        # All up.

        self.arduino.send(
            "MOLES ALL UP"
        )

        time.sleep(2)


        # All down.

        self.arduino.send(
            "MOLES ALL DOWN"
        )

        time.sleep(2)


        self.arduino.send(
            "LIGHTS OFF"
        )

        self.arduino.send(
            "PLAYER_LIGHTS OFF"
        )


        self.state.status = (
            "WAITING FOR BADGE"
        )

        self.state.locked = True


        print()
        print(
            "Startup test complete."
        )

        print(
            "Waiting for badge."
        )


    # ========================================================
    # RFID
    # ========================================================

    def handle_rfid(self, card_id):
        with self._event_lock:
            if not self._stopping and self.persistence_error is None:
                self._handle_rfid(card_id)

    def _handle_rfid(
        self,
        card_id,
    ):

        print()
        print(
            f"RFID: {card_id}"
        )


        # ----------------------------------------------------
        # Unknown badge
        # ----------------------------------------------------

        if (
            card_id not in PLAYER_INDEX
        ):

            print(
                f"Unknown badge: {card_id}"
            )

            return


        # ----------------------------------------------------
        # Completed player
        #
        # GREEN BADGES DO NOTHING.
        # ----------------------------------------------------

        if (
            card_id
            in self.state.completed_players
        ):

            print(
                f"Player {card_id} already completed."
            )

            return


        # ----------------------------------------------------
        # If another unfinished player was active,
        # turn their yellow indicator off.
        #
        # We intentionally allow players to switch.
        # ----------------------------------------------------

        # Replace idle rainbow colors with actual player status before play.
        if self.state.active_player is None:
            for player in PLAYER_IDS:
                color = "GREEN" if player in self.state.completed_players else "OFF"
                self.arduino.send(f"PLAYER_LIGHT {PLAYER_INDEX[player]} {color}")

        previous_player = (
            self.state.active_player
        )


        if (
            previous_player is not None
            and
            previous_player != card_id
            and
            previous_player
            not in self.state.completed_players
        ):

            previous_index = (
                PLAYER_INDEX[
                    previous_player
                ]
            )


            self.arduino.send(
                f"PLAYER_LIGHT "
                f"{previous_index} OFF"
            )


        # ----------------------------------------------------
        # Activate scanned player
        # ----------------------------------------------------

        self.state.active_player = (
            card_id
        )


        player_index = (
            PLAYER_INDEX[
                card_id
            ]
        )


        self.arduino.send(
            f"PLAYER_LIGHT "
            f"{player_index} YELLOW"
        )


        print(
            f"Player {card_id} active."
        )


        # ----------------------------------------------------
        # Start their assigned puzzle
        # ----------------------------------------------------

        self.start_new_round()


    # ========================================================
    # ASSIGN COLORS
    # ========================================================

    def assign_colors(self):

        player_id = (
            self.state.active_player
        )


        if (
            player_id
            not in STATIC_PUZZLES
        ):

            raise ValueError(
                f"No static puzzle defined "
                f"for player {player_id}"
            )


        # ----------------------------------------------------
        # STATIC / SEEDED PUZZLES
        #
        # CURRENTLY ACTIVE
        # ----------------------------------------------------

        self.state.bug_colors = (
            STATIC_PUZZLES[
                player_id
            ].copy()
        )


        # ----------------------------------------------------
        # RANDOM COLOR ASSIGNMENT
        #
        # DISABLED.
        #
        # To return to random puzzles:
        #
        # 1. Comment out the STATIC assignment above.
        # 2. Uncomment this section.
        # ----------------------------------------------------

        # colors = list(Color)
        #
        # random.shuffle(colors)
        #
        # self.state.bug_colors = {
        #     bug.name: colors[index]
        #     for index, bug in enumerate(BUGS)
        # }


    # ========================================================
    # START NEW ROUND
    # ========================================================

    def start_new_round(self):

        if (
            self.state.active_player
            is None
        ):

            print(
                "Cannot start round: "
                "no active player."
            )

            return


        print()
        print("==============================")
        print(
            f"NEW ROUND - "
            f"PLAYER {self.state.active_player}"
        )
        print("==============================")


        # Prevent hits while the new puzzle
        # is being configured.

        self.state.locked = True

        self.state.status = (
            "SETTING UP ROUND"
        )


        self.arduino.send(
            "SENSORS DISABLE"
        )


        # ----------------------------------------------------
        # Assign puzzle colors
        # ----------------------------------------------------

        self.assign_colors()


        # ----------------------------------------------------
        # Calculate solution
        # ----------------------------------------------------

        queen, targets = (
            calculate_whack_order(
                self.state.bug_colors
            )
        )


        self.state.queen = (
            queen.name
        )


        self.state.whack_order = [
            bug.name
            for bug in targets
        ]


        self.state.hit_progress = 0


        # ----------------------------------------------------
        # Validate static puzzle
        # ----------------------------------------------------

        expected = EXPECTED_ORDERS[
            self.state.active_player
        ]


        if (
            self.state.whack_order
            != expected
        ):

            raise RuntimeError(
                "Puzzle validation failed "
                f"for player "
                f"{self.state.active_player}: "
                f"calculated "
                f"{self.state.whack_order}, "
                f"expected {expected}"
            )


        # ----------------------------------------------------
        # Debug output
        # ----------------------------------------------------

        print()
        print("Colors:")


        for bug in BUGS:

            color = (
                self.state.bug_colors[
                    bug.name
                ]
            )

            print(
                f"  {bug.name}: "
                f"{color.value}"
            )


        print()
        print(
            f"Queen: "
            f"{self.state.queen}"
        )


        print(
            "Whack order: "
            +
            " -> ".join(
                self.state.whack_order
            )
        )


        # ----------------------------------------------------
        # Apply puzzle to cabinet
        # ----------------------------------------------------

        self.apply_round_to_hardware()
        self._resume_hit_detection()


        self.state.locked = False

        self.state.status = (
            "PLAYING"
        )
        self.audio.play("game_start")
        self.log_state("ROUND_STARTED")


    # ========================================================
    # APPLY ROUND TO HARDWARE
    # ========================================================

    def apply_round_to_hardware(self):

        # Sensors remain disabled while
        # pneumatics/lights are configured.

        self.arduino.send(
            "SENSORS DISABLE"
        )


        # Raise all five bugs.

        self.arduino.send(
            "MOLES ALL UP"
        )


        # Apply assigned colors.

        for (
            bug_name,
            color
        ) in self.state.bug_colors.items():

            mole_id = (
                MOLE_ID_BY_NAME[
                    bug_name
                ]
            )


            r, g, b = (
                RGB[color]
            )


            self.arduino.send(
                f"LIGHT "
                f"{mole_id} "
                f"{r} "
                f"{g} "
                f"{b}"
            )


        # _resume_hit_detection arms one firmware HIT after setup drains.


    # ========================================================
    # HIT EVENT
    # ========================================================

    def handle_hit(
        self,
        mole_id,
        sensor_channel=None,
        strength=None,
    ):

        if (
            self.state.locked
        ):

            return


        if (
            self.state.active_player
            is None
        ):

            return


        if (
            mole_id
            not in MOLE_BY_ID
        ):

            print(
                f"Unknown mole ID: "
                f"{mole_id}"
            )

            return


        bug_name = (
            MOLE_BY_ID[
                mole_id
            ]
        )


        print()
        print(
            f"HIT: {bug_name}"
        )


        if (
            sensor_channel
            is not None
        ):

            print(
                f"Sensor channel: "
                f"{sensor_channel}"
            )


        if (
            strength
            is not None
        ):

            print(
                f"Strength: "
                f"{strength}"
            )


        # ----------------------------------------------------
        # Determine expected bug
        # ----------------------------------------------------

        if (
            self.state.hit_progress
            >= len(
                self.state.whack_order
            )
        ):

            return


        self.audio.play("mole_hit")

        expected_bug = (
            self.state.whack_order[
                self.state.hit_progress
            ]
        )


        print(
            f"Expected: "
            f"{expected_bug}"
        )


        # ----------------------------------------------------
        # Correct
        # ----------------------------------------------------

        if (
            bug_name
            == expected_bug
        ):

            self.handle_correct_hit(
                mole_id,
                bug_name,
            )


        # ----------------------------------------------------
        # Wrong
        # ----------------------------------------------------

        else:

            self.handle_wrong_hit(
                bug_name,
                expected_bug,
            )


    # ========================================================
    # CORRECT HIT
    # ========================================================

    def handle_correct_hit(
        self,
        mole_id,
        bug_name,
    ):

        print(
            f"CORRECT: {bug_name}"
        )


        # Lock while hardware moves.

        self.state.locked = True
        self._accept_samples_after = float("inf")


        self.arduino.send(
            "SENSORS DISABLE"
        )


        # Lower only the bug that was hit.

        self.arduino.send(
            f"MOLE {mole_id} DOWN"
        )


        # Turn its light off.

        self.arduino.send(
            f"LIGHT {mole_id} OFF"
        )


        # Advance progress.

        self.state.hit_progress += 1
        self.log_state("HIT_CORRECT")


        print(
            f"Progress: "
            f"{self.state.hit_progress}"
            f"/"
            f"{len(self.state.whack_order)}"
        )


        # ----------------------------------------------------
        # Puzzle completed
        # ----------------------------------------------------

        if (
            self.state.hit_progress
            >= len(
                self.state.whack_order
            )
        ):

            self.complete_player()

            return


        # ----------------------------------------------------
        # Continue puzzle
        # ----------------------------------------------------

        self._resume_hit_detection()
        self.state.locked = False
        self.state.status = "PLAYING"


    # ========================================================
    # WRONG HIT
    # ========================================================

    def handle_wrong_hit(
        self,
        bug_name,
        expected_bug,
    ):

        print()
        print(
            f"WRONG: {bug_name}"
        )

        print(
            f"Expected: {expected_bug}"
        )


        self.state.locked = True

        self.state.status = (
            "WRONG - RESETTING"
        )
        self.log_state("HIT_WRONG")


        # ----------------------------------------------------
        # Kill playfield
        # ----------------------------------------------------

        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL DOWN"
        )


        self.arduino.send(
            "LIGHTS OFF"
        )


        # Same player stays active/yellow.
        self.run_failure_show()
        if self.stop_requested():
            return


        # ----------------------------------------------------
        # Restart SAME player's puzzle.
        #
        # Because puzzles are static, this restores
        # the exact same puzzle and resets progress.
        # ----------------------------------------------------

        self.start_new_round()


    def _failure_strike(self, line, received_at, raised, raised_at, latched, last_hit, pending, deadline, victory=False):
        parts = line.split()
        try:
            if len(parts) == 6 and parts[0] == "ACCEL":
                mole, channel, x, y, z = map(int, parts[1:])
                if any(value < -32768 or value > 32767 for value in (x, y, z)):
                    return
                if z > self.HIT_RELEASE_Z:
                    if received_at >= raised_at.get(mole, float("inf")):
                        latched.discard(mole)
                    return
                if z > self.HIT_Z_THRESHOLD:
                    return
            elif len(parts) == 4 and parts[0] == "HIT":
                mole, channel, strength = map(int, parts[1:])
                z = None
            else:
                return
        except ValueError:
            return
        if (mole not in raised or self.SENSOR_CHANNELS.get(mole) != channel
                or received_at < raised_at[mole]
                or (z is not None and mole in latched)
                or received_at - last_hit.get(mole, float("-inf")) < self.HIT_COOLDOWN):
            return
        latched.add(mole)
        last_hit[mole] = received_at
        # Mark down first so retraction vibration cannot cause another strike.
        raised.remove(mole)
        self.arduino.send(f"MOLE {mole} DOWN")
        self.arduino.send(f"LIGHT {mole} OFF")
        # Cut laughter and play the reaction before any replacement rises.
        reaction = self.audio.play_victory_hit if victory else self.audio.play_failure_hit
        delay = reaction(max(0, deadline - time.monotonic()))
        ready_at = time.monotonic() + delay
        candidates = [candidate for candidate in range(5)
                      if candidate not in raised and candidate not in pending and candidate != mole]
        if candidates:
            pending[random.choice(candidates)] = ready_at
        # Another strike cuts the previous reaction too; defer all replacements
        # until this latest reaction is finished.
        for replacement in pending:
            pending[replacement] = ready_at

    def run_failure_show(self):
        self._run_show(self.failure_seconds)

    def run_victory_show(self):
        self._run_show(self.victory_seconds, victory=True,
                       on_start=lambda: self.arduino.send("TICKET 7"))

    def _run_show(self, seconds, victory=False, on_start=None):
        self.state.status = "VICTORY CELEBRATION" if victory else "LAUGH AT YOU"
        self.log_state("SHOW_STARTED")
        self._accept_samples_after = float("inf")
        self.arduino.wait_until_idle()
        if self.stop_requested():
            return
        if seconds <= 0:
            if on_start is not None:
                on_start()
            return
        if victory:
            self.audio.play_victory(seconds)
        else:
            self.audio.play_failure(seconds)
        deadline = time.monotonic() + seconds
        next_motion = time.monotonic()
        motion_interval = 0.5 if victory else 1.0
        next_rainbow = next_motion
        raised, raised_at, latched, last_hit = set(), {}, set(), {}
        pending = {}
        self.arduino.begin_sensor_capture()
        try:
            self.arduino.send("SENSORS ENABLE")
            self.arduino.wait_until_idle()
            if on_start is not None:
                on_start()
            # Poll strikes at 50 Hz; random motion/light changes remain at 2 Hz.
            for _ in range(math.ceil(seconds / 0.02) + 1):
                now = time.monotonic()
                if now >= deadline or self.stop_requested():
                    break
                for line, received_at in self.arduino.read_captured_samples():
                    if line.startswith("TICKET_"):
                        self._handle_ticket_event(line)
                    else:
                        self._failure_strike(line, received_at, raised, raised_at, latched,
                                             last_hit, pending, deadline, victory=victory)
                ready = [mole for mole, ready_at in pending.items() if now >= ready_at]
                for mole in ready:
                    pending.pop(mole)
                    raised.add(mole)
                    raised_at[mole] = time.monotonic()
                    self.arduino.send(f"MOLE {mole} UP")
                    r, g, b = random.choice(tuple(RGB.values())) if victory else (255, 0, 0)
                    self.arduino.send(f"LIGHT {mole} {r} {g} {b}")
                if ready:
                    next_motion = now + motion_interval
                if now >= next_motion and not pending:
                    selected = set(random.sample(range(5), random.randint(1, 3 if victory else 2)))
                    for mole in sorted(raised - selected):
                        self.arduino.send(f"MOLE {mole} DOWN")
                        if not victory:
                            self.arduino.send(f"LIGHT {mole} OFF")
                    for mole in sorted(selected - raised):
                        raised_at[mole] = time.monotonic()
                        self.arduino.send(f"MOLE {mole} UP")
                    raised = selected
                    if not victory:
                        for mole in sorted(raised):
                            self.arduino.send(f"LIGHT {mole} 255 0 0")
                    next_motion = now + motion_interval
                if victory and now >= next_rainbow:
                    for mole in range(5):
                        rgb = colorsys.hsv_to_rgb((now / 3 + mole / 5) % 1, 1, 1)
                        r, g, b = (int(channel * 255) for channel in rgb)
                        self.arduino.send(f"LIGHT {mole} {r} {g} {b}", quiet=True)
                    for player in range(6):
                        rgb = colorsys.hsv_to_rgb((now / 3 + player / 6) % 1, 1, 1)
                        r, g, b = (int(channel * 255) for channel in rgb)
                        self.arduino.send(f"PLAYER_LIGHT {player} {r} {g} {b}", quiet=True)
                    next_rainbow = now + 0.5
                self.arduino.wait_until_idle()
                time.sleep(max(0, min(0.02, deadline - time.monotonic())))
        finally:
            self.arduino.send("SENSORS DISABLE")
            self.arduino.send("MOLES ALL DOWN")
            self.arduino.send("LIGHTS OFF")
            try:
                self.arduino.wait_until_idle()
            finally:
                self.arduino.end_sensor_capture()
                self.audio.stop_show()
                if victory:
                    for player in PLAYER_IDS:
                        self.arduino.send(f"PLAYER_LIGHT {PLAYER_INDEX[player]} GREEN")

    # ========================================================
    # PLAYER COMPLETE
    # ========================================================

    def complete_player(self):

        player_id = (
            self.state.active_player
        )


        if (
            player_id is None
        ):
            return


        print()
        print("==============================")
        print(
            f"PLAYER {player_id} COMPLETE"
        )
        print("==============================")


        self.state.completed_players.add(
            player_id
        )


        player_index = (
            PLAYER_INDEX[
                player_id
            ]
        )


        # ----------------------------------------------------
        # Player indicator GREEN
        # ----------------------------------------------------

        self.arduino.send(
            f"PLAYER_LIGHT "
            f"{player_index} GREEN"
        )


        # ----------------------------------------------------
        # Shut down playfield
        # ----------------------------------------------------

        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL DOWN"
        )


        self.arduino.send(
            "LIGHTS OFF"
        )


        self.state.locked = True


        # ----------------------------------------------------
        # Release active player.
        #
        # Completed badge is now green and future
        # scans of it are ignored.
        # ----------------------------------------------------

        self.state.active_player = None


        # ----------------------------------------------------
        # Check full-game completion
        # ----------------------------------------------------

        if (
            len(
                self.state.completed_players
            )
            >= len(PLAYER_IDS)
        ):

            self.log_state("PLAYER_COMPLETED")
            self.complete_full_game()
            return

        else:

            self.state.status = (
                "WAITING FOR BADGE"
            )


            print()
            print(
                "Waiting for next player."
            )


    # ========================================================
    # ALL SIX PLAYERS COMPLETE
    # ========================================================

        self.log_state("PLAYER_COMPLETED")

    def complete_full_game(self):
        if self.state.completed_players != set(PLAYER_IDS):
            return

        print()
        print("==============================")
        print("ALL PLAYERS COMPLETE")
        print("==============================")


        self.state.locked = True

        self.state.status = (
            "GAME COMPLETE"
        )


        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL DOWN"
        )


        self.arduino.send(
            "LIGHTS OFF"
        )


        # Make absolutely sure all six
        # player indicators are green.

        for player_id in PLAYER_IDS:

            player_index = (
                PLAYER_INDEX[
                    player_id
                ]
            )


            self.arduino.send(
                f"PLAYER_LIGHT "
                f"{player_index} GREEN"
            )


        # ----------------------------------------------------
        # Ticket payout exactly once
        # ----------------------------------------------------

        if (
            not self.state.ticket_dispensed
        ):

            # Payout intent is in-memory for this session; log it before issuing payout.
            self.state.ticket_dispensed = True
            self.log_state('TICKET_REQUESTED')
            self.state.ticket_status = "REQUESTED"
            self.run_victory_show()
            self.state.status = "GAME COMPLETE"
            self.log_state("GAME_COMPLETE")
            if self._stopping or self.stop_requested():
                return
            self.arduino.send("SAFE STOP")
            self.arduino.wait_until_idle()
            self.state = GameState()
            self._next_idle_frame = 0.0
            self.initialize_hardware()
            self.log_state("VICTORY_RESET_TO_IDLE")


    # ========================================================
    # RETRACT GAME
    # ========================================================

    def retract_game(self):
        with self._event_lock:
            self._stopping = True
            self._retract_game()

    def _retract_game(self):

        self.state.locked = True


        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL DOWN"
        )


        self.arduino.send(
            "LIGHTS OFF"
        )


    def _resume_hit_detection(self):
        # ACKs are read on a separate thread, so waiting here is safe.
        self.arduino.wait_until_idle()
        # Capture the cutoff before arming, so a strike received immediately
        # after the ACK isn't dropped once firmware has consumed its one hit.
        self._accept_samples_after = time.monotonic()
        self.arduino.send("SENSORS PUZZLE")
        self.arduino.wait_until_idle()

    def handle_accel(self, mole_id, sensor_channel, x, y, z, received_at=None):
        sample_time = time.monotonic() if received_at is None else received_at
        if self.SENSOR_CHANNELS.get(mole_id) != sensor_channel:
            return
        if any(value < -32768 or value > 32767 for value in (x, y, z)):
            return
        if (self.state.locked or self.state.active_player is None
                or sample_time <= self._accept_samples_after):
            return

        # Completed targets are down. Their retraction vibration is irrelevant.
        bug_name = MOLE_BY_ID[mole_id]
        if bug_name in self.state.whack_order[:self.state.hit_progress]:
            return

        if z > self.HIT_RELEASE_Z:
            self._hit_latched.discard(mole_id)
            return
        if z > self.HIT_Z_THRESHOLD or mole_id in self._hit_latched:
            return
        if sample_time - self._last_hit.get(mole_id, float("-inf")) < self.HIT_COOLDOWN:
            return

        self._hit_latched.add(mole_id)
        self._last_hit[mole_id] = sample_time
        print(f"ACCEL HIT: mole={mole_id} channel={sensor_channel} X={x} Y={y} Z={z}")
        self.handle_hit(mole_id, sensor_channel, -z)

    # ========================================================
    # ARDUINO EVENT HANDLER
    # ========================================================

    def _handle_ticket_event(self, line):
        parts = line.split()
        try:
            if len(parts) == 2 and parts[0] == "TICKET_START" and int(parts[1]) == 7:
                self.state.ticket_status = "DISPENSING"
            elif len(parts) == 2 and parts[0] in ("TICKET_COUNT", "TICKET_DONE"):
                count = int(parts[1])
                if not 0 <= count <= 7:
                    return
                self.state.tickets_dispensed = count
                self.state.ticket_status = ("DONE" if count == 7 else "ERROR") if parts[0] == "TICKET_DONE" else "DISPENSING"
            elif len(parts) == 3 and parts[:2] == ["TICKET_ERROR", "TIMEOUT"]:
                self.state.tickets_dispensed = max(0, min(7, int(parts[2])))
                self.state.ticket_status = "ERROR"
        except ValueError:
            return

        if line.startswith("TICKET_"):
            self.log_state("TICKET_PROGRESS")

    def handle_arduino_event(self, line, received_at=None):
        with self._event_lock:
            if not self._stopping and self.persistence_error is None:
                self._handle_arduino_event(line, received_at)

    def _handle_arduino_event(
        self,
        line,
        received_at=None,
    ):

        if line.startswith("TICKET_"):
            self._handle_ticket_event(line)
            return
        parts = line.split()


        if (
            not parts
        ):
            return


        # ----------------------------------------------------
        # RFID
        #
        # ONLY:
        #
        # RFID 001
        #
        # through:
        #
        # RFID 006
        #
        # Diagnostic RFID_DIAG lines are ignored.
        # ----------------------------------------------------

        if (
            parts[0] == "RFID"
            and
            len(parts) == 2
            and
            parts[1] in PLAYER_IDS
        ):

            self.handle_rfid(
                parts[1]
            )

            return


        if parts[0] == "ACCEL":
            if len(parts) != 6:
                return
            try:
                values = [int(value) for value in parts[1:]]
            except ValueError:
                return
            self.handle_accel(*values, received_at=received_at)
            return

        # ----------------------------------------------------
        # HIT
        #
        # HIT <mole> <sensor channel> <strength>
        # ----------------------------------------------------

        if (
            parts[0] == "HIT"
            and
            len(parts) >= 4
        ):
            if received_at is not None and received_at <= self._accept_samples_after:
                return

            try:

                mole_id = int(
                    parts[1]
                )

                sensor_channel = int(
                    parts[2]
                )

                strength = int(
                    parts[3]
                )

            except ValueError:

                print(
                    f"Bad HIT event: {line}"
                )

                return


            if self.SENSOR_CHANNELS.get(mole_id) != sensor_channel or strength < abs(self.HIT_Z_THRESHOLD):
                return
            self.handle_hit(
                mole_id,
                sensor_channel,
                strength,
            )

            return


    # ========================================================
    # PRINT STATE
    # ========================================================

    def print_state(self):

        print()
        print("==============================")
        print("GAME STATE")
        print("==============================")


        print(
            f"Active player: "
            f"{self.state.active_player}"
        )


        print(
            f"Completed: "
            f"{sorted(self.state.completed_players)}"
        )


        print(
            f"Queen: "
            f"{self.state.queen}"
        )


        print(
            f"Whack order: "
            f"{self.state.whack_order}"
        )


        print(
            f"Progress: "
            f"{self.state.hit_progress}"
        )


        print(
            f"Locked: "
            f"{self.state.locked}"
        )


        print(
            f"Status: "
            f"{self.state.status}"
        )


    # ========================================================
    # STATUS SERVICE
    # ========================================================

    def get_state_dict(self):

        solution_order = [
            self.state.bug_colors[
                bug_name
            ].value
            for bug_name
            in self.state.whack_order
            if bug_name
            in self.state.bug_colors
        ]


        return {

            "solve_state": {
                "fully_solved": self.state.completed_players == set(PLAYER_IDS),
                "completed_count": len(self.state.completed_players),
                "total_players": len(PLAYER_IDS),
                "players": {player: ("SOLVED" if player in self.state.completed_players
                                      else "ACTIVE" if player == self.state.active_player else "PENDING")
                            for player in PLAYER_IDS},
                "current_steps_completed": self.state.hit_progress,
                "current_steps_total": len(self.state.whack_order),
                "next_expected_mole": (self.state.whack_order[self.state.hit_progress]
                                       if self.state.active_player and self.state.hit_progress < len(self.state.whack_order)
                                       else None),
                "ticket_requested": self.state.ticket_dispensed,
                "physical_payout_confirmed": self.state.ticket_status == "DONE",
            },
            "active_player":
                self.state.active_player,

            "completed_players":
                sorted(
                    self.state.completed_players
                ),

            "bug_colors": {
                bug_name: color.value
                for (
                    bug_name,
                    color
                )
                in self.state.bug_colors.items()
            },

            "queen":
                self.state.queen,

            "whack_order":
                self.state.whack_order,

            "solution_order":
                solution_order,

            "hit_progress":
                self.state.hit_progress,

            "locked":
                self.state.locked,

            "status":
                self.state.status,

            "ticket_dispensed":
                self.state.ticket_dispensed,
            "ticket_status": self.state.ticket_status,
            "tickets_dispensed": self.state.tickets_dispensed,
        }
