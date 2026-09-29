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

    if not live or not any(live.values()):
        return DisplayState.NEUTRAL
    earned = DisplayState.NEUTRAL
    tiers = ((Difficulty.BASIC, DisplayState.BRONZE),
             (Difficulty.INTERMEDIATE, DisplayState.SILVER),
             (Difficulty.ADVANCED, DisplayState.GOLD))
    for level, state in tiers:
        band = [p for e, p in live.items() if e.difficulty == level]
        if not band:
            continue
        if not all(band):
            break
        earned = state
    return earned


__all__ = ["DisplayState", "badge_state"]
