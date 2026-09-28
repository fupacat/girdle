"""Registry of every check girdle computes, with category membership and difficulty tier.

Each entry maps a check key to:
- ``categories``: which scoring categories it counts toward (many-to-many)
- ``difficulty``: static difficulty tier (``basic``, ``intermediate``, or ``advanced``)

Checks that are reserved for future implementation are included here so that
the registry is complete, but they do not correspond to a live check yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class Difficulty(str, Enum):
    """Static difficulty tier for a check, independent of category."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class CheckEntry:
    """Registry entry for a single check."""

    key: str
    categories: tuple[str, ...]
    difficulty: Difficulty

    # When True the check key is a placeholder for a not-yet-implemented check.
    reserved: bool = False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ENTRIES: tuple[CheckEntry, ...] = (
    # ── Basic ──────────────────────────────────────────────────────────────
    CheckEntry("readme", ("readme",), Difficulty.BASIC),
    CheckEntry("gitignore", ("gitignore",), Difficulty.BASIC),
    CheckEntry(
        "license",
        ("license",),
        Difficulty.BASIC,
        reserved=True,
    ),
    CheckEntry("contributing", ("contributing",), Difficulty.BASIC),
    # ── Intermediate ───────────────────────────────────────────────────────
    CheckEntry("tests", ("tests",), Difficulty.INTERMEDIATE),
    CheckEntry("lint", ("lint",), Difficulty.INTERMEDIATE),
    CheckEntry("coverage", ("coverage",), Difficulty.INTERMEDIATE),
    CheckEntry("ci_gating", ("ci_gating",), Difficulty.INTERMEDIATE),
    CheckEntry("codeowners", ("codeowners",), Difficulty.INTERMEDIATE),
    CheckEntry("dependency_monitoring", ("dependency_monitoring",), Difficulty.INTERMEDIATE),
    CheckEntry("editorconfig", ("editorconfig",), Difficulty.INTERMEDIATE),
    CheckEntry("gitattributes", ("gitattributes",), Difficulty.INTERMEDIATE),
    CheckEntry("precommit", ("precommit",), Difficulty.INTERMEDIATE),
    # ── Advanced ───────────────────────────────────────────────────────────
    CheckEntry("agent_instructions", ("agent_instructions",), Difficulty.ADVANCED),
    CheckEntry("agent_sandbox_bootstrap", ("agent_sandbox_bootstrap",), Difficulty.ADVANCED),
    CheckEntry(
        "reproducibility",
        ("reproducibility",),
        Difficulty.ADVANCED,
        reserved=True,
    ),
)

# Keyed look-up, built once at import time.
CHECK_REGISTRY: dict[str, CheckEntry] = {e.key: e for e in _ENTRIES}


def checks_by_difficulty(difficulty: Difficulty) -> Sequence[CheckEntry]:
    """Return all registry entries that match *difficulty*."""
    return [e for e in _ENTRIES if e.difficulty is difficulty]


__all__ = [
    "Difficulty",
    "CheckEntry",
    "CHECK_REGISTRY",
    "checks_by_difficulty",
]
