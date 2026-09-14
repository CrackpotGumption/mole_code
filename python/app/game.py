from .bugs import (
    BUGS,
    DOCTRINE,
    SPECTRUM,
)


# ============================================================
# FIND QUEEN
#
# The bug with the strongest Spectrum color is the Queen.
# Higher SPECTRUM value = stronger color.
# ============================================================

def find_queen(
    bug_colors,
):

    return max(
        BUGS,
        key=lambda bug: (
            SPECTRUM[
                bug_colors[
                    bug.name
                ]
            ]
        ),
    )


# ============================================================
# KINSHIP SCORE
#
# Queen's number of legs selects the Doctrine.
#
# Each matching Doctrine trait is worth 1 point.
# Higher score = closer kinship.
# ============================================================

def kinship_score(
    bug,
    queen,
):

    traits = DOCTRINE[
        queen.legs
    ]


    score = 0


    for trait in traits:

        bug_value = getattr(
            bug,
            trait,
        )

        queen_value = getattr(
            queen,
            trait,
        )


        if (
            bug_value
            == queen_value
        ):

            score += 1


    return score


# ============================================================
# CALCULATE WHACK ORDER
#
# Primary sort:
#     Highest kinship first.
#
# Tie breaker:
#     Strongest Spectrum color first.
#
# Queen is never included in the targets.
# ============================================================

def calculate_whack_order(
    bug_colors,
):

    queen = find_queen(
        bug_colors
    )


    targets = [
        bug
        for bug in BUGS
        if bug != queen
    ]


    targets.sort(
        key=lambda bug: (
            kinship_score(
                bug,
                queen,
            ),

            SPECTRUM[
                bug_colors[
                    bug.name
                ]
            ],
        ),

        reverse=True,
    )


    return (
        queen,
        targets,
    )