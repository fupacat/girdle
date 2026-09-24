"""Top-level scan orchestration: run every detector against the repo root,
build an EcosystemResult per match, and assemble a ScanResult.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from girdle.detectors import ALL_DETECTORS
from girdle.detectors.base import Detector, Fingerprint
from girdle.platform import check_platform
from girdle.runner import run_check
from girdle.schema import CategoryResult, EcosystemResult, ScanResult, Tier


def run_scan(
    repo_root: Path, mode: str = "static", check_platform_enforcement: bool = False
) -> ScanResult:
    repo_root = repo_root.resolve()
    ecosystems: list[EcosystemResult] = []
    warnings: list[str] = []

    for detector in ALL_DETECTORS:
        fp = detector.detect(repo_root)
        if fp is None:
            continue
        categories = detector.scan(fp, mode)
        _verify(detector, fp, categories, mode)
        ecosystems.append(
            EcosystemResult(
                id=fp.id,
                language=fp.language,
                toolchain=fp.toolchain,
                root=str(fp.root.relative_to(repo_root)) if fp.root != repo_root else ".",
                variants=fp.variants,
                categories=categories,
                applicable_categories=detector.applicable_categories(fp),
            )
        )

    if not ecosystems:
        warnings.append("no known ecosystem detected at repo root")

    platform = check_platform(repo_root) if check_platform_enforcement else None

    return ScanResult(
        repo_root=str(repo_root),
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        mode=mode,
        ecosystems=ecosystems,
        warnings=warnings,
        platform=platform,
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
            result.evidence = [*result.evidence, f"verified: `{' '.join(command)}` exited 0"]
        elif outcome.ran:
            result.reason = outcome.reason
        else:
            result.evidence = [*result.evidence, f"not verified: {outcome.reason}"]
