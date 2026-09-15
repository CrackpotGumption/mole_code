import random
import time

from dataclasses import dataclass, field

from .bugs import BUGS, Color
from .game import calculate_whack_order


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
# ============================================================

STATIC_PUZZLES = {

    # Round 1
    "001": {
        "FRASIER": Color.WHITE,
        "NILES": Color.YELLOW,
        "MARTIN": Color.RED,
        "DAPHNE": Color.GREEN,
        "ROZ": Color.BLUE,
    },

    # Round 2
    "002": {
        "FRASIER": Color.BLUE,
        "NILES": Color.PURPLE,
        "MARTIN": Color.ORANGE,
        "DAPHNE": Color.WHITE,
        "ROZ": Color.GREEN,
    },

    # Round 3
    "003": {
        "FRASIER": Color.GREEN,
        "NILES": Color.RED,
        "MARTIN": Color.BLUE,
        "DAPHNE": Color.YELLOW,
        "ROZ": Color.PURPLE,
    },

    # Round 4
    "004": {
        "FRASIER": Color.PURPLE,
        "NILES": Color.ORANGE,
        "MARTIN": Color.RED,
        "DAPHNE": Color.BLUE,
        "ROZ": Color.GREEN,
    },

    # Round 5
    "005": {
        "FRASIER": Color.YELLOW,
        "NILES": Color.BLUE,
        "MARTIN": Color.PURPLE,
        "DAPHNE": Color.GREEN,
        "ROZ": Color.ORANGE,
    },

    # Round 6
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

        # RFID cards are queued here when the Arduino emits:
        #
        # RFID 001
        #
        # We do NOT act on the card until the Arduino later emits:
        #
        # RFID_DIAG READY_FOR_NEXT_CARD
        #
        # This prevents Python from blasting commands at the Mega
        # while it is still finishing its RFID transaction.

        self.pending_rfid = None


    # ========================================================
    # STARTUP TEST SEQUENCE
    #
    # Intentionally NOT automatic.
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


        for mole_id in range(5):

            self.arduino.send(
                f"MOLE {mole_id} UP"
            )

            time.sleep(1)

            self.arduino.send(
                f"MOLE {mole_id} DOWN"
            )

            time.sleep(0.5)


        self.arduino.send(
            "MOLES ALL UP"
        )

        time.sleep(2)


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
        # Completed badge does nothing.
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
        # If switching from another unfinished player,
        # turn the old yellow player light off.
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
        # Activate new player
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
        # STATIC PUZZLES
        #
        # CURRENTLY ACTIVE
        # ----------------------------------------------------

        self.state.bug_colors = (
            STATIC_PUZZLES[
                player_id
            ].copy()
        )


        # ----------------------------------------------------
        # RANDOM PUZZLES
        #
        # DISABLED
        #
        # To return to random puzzles:
        #
        # Comment out the STATIC assignment above,
        # then uncomment this block.
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


        self.state.locked = True

        self.state.status = (
            "SETTING UP ROUND"
        )


        self.arduino.send(
            "SENSORS DISABLE"
        )


        # ----------------------------------------------------
        # Load colors
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
        # Validate known solution
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
        # Apply puzzle to hardware
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

        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL UP"
        )


        for (
            bug_name,
            color
        ) in self.state.bug_colors.items():

            mole_id = (
                MOLE_ID_BY_NAME[
                    bug_name
                ]
            )


            r, g, b = RGB[
                color
            ]


            self.arduino.send(
                f"LIGHT "
                f"{mole_id} "
                f"{r} "
                f"{g} "
                f"{b}"
            )


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


        if (
            bug_name
            == expected_bug
        ):

            self.handle_correct_hit(
                mole_id,
                bug_name,
            )


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


        self.state.locked = True


        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            f"MOLE {mole_id} DOWN"
        )


        self.arduino.send(
            f"LIGHT {mole_id} OFF"
        )


        self.state.hit_progress += 1


        print(
            f"Progress: "
            f"{self.state.hit_progress}"
            f"/"
            f"{len(self.state.whack_order)}"
        )


        if (
            self.state.hit_progress
            >= len(
                self.state.whack_order
            )
        ):

            self.complete_player()

            return


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


        self.arduino.send(
            "SENSORS DISABLE"
        )


        self.arduino.send(
            "MOLES ALL DOWN"
        )


        self.arduino.send(
            "LIGHTS OFF"
        )


        time.sleep(1)


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


        self.arduino.send(
            f"PLAYER_LIGHT "
            f"{player_index} GREEN"
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


        self.state.locked = True


        self.state.active_player = None


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
    # ALL SIX COMPLETE
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


        if (
            not self.state.ticket_dispensed
        ):

            self.arduino.send(
                "TICKET 8"
            )


            self.state.ticket_dispensed = (
                True
            )


        # Leave the completed-game display up long enough for the
        # ticket payout / celebration to be seen, then automatically
        # return the cabinet to its initial waiting state.
        #
        # This runs on the event-worker thread, not the serial-reader
        # thread, so ACKs can continue to be received normally.
        self.arduino.wait_until_idle()

        print(
            "Game complete. Resetting in 25 seconds..."
        )

        time.sleep(25)


        # ----------------------------------------------------
        # END-OF-GAME RESET WARNING
        #
        # Blink all five mole lights and all six player lights
        # three times before clearing the game.
        # ----------------------------------------------------

        for _ in range(3):

            for mole_id in range(5):

                self.arduino.send(
                    f"LIGHT {mole_id} 255 255 255"
                )

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

            self.arduino.wait_until_idle()

            time.sleep(0.4)

            self.arduino.send(
                "LIGHTS OFF"
            )

            self.arduino.send(
                "PLAYER_LIGHTS OFF"
            )

            self.arduino.wait_until_idle()

            time.sleep(0.4)


        # ----------------------------------------------------
        # STATE 0
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

        self.arduino.send(
            "PLAYER_LIGHTS OFF"
        )

        self.arduino.wait_until_idle()


        self.state = GameState()

        self.pending_rfid = None


        print()
        print("==============================")
        print("GAME RESET - STATE 0")
        print("==============================")


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
        # RFID CARD EVENT
        #
        # Arduino sends:
        #
        # RFID 001
        #
        # But we do NOT handle it immediately.
        #
        # We queue it and wait for:
        #
        # RFID_DIAG READY_FOR_NEXT_CARD
        #
        # This prevents command traffic from colliding with
        # the tail end of the RFID transaction.
        # ----------------------------------------------------

        if (
            parts[0] == "RFID"
            and
            len(parts) == 2
            and
            parts[1] in PLAYER_IDS
        ):

            self.pending_rfid = (
                parts[1]
            )


            print(
                f"RFID queued: "
                f"{self.pending_rfid}"
            )


            return


        # ----------------------------------------------------
        # RFID READER FINISHED
        #
        # Now it is safe to respond to the card.
        # ----------------------------------------------------

        if (
            line
            == "RFID_DIAG READY_FOR_NEXT_CARD"
        ):

            if (
                self.pending_rfid
                is not None
            ):

                card_id = (
                    self.pending_rfid
                )


                self.pending_rfid = None


                self.handle_rfid(
                    card_id
                )


            return


        # ----------------------------------------------------
        # HIT
        #
        # HIT <mole> <sensor_channel> <strength>
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