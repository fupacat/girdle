"""Shields.io-compatible readiness badge, derived from the same scan dict the
CLI's --json output and the HTML dashboard use - no separate scoring logic.
"""

from __future__ import annotations

from urllib.parse import quote

TIER_LABEL = {0: "absent", 1: "configured", 2: "verified"}
TIER_COLOR = {0: "e05252", 1: "d9a441", 2: "4caf7d"}  # matches dashboard.py's palette
STATE_COLOR = {
    "neutral": "7f8794",
    "bronze": "cd7f32",
    "silver": "aeb5c0",
    "gold": "d4af37",
    "red": "e05252",
}

GIRDLE_URL = "https://github.com/fupacat/girdle"


def _summary_message_color(data: dict) -> tuple[str, str]:
    summary = data.get("summary", {})
    if "overall_percentage" in summary and "overall_state" in summary:
        percentage = summary["overall_percentage"]
        state = summary["overall_state"]
        suffix = f" {state}" if state in {"bronze", "silver", "gold"} else ""
        return f"{percentage:g}%{suffix}", STATE_COLOR.get(state, "lightgrey")

    tier = summary.get("overall_min")
    return TIER_LABEL.get(tier, "unknown"), TIER_COLOR.get(tier, "lightgrey")


def badge_url(data: dict, label: str = "girdle") -> str:
    message, color = _summary_message_color(data)
    return f"https://img.shields.io/badge/{quote(label)}-{quote(message)}-{color}"


def badge_markdown(data: dict, label: str = "girdle", link: str = GIRDLE_URL) -> str:
    return f"[![{label}]({badge_url(data, label)})]({link})"


def badge_endpoint(data: dict, label: str = "girdle") -> dict:
    """Shields.io "endpoint badge" schema: https://shields.io/badges/endpoint-badge

    Meant to be written to a static file and served from a stable public URL
    (e.g. GitHub Pages) that shields.io fetches live on every render, so the
    badge stays current without embedding a fixed color/message in markdown.
    """
    message, color = _summary_message_color(data)
    return {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color,
    }
