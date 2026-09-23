"""JS/TS (npm) detector. Yarn/pnpm/Bun are separate detectors sharing this
package.json-reading logic would be a premature abstraction until a second
one is implemented — kept as a TODO for when yarn/pnpm/bun land.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_json, read_text
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

TEST_RUNNER_DEPS = ("jest", "vitest", "mocha", "ava", "jasmine", "@playwright/test", "cypress")
LINT_CONFIG_FILES = (
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.ts",
)
CI_FILES = (".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml")


class JsNpmDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pkg = root / "package.json"
        if not pkg.exists():
            return None
        # Only claim npm if no other lockfile signals a different toolchain.
        other_lockfiles = ("yarn.lock", "pnpm-lock.yaml", "bun.lockb")
        if any((root / lf).exists() for lf in other_lockfiles):
            return None
        variants = []
        if (root / "tsconfig.json").exists():
            variants.append("typescript")
        return Fingerprint(
            id="js-npm", language="javascript", toolchain="npm", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": self._scan_tests(root, pkg_data),
            "lint": self._scan_lint(root, pkg_data, fp),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": self._scan_ci(root),
        }

    def _scan_tests(self, root: Path, pkg_data: dict) -> CategoryResult:
        scripts = pkg_data.get("scripts", {})
        test_script = scripts.get("test", "")
        deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
        found_runner = next((d for d in TEST_RUNNER_DEPS if d in deps), None)

        evidence = []
        if test_script and "no test specified" not in test_script:
            evidence.append(f"package.json#scripts.test = {test_script!r}")
        if found_runner:
            evidence.append(f"devDependency: {found_runner}")

        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no test script or known test-runner dependency found"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, root: Path, pkg_data: dict, fp: Fingerprint) -> CategoryResult:
        evidence = [str(f) for f in LINT_CONFIG_FILES if (root / f).exists()]
        if "typescript" in fp.variants:
            tsconfig = read_json(root / "tsconfig.json") or {}
            if tsconfig.get("compilerOptions", {}).get("strict"):
                evidence.append("tsconfig.json#compilerOptions.strict = true")
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no eslint config or tsconfig strict mode found"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        lockfile = root / "package-lock.json"
        if not lockfile.exists():
            return CategoryResult(Tier.ABSENT, reason="no package-lock.json found")
        gitignore = read_text(root / ".gitignore") or ""
        if re.search(r"^package-lock\.json$", gitignore, re.MULTILINE):
            return CategoryResult(
                Tier.ABSENT, reason="package-lock.json exists but is gitignored (not committed)"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=["package-lock.json"])

    def _scan_ci(self, root: Path) -> CategoryResult:
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                text = read_text(wf) or ""
                if re.search(r"\bnpm (run )?test\b", text) or re.search(r"\bnpm (run )?ci\b", text):
                    return CategoryResult(
                        Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs npm test"]
                    )
        for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
            p = root / f
            if p.exists() and re.search(r"\bnpm (run )?test\b", read_text(p) or ""):
                return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs npm test"])
        return CategoryResult(Tier.ABSENT, reason="no CI config found running npm test")
