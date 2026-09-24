"""Tier/CategoryResult live here, separate from schema.py, so both
schema.py (ScanResult etc.) and hygiene.py can depend on them without a
circular import (schema.py needs HygieneResult, hygiene.py needs
CategoryResult). schema.py re-exports these names, so existing
`from girdle.schema import Tier, CategoryResult` call sites are unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Tier(IntEnum):
    ABSENT = 0
    CONFIGURED = 1
    VERIFIED = 2


TIER_STATUS = {
    Tier.ABSENT: "absent",
    Tier.CONFIGURED: "configured",
    Tier.VERIFIED: "verified",
}


@dataclass
class CategoryResult:
    tier: Tier
    evidence: list[str] = field(default_factory=list)
    reason: str | None = None
    recommendation: str | None = None

    @property
    def status(self) -> str:
        return TIER_STATUS[self.tier]

    def to_dict(self) -> dict:
        return {
            "tier": int(self.tier),
            "status": self.status,
            "evidence": self.evidence,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }
