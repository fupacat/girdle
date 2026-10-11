"""Shared file-reading helpers for detectors. Never scrapes free-text content
into evidence — callers pass back file paths / matched markers only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib
import yaml

from girdle.schema import CategoryResult, Tier

SEMGREP_CONFIG_NAMES = (".semgrep.yml", ".semgrep.yaml", "semgrep.yml", "semgrep.yaml")
SONAR_CONFIG_NAMES = ("sonar-project.properties", ".sonarcloud.properties")

CODEQL_CI_PATTERN = re.compile(r"github/codeql-action(?:/|@)")
SEMGREP_CI_PATTERN = re.compile(
    r"(?:returntocorp|semgrep)/semgrep-action|\bsemgrep(?:-agent)?\s+(?:ci|scan)\b"
)
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
    run_re = re.compile(run_pattern)
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            text = read_text(wf) or ""
            if _gha_workflow_runs_tool_on_pr_or_default_push(text, run_re):
                return CategoryResult(
                    Tier.CONFIGURED,
                    evidence=[f".github/workflows/{wf.name}: runs {run_label}"],
                )
    for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / f
        if p.exists() and run_re.search(read_text(p) or ""):
            return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs {run_label}"])
    return CategoryResult(
        Tier.ABSENT,
        reason=f"no CI config found running {run_label}",
        recommendation=(
            f"Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs `{run_label}`."
        ),
    )


def _gha_workflow_runs_tool_on_pr_or_default_push(
    workflow_text: str, run_re: re.Pattern[str]
) -> bool:
    try:
        workflow = yaml.safe_load(workflow_text) or {}
    except yaml.YAMLError:
        return False
    if not isinstance(workflow, dict):
        return False
    on_config = workflow.get("on", workflow.get(True))
    if not _gha_triggers_pr_or_default_push(on_config):
        return False
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run")
            if isinstance(run_cmd, str) and _run_step_matches(run_cmd, run_re):
                return True
    return False


def _run_step_matches(run_cmd: str, run_re: re.Pattern[str]) -> bool:
    for line in run_cmd.splitlines() or [run_cmd]:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if run_re.search(line):
            return True
    return False


def _gha_triggers_pr_or_default_push(on_config: object) -> bool:
    if isinstance(on_config, str):
        return on_config in {"pull_request", "pull_request_target", "merge_group", "push"}
    if isinstance(on_config, list):
        return any(
            isinstance(event, str)
            and event in {"pull_request", "pull_request_target", "merge_group", "push"}
            for event in on_config
        )
    if not isinstance(on_config, dict):
        return False
    if any(event in on_config for event in ("pull_request", "pull_request_target", "merge_group")):
        return True
    if "push" not in on_config:
        return False
    return _gha_push_targets_default_branch(on_config.get("push"))


def _gha_push_targets_default_branch(push_config: object) -> bool:
    if push_config is None:
        return True
    if not isinstance(push_config, dict):
        return True
    branches = push_config.get("branches")
    branches_ignore = push_config.get("branches-ignore")

    include_default = True
    if branches is not None:
        include_default = any(_is_default_branch_selector(v) for v in _string_values(branches))
    if not include_default:
        return False
    if branches_ignore is not None and any(
        _is_default_branch_selector(v) for v in _string_values(branches_ignore)
    ):
        return False
    return True


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _is_default_branch_selector(value: str) -> bool:
    normalized = value.strip().removeprefix("refs/heads/")
    return (
        normalized in {"master", "main"}
        or "default_branch" in normalized
    )
