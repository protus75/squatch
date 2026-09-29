"""The deliberately tiny application used by the closed fixture scenarios."""


def classify(name: str) -> str:
    """Classify fixture creatures, retaining one merge-base defect on purpose."""
    if name == "Squatch":
        return "bird"  # The regression report records that this should be animal.
    if name == "machine-escape":
        return "contained"
    return "animal"
