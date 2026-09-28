"""Data shapes for a girdle scan result.

This is the single source of truth: the CLI's JSON output is a direct
serialization of `ScanResult`, and the HTML dashboard renders the same
object. Never build a second, dashboard-only representation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from girdle.checks import CHECK_REGISTRY
from girdle.hygiene import HygieneResult
from girdle.platform import PlatformResult
from girdle.tiers import CategoryResult, Tier

GIRDLE_VERSION = "0.1.0"

CATEGORY_NAMES = ("tests", "lint", "coverage", "reproducibility", "ci_gating")


def _passed(result: CategoryResult) -> bool:
    return result.tier > Tier.ABSENT


def _percentage(results: list[CategoryResult]) -> float:
    if not results:
        return 0.0
    return round(sum(1 for result in results if _passed(result)) * 100 / len(results), 2)


def _registry_category_names() -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for entry in CHECK_REGISTRY.values():
        for category in entry.categories:
            if category not in seen:
                seen.add(category)
                names.append(category)
    return names


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
    def applicable_checks(self) -> dict[str, CategoryResult]:
        applicable = {}
        categories = set(self.applicable_categories)
        for check_key, result in self.categories.items():
            entry = CHECK_REGISTRY.get(check_key)
            if entry is None:
                continue
            if any(category in categories for category in entry.categories):
                applicable[check_key] = result
        return applicable

    @property
    def category_percentages(self) -> dict[str, float]:
        percentages = {category: 0.0 for category in self.applicable_categories}
        applicable_checks = self.applicable_checks
        for category in self.applicable_categories:
            results = [
                result
                for check_key, result in applicable_checks.items()
                if category in CHECK_REGISTRY[check_key].categories
            ]
            percentages[category] = _percentage(results)
        return percentages

    @property
    def overall_percentage(self) -> float:
        return _percentage(list(self.applicable_checks.values()))

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
            "category_percentages": self.category_percentages,
            "overall_percentage": self.overall_percentage,
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

    @property
    def category_percentages(self) -> dict[str, float]:
        percentages = {category: 0.0 for category in _registry_category_names()}
        bucketed: dict[str, list[CategoryResult]] = {category: [] for category in percentages}

        for eco in self.ecosystems:
            for check_key, result in eco.applicable_checks.items():
                entry = CHECK_REGISTRY.get(check_key)
                if entry is None:
                    continue
                for category in entry.categories:
                    if category in eco.applicable_categories:
                        bucketed[category].append(result)

        if self.hygiene is not None:
            for check_key, result in self.hygiene.checks.items():
                entry = CHECK_REGISTRY.get(check_key)
                if entry is None:
                    continue
                for category in entry.categories:
                    bucketed[category].append(result)

        for category, results in bucketed.items():
            percentages[category] = _percentage(results)
        return percentages

    @property
    def overall_percentage(self) -> float:
        results: list[CategoryResult] = []
        for eco in self.ecosystems:
            results.extend(eco.applicable_checks.values())
        if self.hygiene is not None:
            results.extend(self.hygiene.checks.values())
        return _percentage(results)

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
                "overall_percentage": self.overall_percentage,
                "category_percentages": self.category_percentages,
            },
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
