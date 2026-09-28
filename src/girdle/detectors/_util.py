"""Shared file-reading helpers for detectors. Never scrapes free-text content
into evidence — callers pass back file paths / matched markers only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

from girdle.schema import CategoryResult, Tier

SEMGREP_CONFIG_NAMES = (".semgrep.yml", ".semgrep.yaml", "semgrep.yml", "semgrep.yaml")
SONAR_CONFIG_NAMES = ("sonar-project.properties", ".sonarcloud.properties")

CODEQL_CI_PATTERN = re.compile(r"github/codeql-action(?:/|@)")
SEMGREP_CI_PATTERN = re.compile(r"returntocorp/semgrep-action|\bsemgrep(?:-agent)?\s+(?:ci|scan)\b")
SONAR_CI_PATTERN = re.compile(
    r"sonarcloud-github-action|sonarqube-scan-action|sonarsource/sonar-scan-action|"
    r"\bsonar-scanner\b",
    re.IGNORECASE,
)
GITLAB_SAST_PATTERN = re.compile(r"Jobs/SAST\.gitlab-ci\.yml|\bsemgrep-sast\b", re.IGNORECASE)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_toml(path: Path) -> dict | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _ci_texts(root: Path):
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            yield f".github/workflows/{wf.name}", read_text(wf) or ""
    for name in (".gitlab-ci.yml", "azure-pipelines.yml"):
        path = root / name
        if path.exists():
            yield name, read_text(path) or ""


def _first_existing_name(root: Path, names: tuple[str, ...]) -> str | None:
    for name in names:
        if (root / name).exists():
            return name
    return None


def scan_static_analysis(root: Path) -> CategoryResult:
    sonar_cfg = _first_existing_name(root, SONAR_CONFIG_NAMES)
    for label, text in _ci_texts(root):
        if CODEQL_CI_PATTERN.search(text):
            return CategoryResult(
                Tier.CONFIGURED, evidence=[f"{label}: uses github/codeql-action"]
            )
        if SEMGREP_CI_PATTERN.search(text):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{label}: runs Semgrep"])
        if sonar_cfg and SONAR_CI_PATTERN.search(text):
            return CategoryResult(
                Tier.CONFIGURED,
                evidence=[f"{sonar_cfg} + {label}: runs SonarQube/SonarCloud"],
            )
        if GITLAB_SAST_PATTERN.search(text):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{label}: includes GitLab SAST"])

    for name in SEMGREP_CONFIG_NAMES:
        if (root / name).exists():
            return CategoryResult(Tier.CONFIGURED, evidence=[name])
    if (root / ".semgrep").is_dir():
        return CategoryResult(Tier.CONFIGURED, evidence=[".semgrep/"])

    return CategoryResult(
        Tier.ABSENT,
        reason="no static-analysis/SAST tooling found",
        recommendation=(
            "Add a static-analysis workflow such as GitHub CodeQL "
            "(`github/codeql-action`), Semgrep, or SonarQube/SonarCloud."
        ),
    )


def scan_ci(root: Path, run_pattern: str, run_label: str) -> CategoryResult:
    """Shared CI-gating detection used by single-toolchain detectors.

    Mirrors the equivalent helpers in js_common.py / python_common.py.
    Globs .github/workflows/*.y*ml first, then falls back to
    .gitlab-ci.yml and azure-pipelines.yml.
    """
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            text = read_text(wf) or ""
            if re.search(run_pattern, text):
                return CategoryResult(
                    Tier.CONFIGURED,
                    evidence=[f".github/workflows/{wf.name}: runs {run_label}"],
                )
    for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / f
        if p.exists() and re.search(run_pattern, read_text(p) or ""):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs {run_label}"])
    return CategoryResult(
        Tier.ABSENT,
        reason=f"no CI config found running {run_label}",
        recommendation=(
            f"Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs `{run_label}`."
        ),
    )
