from __future__ import annotations

from pathlib import Path

from girdle.detectors import js_common
from girdle.detectors._util import read_json
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

PNPM_LOCK_YAML = "pnpm-lock.yaml"


class JsPnpmDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "package.json").exists() or not (root / PNPM_LOCK_YAML).exists():
            return None
        variants = js_common.detect_variants(root)
        if (root / "pnpm-workspace.yaml").exists():
            variants.append("workspace")
        return Fingerprint(
            id="js-pnpm", language="javascript", toolchain="pnpm", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": js_common.scan_tests(pkg_data, "pnpm"),
            "lint": js_common.scan_lint(root, fp, "pnpm"),
            "coverage": js_common.scan_coverage(pkg_data, "pnpm"),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": js_common.scan_ci(root, r"\bpnpm (run )?test\b", "pnpm test"),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return js_common.run_commands(fp.root, "pnpm")

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        if js_common.is_lockfile_gitignored(root, PNPM_LOCK_YAML):
            return CategoryResult(
                Tier.ABSENT, reason=f"{PNPM_LOCK_YAML} exists but is gitignored",
                recommendation=f"Remove {PNPM_LOCK_YAML} from .gitignore and commit it.",
            )
        evidence = [PNPM_LOCK_YAML]
        if "workspace" in fp.variants:
            evidence.append(
                "pnpm-workspace.yaml (monorepo - packages may warrant per-package scoring)"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)
