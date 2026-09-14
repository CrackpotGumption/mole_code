from dataclasses import dataclass
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class Antennae(str, Enum):
    NONE = "none"
    PLAIN = "plain"
    KNOBBED = "knobbed"


class Marks(str, Enum):
    NONE = "none"
    SPOTS = "spots"
    STRIPES = "stripes"


class Wings(str, Enum):
    NONE = "none"
    TWO = "two"
    FOUR = "four"


class Mouth(str, Enum):
    CHEWING = "chewing"
    STRAW = "straw"


class Body(str, Enum):
    THREEPIECE = "threepiece"
    FUSED = "fused"


class Color(str, Enum):
    WHITE = "white"
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"


# ============================================================
# BUG DATA MODEL
# ============================================================

@dataclass(frozen=True)
class Bug:
    name: str
    antennae: Antennae
    marks: Marks
    legs: int
    tail: bool
    wings: Wings
    mouth: Mouth
    body: Body


# ============================================================
# SPECIMENS
# ============================================================

FRASIER = Bug(
    name="FRASIER",
    antennae=Antennae.KNOBBED,
    marks=Marks.STRIPES,
    legs=6,
    tail=False,
    wings=Wings.TWO,
    mouth=Mouth.CHEWING,
    body=Body.THREEPIECE,
)


NILES = Bug(
    name="NILES",
    antennae=Antennae.KNOBBED,
    marks=Marks.STRIPES,
    legs=6,
    tail=False,
    wings=Wings.TWO,
    mouth=Mouth.STRAW,
    body=Body.THREEPIECE,
)


MARTIN = Bug(
    name="MARTIN",
    antennae=Antennae.PLAIN,
    marks=Marks.NONE,
    legs=4,
    tail=True,
    wings=Wings.NONE,
    mouth=Mouth.CHEWING,
    body=Body.FUSED,
)


DAPHNE = Bug(
    name="DAPHNE",
    antennae=Antennae.PLAIN,
    marks=Marks.SPOTS,
    legs=8,
    tail=True,
    wings=Wings.FOUR,
    mouth=Mouth.STRAW,
    body=Body.FUSED,
)


ROZ = Bug(
    name="ROZ",
    antennae=Antennae.NONE,
    marks=Marks.SPOTS,
    legs=8,
    tail=False,
    wings=Wings.TWO,
    mouth=Mouth.CHEWING,
    body=Body.FUSED,
)


# ============================================================
# COLLECTIONS
# ============================================================

BUGS = (
    FRASIER,
    NILES,
    MARTIN,
    DAPHNE,
    ROZ,
)


BUG_BY_NAME = {
    bug.name: bug
    for bug in BUGS
}


# ============================================================
# DOCTRINE
#
# Queen leg count determines which traits count toward kinship.
# ============================================================

DOCTRINE = {

    4: (
        "antennae",
        "marks",
        "tail",
        "wings",
    ),

    6: (
        "marks",
        "legs",
        "wings",
        "mouth",
        "body",
    ),

    8: (
        "antennae",
        "marks",
        "legs",
        "tail",
        "wings",
        "mouth",
        "body",
    ),
}


# ============================================================
# SPECTRUM
#
# Higher number = stronger color.
# ============================================================

SPECTRUM = {
    Color.WHITE: 7,
    Color.RED: 6,
    Color.ORANGE: 5,
    Color.YELLOW: 4,
    Color.GREEN: 3,
    Color.BLUE: 2,
    Color.PURPLE: 1,
}