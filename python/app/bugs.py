from dataclasses import dataclass
from enum import Enum


# ============================================================
# Trait values
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
# Bug definition
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
# Doctrine
#
# The QUEEN'S leg count determines which traits are used
# when calculating kinship.
# ============================================================

DOCTRINE: dict[int, tuple[str, ...]] = {
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
# Spectrum
#
# Higher number = stronger color = higher royal precedence.
# ============================================================

SPECTRUM: dict[Color, int] = {
    Color.WHITE: 7,
    Color.RED: 6,
    Color.ORANGE: 5,
    Color.YELLOW: 4,
    Color.GREEN: 3,
    Color.BLUE: 2,
    Color.PURPLE: 1,
}


# ============================================================
# Specimens
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
    mouth=Mouth.CHEWING,
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
    wings=Wings.NONE,
    mouth=Mouth.CHEWING,
    body=Body.FUSED,
)


BUGS: tuple[Bug, ...] = (
    FRASIER,
    NILES,
    MARTIN,
    DAPHNE,
    ROZ,
)

BUG_BY_NAME: dict[str, Bug] = {
    bug.name: bug
    for bug in BUGS
}