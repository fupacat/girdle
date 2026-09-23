"""Top-level scan orchestration: run every detector against the repo root,
build an EcosystemResult per match, and assemble a ScanResult.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from girdle.detectors import ALL_DETECTORS
from girdle.schema import EcosystemResult, ScanResult


def run_scan(repo_root: Path, mode: str = "static") -> ScanResult:
    repo_root = repo_root.resolve()
    ecosystems: list[EcosystemResult] = []
    warnings: list[str] = []

    for detector in ALL_DETECTORS:
        fp = detector.detect(repo_root)
        if fp is None:
            continue
        categories = detector.scan(fp, mode)
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

    return ScanResult(
        repo_root=str(repo_root),
        scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        mode=mode,
        ecosystems=ecosystems,
        warnings=warnings,
    )
