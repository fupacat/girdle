"""Shields.io-compatible readiness badge, derived from the same scan dict the
CLI's --json output and the HTML dashboard use - no separate scoring logic.
"""

from __future__ import annotations

from urllib.parse import quote

TIER_LABEL = {0: "absent", 1: "configured", 2: "verified"}
TIER_COLOR = {0: "e05252", 1: "d9a441", 2: "4caf7d"}  # matches dashboard.py's palette

GIRDLE_URL = "https://github.com/fupacat/girdle"


def badge_url(data: dict, label: str = "girdle") -> str:
    tier = data["summary"]["overall_min"]
    message = TIER_LABEL.get(tier, "unknown")
    color = TIER_COLOR.get(tier, "lightgrey")
    return f"https://img.shields.io/badge/{quote(label)}-{message}-{color}"


def badge_markdown(data: dict, label: str = "girdle", link: str = GIRDLE_URL) -> str:
    return f"[![{label}]({badge_url(data, label)})]({link})"
