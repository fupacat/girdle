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
COVERAGE_DEPS = (
    "nyc", "c8", "@vitest/coverage-v8", "@vitest/coverage-istanbul", "@vitest/coverage-c8",
)


def detect_variants(root: Path) -> list[str]:
    return ["typescript"] if (root / "tsconfig.json").exists() else []


def scan_tests(pkg_data: dict, pkg_manager: str = "npm") -> CategoryResult:
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
        install = "add" if pkg_manager in ("yarn", "pnpm", "bun") else "install --save-dev"
        return CategoryResult(
            Tier.ABSENT,
            reason="no test script or known test-runner dependency found",
            recommendation=(
                f'Add a test runner (e.g. `{pkg_manager} {install} vitest`) and a '
                f'"test" script in package.json.'
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def scan_lint(root: Path, fp: Fingerprint, pkg_manager: str = "npm") -> CategoryResult:
    evidence = [str(f) for f in LINT_CONFIG_FILES if (root / f).exists()]
    if "typescript" in fp.variants:
        tsconfig = read_json(root / "tsconfig.json") or {}
        if tsconfig.get("compilerOptions", {}).get("strict"):
            evidence.append("tsconfig.json#compilerOptions.strict = true")
    if not evidence:
        install = "add" if pkg_manager in ("yarn", "pnpm", "bun") else "install --save-dev"
        rec = f"Add an ESLint config (`{pkg_manager} {install} eslint` then create eslint config)"
        if "typescript" in fp.variants:
            rec += ", or enable `compilerOptions.strict` in tsconfig.json"
        return CategoryResult(
            Tier.ABSENT, reason="no eslint config or tsconfig strict mode found",
            recommendation=rec + ".",
        )
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def scan_coverage(pkg_data: dict, pkg_manager: str = "npm") -> CategoryResult:
    scripts = pkg_data.get("scripts", {})
    deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
    found_dep = next((d for d in COVERAGE_DEPS if d in deps), None)
    has_coverage_script = "coverage" in scripts or any(
        "--coverage" in v for v in scripts.values() if isinstance(v, str)
    )
    jest_cfg = pkg_data.get("jest", {})
    jest_coverage = isinstance(jest_cfg, dict) and jest_cfg.get("collectCoverage") is True

    evidence = []
    if found_dep:
        evidence.append(f"devDependency: {found_dep}")
    if has_coverage_script:
        evidence.append("package.json#scripts.coverage")
    if jest_coverage:
        evidence.append("package.json#jest.collectCoverage")

    if not evidence:
        install = "add" if pkg_manager in ("yarn", "pnpm", "bun") else "install --save-dev"
        return CategoryResult(
            Tier.ABSENT, reason="no coverage tooling detected",
            recommendation=(
                f"Add coverage tooling (e.g. `{pkg_manager} {install} "
                f'@vitest/coverage-v8` or `nyc`) and a "coverage" script in package.json.'
            ),
        )
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
    return CategoryResult(
        Tier.ABSENT, reason=f"no CI config found running {run_label}",
        recommendation=(
            f"Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs `{run_label}`."
        ),
    )


def is_lockfile_gitignored(root: Path, lockfile_name: str) -> bool:
    gitignore = read_text(root / ".gitignore") or ""
    return bool(re.search(rf"^{re.escape(lockfile_name)}$", gitignore, re.MULTILINE))


def run_commands(root: Path, pkg_manager: str) -> dict[str, list[str]]:
    """--run commands for a package.json-based toolchain. `pkg_manager` is
    the literal command (npm/yarn/pnpm/bun); only a declared `scripts.lint`
    is run for lint, since there's no universal lint entry point otherwise.
    """
    commands = {"tests": [pkg_manager, "test"]}
    pkg_data = read_json(root / "package.json") or {}
    if "lint" in pkg_data.get("scripts", {}):
        commands["lint"] = [pkg_manager, "run", "lint"]
    if "coverage" in pkg_data.get("scripts", {}):
        commands["coverage"] = [pkg_manager, "run", "coverage"]
    return commands
