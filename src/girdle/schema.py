"""Data shapes for a girdle scan result.

This is the single source of truth: the CLI's JSON output is a direct
serialization of `ScanResult`, and the HTML dashboard renders the same
object. Never build a second, dashboard-only representation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum

GIRDLE_VERSION = "0.1.0"

CATEGORY_NAMES = ("tests", "lint", "reproducibility", "ci_gating")


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

    @property
    def status(self) -> str:
        return TIER_STATUS[self.tier]

    def to_dict(self) -> dict:
        return {
            "tier": int(self.tier),
            "status": self.status,
            "evidence": self.evidence,
            "reason": self.reason,
        }


@dataclass
class EcosystemResult:
    id: str
    language: str
    toolchain: str
    root: str
    variants: list[str] = field(default_factory=list)
    categories: dict[str, CategoryResult] = field(default_factory=dict)
    applicable_categories: list[str] = field(default_factory=lambda: list(CATEGORY_NAMES))

    @property
    def _applicable_tiers(self) -> list[Tier]:
        return [self.categories[c].tier for c in self.applicable_categories if c in self.categories]

    @property
    def category_min(self) -> int:
        return min((int(t) for t in self._applicable_tiers), default=0)

    @property
    def category_avg(self) -> float:
        applicable = self._applicable_tiers
        if not applicable:
            return 0.0
        return round(sum(int(t) for t in applicable) / (len(applicable) * Tier.VERIFIED), 4)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "language": self.language,
            "toolchain": self.toolchain,
            "variants": self.variants,
            "root": self.root,
            "categories": {k: v.to_dict() for k, v in self.categories.items()},
            "category_min": self.category_min,
            "category_avg": self.category_avg,
            "applicable_categories": self.applicable_categories,
        }


@dataclass
class ScanResult:
    repo_root: str
    scanned_at: str
    mode: str  # "static" | "run"
    ecosystems: list[EcosystemResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def overall_min(self) -> int:
        return min((e.category_min for e in self.ecosystems), default=0)

    @property
    def overall_avg(self) -> float:
        if not self.ecosystems:
            return 0.0
        return round(sum(e.category_avg for e in self.ecosystems) / len(self.ecosystems), 4)

    @property
    def weakest_category(self) -> str | None:
        worst: tuple[int, str] | None = None
        for eco in self.ecosystems:
            for name in eco.applicable_categories:
                cat = eco.categories.get(name)
                if cat is None:
                    continue
                if worst is None or int(cat.tier) < worst[0]:
                    worst = (int(cat.tier), name)
        return worst[1] if worst else None

    def to_dict(self) -> dict:
        return {
            "girdle_version": GIRDLE_VERSION,
            "scanned_at": self.scanned_at,
            "repo_root": self.repo_root,
            "mode": self.mode,
            "ecosystems": [e.to_dict() for e in self.ecosystems],
            "summary": {
                "ecosystem_count": len(self.ecosystems),
                "weakest_category": self.weakest_category,
                "overall_min": self.overall_min,
                "overall_avg": self.overall_avg,
            },
            "warnings": self.warnings,
        }


__all__ = [
    "Tier",
    "CategoryResult",
    "EcosystemResult",
    "ScanResult",
    "CATEGORY_NAMES",
    "GIRDLE_VERSION",
    "asdict",
]
