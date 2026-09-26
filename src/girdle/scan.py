"""Top-level scan orchestration: run every detector against the repo root,
build an EcosystemResult per match, and assemble a ScanResult.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from girdle.coverage_gate import detect_gate
from girdle.coverage_parse import parse_percentage
from girdle.detectors import ALL_DETECTORS
from girdle.detectors.base import Detector, Fingerprint
from girdle.hygiene import build_hygiene
from girdle.platform import check_platform
from girdle.runner import run_check
from girdle.schema import CategoryResult, EcosystemResult, ScanResult, Tier


def _run_detector(detector: Detector, repo_root: Path, mode: str) -> EcosystemResult | None:
    fp = detector.detect(repo_root)
    if fp is None:
        return None
    categories = detector.scan(fp, mode)
    _verify(detector, fp, categories, mode)
    _check_coverage_gate(fp, categories)
    return EcosystemResult(
        id=fp.id,
        language=fp.language,
        toolchain=fp.toolchain,
        root=str(fp.root.relative_to(repo_root)) if fp.root != repo_root else ".",
        variants=fp.variants,
        categories=categories,
        applicable_categories=detector.applicable_categories(fp),
    )


def run_scan(
    repo_root: Path, mode: str = "static", check_platform_enforcement: bool = False
) -> ScanResult:
    repo_root = repo_root.resolve()
    ecosystems = [
        eco
        for detector in ALL_DETECTORS
        if (eco := _run_detector(detector, repo_root, mode)) is not None
    ]
    warnings: list[str] = []

    if not ecosystems:
        warnings.append("no known ecosystem detected at repo root")

    platform = check_platform(repo_root) if check_platform_enforcement else None
    languages = {e.language for e in ecosystems}
    hygiene = build_hygiene(repo_root, languages)

    return ScanResult(
        repo_root=str(repo_root),
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        mode=mode,
        ecosystems=ecosystems,
        warnings=warnings,
        platform=platform,
        hygiene=hygiene,
    )


def _check_coverage_gate(fp: Fingerprint, categories: dict[str, CategoryResult]) -> None:
    """Enriches the coverage category's evidence/recommendation with
    whether it's enforced as a PR-scoped gate in CI - only meaningful, and
    only checked, when both coverage AND ci_gating are already configured
    for this ecosystem. Neither half makes sense to report in isolation:
    a gate with no coverage tool to gate, or no CI to enforce it in, isn't
    a finding, it's noise.
    """
    coverage = categories.get("coverage")
    ci_gating = categories.get("ci_gating")
    if coverage is None or ci_gating is None:
        return
    if coverage.tier < Tier.CONFIGURED or ci_gating.tier < Tier.CONFIGURED:
        return

    gate = detect_gate(fp.root)
    if gate:
        coverage.evidence = [*coverage.evidence, f"PR-scoped gate: {gate}"]
    elif coverage.recommendation is None:
        coverage.recommendation = (
            "Coverage runs but isn't enforced as a PR-scoped gate. Add a diff-coverage "
            "check (Codecov's patch status, Coveralls, or `diff-cover --fail-under=N` "
            "in CI) as a required status check."
        )


def _verify(
    detector: Detector, fp: Fingerprint, categories: dict[str, CategoryResult], mode: str
) -> None:
    """Mutates `categories` in place. In "run" mode: upgrade CONFIGURED ->
    VERIFIED for any category the detector declares a run command for, if
    that command actually passes when executed against the repo. In
    "static" mode: for the same categories, add a generic "run --run to
    verify" recommendation instead of executing anything - only shown where
    a verify path genuinely exists (a detector-declared run command), not a
    blanket suggestion on categories that can never be tier-2 verifiable
    (e.g. reproducibility, ci_gating).
    """
    get_commands = getattr(detector, "run_commands", None)
    if get_commands is None:
        return
    commands = get_commands(fp)
    for category, command in commands.items():
        result = categories.get(category)
        if result is None or result.tier != Tier.CONFIGURED:
            continue
        if mode == "static":
            if result.recommendation is None:
                result.recommendation = (
                    "Run `girdle scan --run` to verify this actually passes (tier 2)."
                )
            continue
        outcome = run_check(command, fp.root)
        if outcome.passed:
            result.tier = Tier.VERIFIED
            evidence_line = f"verified: `{' '.join(command)}` exited 0"
            if category == "coverage":
                pct = parse_percentage(fp.language, outcome.stdout)
                if pct:
                    evidence_line += f" ({pct} coverage)"
            result.evidence = [*result.evidence, evidence_line]
        elif outcome.ran:
            result.reason = outcome.reason
        else:
            result.evidence = [*result.evidence, f"not verified: {outcome.reason}"]
