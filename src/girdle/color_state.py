"""Display color-state logic for dashboard percentages.

Given a percentage (0–100 float, or None when absent) and an active-harm
flag, returns the display state:

- **neutral** – default; nothing earned yet, including 0% / absent.  Never
  a warning color for mere incompleteness.
- **bronze / silver / gold** – badge tiers earned once the percentage
  crosses the threshold corresponding to a check-difficulty band (BASIC →
  bronze, BASIC + INTERMEDIATE → silver, all non-reserved → gold).
- **red** – reserved exclusively for active-harm findings (committed
  secrets, poisoned agent instructions).  Fires regardless of percentage;
  is never a point on the badge scale.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from girdle.checks import CHECK_REGISTRY, CheckEntry, Difficulty


class DisplayState(str, Enum):
    NEUTRAL = "neutral"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    RED = "red"


def _badge_thresholds(
    entries: Iterable[CheckEntry] | None = None,
) -> tuple[float, float, float]:
    """Return *(bronze, silver, gold)* percentage thresholds from the live registry.

    Thresholds are derived by asking: "what percentage would you score if
    every non-reserved check of at most difficulty *D* passed?"

    - **Bronze** – all BASIC checks passing.
    - **Silver** – all BASIC + INTERMEDIATE checks passing.
    - **Gold** – 100 % (every non-reserved check passing).

    When *entries* is provided, thresholds are derived only from those checks;
    otherwise the full registry is used. Reserved checks are excluded so the
    thresholds reflect only real, actionable checks.
    """
    active = [
        e
        for e in (entries if entries is not None else CHECK_REGISTRY.values())
        if not e.reserved
    ]
    total = len(active)
    if total == 0:
        return (0.0, 0.0, 100.0)
    basic = sum(1 for e in active if e.difficulty is Difficulty.BASIC)
    basic_and_intermediate = sum(
        1 for e in active
        if e.difficulty in (Difficulty.BASIC, Difficulty.INTERMEDIATE)
    )
    bronze = round(basic / total * 100, 2)
    silver = round(basic_and_intermediate / total * 100, 2)
    return (bronze, silver, 100.0)


BRONZE_THRESHOLD, SILVER_THRESHOLD, GOLD_THRESHOLD = _badge_thresholds()


def display_state(
    percentage: float | None,
    *,
    active_harm: bool = False,
    entries: Iterable[CheckEntry] | None = None,
) -> DisplayState:
    """Return the display state for a dashboard percentage and active-harm flag.

    Args:
        percentage: Overall or per-category percentage (0–100), or ``None``
            when no applicable checks exist.
        active_harm: ``True`` when an active-harm finding (secrets,
            malicious/poisoned agent instructions) is present.  Forces
            :attr:`DisplayState.RED` regardless of *percentage*.
        entries: Applicable checks for this scan, when thresholds should be
            derived from only the checks included in *percentage*.
    """
    if active_harm:
        return DisplayState.RED
    bronze, silver, gold = (
        _badge_thresholds(entries)
        if entries is not None
        else (BRONZE_THRESHOLD, SILVER_THRESHOLD, GOLD_THRESHOLD)
    )
    if percentage is None or percentage < bronze:
        return DisplayState.NEUTRAL
    if percentage < silver:
        return DisplayState.BRONZE
    if percentage < gold:
        return DisplayState.SILVER
    return DisplayState.GOLD


__all__ = [
    "DisplayState",
    "display_state",
    "BRONZE_THRESHOLD",
    "SILVER_THRESHOLD",
    "GOLD_THRESHOLD",
]
