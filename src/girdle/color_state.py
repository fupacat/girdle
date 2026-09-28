"""Display badge color state based on passed checks and difficulty bands.

- **neutral** – default; no applicable checks or no badge tier earned yet.
  Never a warning color for mere incompleteness.
- **bronze / silver / gold** – tiers earned by passing every check in the
  corresponding difficulty bands: BASIC, BASIC + INTERMEDIATE, or all
  non-reserved checks, respectively.
- **red** – reserved exclusively for active-harm findings (committed
  secrets, poisoned agent instructions).  It overrides the badge scale.
"""

from __future__ import annotations

from enum import Enum

from girdle.checks import CheckEntry, Difficulty


class DisplayState(str, Enum):
    NEUTRAL = "neutral"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    RED = "red"


def badge_state(
    results: dict[CheckEntry, bool], *, active_harm: bool = False
) -> DisplayState:
    """Return the badge state earned by passed checks and their difficulty.

    Reserved checks do not contribute to badge tiers. A tier is earned only
    when every non-reserved check in its difficulty band has passed.
    """
    if active_harm:
        return DisplayState.RED
    live = {entry: passed for entry, passed in results.items() if not entry.reserved}

    def band_ok(levels: tuple[Difficulty, ...]) -> bool:
        band = [passed for entry, passed in live.items() if entry.difficulty in levels]
        return bool(band) and all(band)

    if not live or not any(live.values()):
        return DisplayState.NEUTRAL
    if all(live.values()):
        return DisplayState.GOLD
    if band_ok((Difficulty.BASIC, Difficulty.INTERMEDIATE)):
        return DisplayState.SILVER
    if band_ok((Difficulty.BASIC,)):
        return DisplayState.BRONZE
    return DisplayState.NEUTRAL


__all__ = ["DisplayState", "badge_state"]
