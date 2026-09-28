"""Shields.io-compatible readiness badge, derived from the same scan dict the
CLI's --json output and the HTML dashboard use - no separate scoring logic.
"""

from __future__ import annotations

from urllib.parse import quote

TIER_LABEL = {0: "absent", 1: "configured", 2: "verified"}
TIER_COLOR = {0: "e05252", 1: "d9a441", 2: "4caf7d"}  # matches dashboard.py's palette

GIRDLE_URL = "https://github.com/fupacat/girdle"


ACTIVE_HARM_MESSAGE = "harm detected"


def badge_url(data: dict, label: str = "girdle") -> str:
    if data["summary"].get("has_active_harm"):
        return (
            f"https://img.shields.io/badge/{quote(label)}"
            f"-{quote(ACTIVE_HARM_MESSAGE)}-{TIER_COLOR[0]}"
        )
    tier = data["summary"]["overall_min"]
    message = TIER_LABEL.get(tier, "unknown")
    color = TIER_COLOR.get(tier, "lightgrey")
    return f"https://img.shields.io/badge/{quote(label)}-{message}-{color}"


def badge_markdown(data: dict, label: str = "girdle", link: str = GIRDLE_URL) -> str:
    return f"[![{label}]({badge_url(data, label)})]({link})"


def badge_endpoint(data: dict, label: str = "girdle") -> dict:
    """Shields.io "endpoint badge" schema: https://shields.io/badges/endpoint-badge

    Meant to be written to a static file and served from a stable public URL
    (e.g. GitHub Pages) that shields.io fetches live on every render, so the
    badge stays current without embedding a fixed color/message in markdown.
    """
    if data["summary"].get("has_active_harm"):
        return {
            "schemaVersion": 1,
            "label": label,
            "message": ACTIVE_HARM_MESSAGE,
            "color": TIER_COLOR[0],
        }
    tier = data["summary"]["overall_min"]
    return {
        "schemaVersion": 1,
        "label": label,
        "message": TIER_LABEL.get(tier, "unknown"),
        "color": TIER_COLOR.get(tier, "lightgrey"),
    }
