"""Data shapes for a girdle scan result.

This is the single source of truth: the CLI's JSON output is a direct
serialization of `ScanResult`, and the HTML dashboard renders the same
object. Never build a second, dashboard-only representation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from girdle.checks import CHECK_REGISTRY, Difficulty
from girdle.hygiene import HygieneResult
from girdle.platform import PlatformResult
from girdle.tiers import CategoryResult, Tier

GIRDLE_VERSION = "0.1.0"

CATEGORY_NAMES = ("tests", "lint", "coverage", "reproducibility", "ci_gating")
BADGE_BY_DIFFICULTY = {
    Difficulty.BASIC: "bronze",
    Difficulty.INTERMEDIATE: "silver",
    Difficulty.ADVANCED: "gold",
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
    platform: PlatformResult | None = None
    hygiene: HygieneResult | None = None
    active_harm: bool = False

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

    @property
    def check_statuses(self) -> dict[str, dict]:
        statuses: dict[str, dict] = {}
        for key, entry in CHECK_REGISTRY.items():
            if entry.reserved:
                continue

            seen_in: list[str] = []
            failing_in: list[str] = []
            if self.hygiene is not None and key in self.hygiene.checks:
                seen_in.append("hygiene")
                if self.hygiene.checks[key].tier < Tier.CONFIGURED:
                    failing_in.append("hygiene")

            for eco in self.ecosystems:
                cat = eco.categories.get(key)
                if key in eco.applicable_categories:
                    seen_in.append(eco.id)
                    if cat is None or cat.tier < Tier.CONFIGURED:
                        failing_in.append(eco.id)
                    continue
                if cat is None:
                    continue
                seen_in.append(eco.id)
                if cat.tier < Tier.CONFIGURED:
                    failing_in.append(eco.id)

            if not seen_in:
                continue

            statuses[key] = {
                "passed": len(failing_in) == 0,
                "difficulty": entry.difficulty.value,
                "categories": list(entry.categories),
                "failing_in": failing_in,
            }
        return statuses

    @staticmethod
    def _badge_state_for_keys(keys: list[str], statuses: dict[str, dict]) -> str | None:
        earned: str | None = None
        for difficulty in (Difficulty.BASIC, Difficulty.INTERMEDIATE, Difficulty.ADVANCED):
            tier_keys = [k for k in keys if Difficulty(statuses[k]["difficulty"]) == difficulty]
            if not tier_keys or not all(statuses[k]["passed"] for k in tier_keys):
                break
            earned = BADGE_BY_DIFFICULTY[difficulty]
        return earned

    @property
    def category_scores(self) -> dict[str, dict]:
        return self._category_scores(self.check_statuses)

    def _category_scores(self, statuses: dict[str, dict]) -> dict[str, dict]:
        per_category: dict[str, list[str]] = defaultdict(list)
        for key, status in statuses.items():
            for category in status["categories"]:
                per_category[category].append(key)

        all_categories = sorted(per_category.keys())
        scores: dict[str, dict] = {}
        for category in all_categories:
            keys = sorted(per_category.get(category, []))
            total = len(keys)
            passed = sum(1 for key in keys if statuses[key]["passed"])
            percentage = round((100.0 * passed / total), 1) if total else 0.0
            outstanding = [key for key in keys if not statuses[key]["passed"]]
            badge = self._badge_state_for_keys(keys, statuses)
            if self.active_harm:
                state = "red"
            else:
                state = badge or "neutral"
            scores[category] = {
                "passed": passed,
                "total": total,
                "percentage": percentage,
                "badge": badge,
                "state": state,
                "outstanding": outstanding,
            }
        return scores

    @property
    def overall_score(self) -> dict:
        return self._overall_score(self.check_statuses)

    def _overall_score(self, statuses: dict[str, dict]) -> dict:
        keys = sorted(statuses.keys())
        total = len(keys)
        passed = sum(1 for key in keys if statuses[key]["passed"])
        percentage = round((100.0 * passed / total), 1) if total else 0.0
        outstanding = [key for key in keys if not statuses[key]["passed"]]
        badge = self._badge_state_for_keys(keys, statuses)
        if self.active_harm:
            state = "red"
        else:
            state = badge or "neutral"
        return {
            "passed": passed,
            "total": total,
            "percentage": percentage,
            "badge": badge,
            "state": state,
            "outstanding": outstanding,
        }

    def to_dict(self) -> dict:
        statuses = self.check_statuses
        category_scores = self._category_scores(statuses)
        overall_score = self._overall_score(statuses)
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
                "overall_percentage": overall_score["percentage"],
                "overall_state": overall_score["state"],
                "overall_badge": overall_score["badge"],
                "overall_outstanding": overall_score["outstanding"],
                "category_scores": category_scores,
            },
            "checks": statuses,
            "active_harm": self.active_harm,
            "warnings": self.warnings,
            "platform": self.platform.to_dict() if self.platform is not None else None,
            "hygiene": self.hygiene.to_dict() if self.hygiene is not None else None,
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
