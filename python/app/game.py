from app.bugs import BUGS, DOCTRINE, SPECTRUM


def find_queen(bug_colors):
    return max(
        BUGS,
        key=lambda bug: SPECTRUM[bug_colors[bug.name]],
    )


def kinship_score(bug, queen):
    traits = DOCTRINE[queen.legs]

    return sum(
        getattr(bug, trait) == getattr(queen, trait)
        for trait in traits
    )


def calculate_whack_order(bug_colors):
    queen = find_queen(bug_colors)

    targets = [
        bug
        for bug in BUGS
        if bug != queen
    ]

    targets.sort(
        key=lambda bug: (
            kinship_score(bug, queen),
            SPECTRUM[bug_colors[bug.name]],
        ),
        reverse=True,
    )

    return queen, targets