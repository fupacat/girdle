"""Shared package.json-based scan logic for npm/Yarn/pnpm/Bun. Toolchains
differ only in which lockfile signals them and how that lockfile is judged;
tests/lint/CI detection is identical across all four.
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


def detect_variants(root: Path) -> list[str]:
    return ["typescript"] if (root / "tsconfig.json").exists() else []


def scan_tests(pkg_data: dict) -> CategoryResult:
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


def scan_lint(root: Path, fp: Fingerprint) -> CategoryResult:
    evidence = [str(f) for f in LINT_CONFIG_FILES if (root / f).exists()]
    if "typescript" in fp.variants:
        tsconfig = read_json(root / "tsconfig.json") or {}
        if tsconfig.get("compilerOptions", {}).get("strict"):
            evidence.append("tsconfig.json#compilerOptions.strict = true")
    if not evidence:
        return CategoryResult(Tier.ABSENT, reason="no eslint config or tsconfig strict mode found")
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def scan_ci(root: Path, run_pattern: str, run_label: str) -> CategoryResult:
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            text = read_text(wf) or ""
            if re.search(run_pattern, text):
                return CategoryResult(
                    Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs {run_label}"]
                )
    for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / f
        if p.exists() and re.search(run_pattern, read_text(p) or ""):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs {run_label}"])
    return CategoryResult(Tier.ABSENT, reason=f"no CI config found running {run_label}")


def is_lockfile_gitignored(root: Path, lockfile_name: str) -> bool:
    gitignore = read_text(root / ".gitignore") or ""
    return bool(re.search(rf"^{re.escape(lockfile_name)}$", gitignore, re.MULTILINE))
