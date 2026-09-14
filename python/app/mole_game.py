import random
import time

from dataclasses import dataclass, field

from bugs import BUGS, Color
from game import calculate_whack_order


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
# 0 = Back left
# 1 = Back right
# 2 = Front left
# 3 = Front center
# 4 = Front right
# ============================================================

MOLE_BY_ID = {
    0: "FRASIER",
    1: "NILES",
    2: "MARTIN",
    3: "DAPHNE",
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


# ============================================================
# GAME
# ============================================================

class MoleGame:

    def __init__(
        self,
        arduino,
    ):

        self.arduino = arduino

        self.state = GameState()


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

    def handle_rfid(
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


        self.state.locked = False

        self.state.status = (
            "PLAYING"
        )


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


        # Arduino also has its mechanical
        # settle timer before hits are accepted.

        self.arduino.send(
            "SENSORS ENABLE"
        )


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

        self.state.locked = False

        self.state.status = (
            "PLAYING"
        )


        self.arduino.send(
            "SENSORS ENABLE"
        )


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

        time.sleep(1)


        # ----------------------------------------------------
        # Restart SAME player's puzzle.
        #
        # Because puzzles are static, this restores
        # the exact same puzzle and resets progress.
        # ----------------------------------------------------

        self.start_new_round()


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

            self.complete_full_game()

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

    def complete_full_game(self):

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

            self.arduino.send(
                "TICKET 1"
            )


            self.state.ticket_dispensed = (
                True
            )


    # ========================================================
    # RETRACT GAME
    # ========================================================

    def retract_game(self):

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


    # ========================================================
    # ARDUINO EVENT HANDLER
    # ========================================================

    def handle_arduino_event(
        self,
        line,
    ):

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
        }