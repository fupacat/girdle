from __future__ import annotations

from pathlib import Path

from girdle.detectors import js_common
from girdle.detectors._util import read_json, read_text
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class JsYarnDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "package.json").exists() or not (root / "yarn.lock").exists():
            return None
        variants = js_common.detect_variants(root)
        if (root / ".yarnrc.yml").exists():
            variants.append("berry")
        return Fingerprint(
            id="js-yarn", language="javascript", toolchain="yarn", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": js_common.scan_tests(pkg_data),
            "lint": js_common.scan_lint(root, fp),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": js_common.scan_ci(root, r"\byarn (run )?test\b", "yarn test"),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return js_common.run_commands(fp.root, "yarn")

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        if js_common.is_lockfile_gitignored(root, "yarn.lock"):
            return CategoryResult(Tier.ABSENT, reason="yarn.lock exists but is gitignored")
        evidence = ["yarn.lock"]
        if "berry" in fp.variants:
            # PnP mode changes what "installed" even means; note it rather than score it.
            rc = read_text(root / ".yarnrc.yml") or ""
            if "nodeLinker: pnp" in rc or "nodeLinker: 'pnp'" in rc:
                evidence.append(".yarnrc.yml (Yarn Berry, PnP linker)")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)
