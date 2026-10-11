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
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in sorted(wf_dir.glob("*.y*ml")):
            text = read_text(wf) or ""
            if _workflow_runs_tool_on_gating_trigger(text, run_pattern):
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


def _workflow_runs_tool_on_gating_trigger(workflow_text: str, run_pattern: str) -> bool:
    try:
        data = yaml.safe_load(workflow_text) or {}
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    if not _workflow_has_gating_trigger(data):
        return False
    for run in _iter_run_steps(data):
        if _run_step_invokes_tool(run, run_pattern):
            return True
    return False


def _workflow_has_gating_trigger(workflow: dict) -> bool:
    # PyYAML parses unquoted `on:` keys as boolean True (YAML 1.1 behavior).
    on_cfg = workflow.get(True, workflow.get("on"))
    pr_events = {"pull_request", "pull_request_target", "merge_group"}
    if isinstance(on_cfg, str):
        if on_cfg in pr_events:
            return True
        if on_cfg == "push":
            # No branch filters means push applies to all branches, including default.
            return _push_targets_default_branch(None)
        return False
    if isinstance(on_cfg, list):
        events = {event for event in on_cfg if isinstance(event, str)}
        if events & pr_events:
            return True
        if "push" in events:
            # List form cannot carry push branch filters; treat as unconstrained push.
            return _push_targets_default_branch(None)
        return False
    if not isinstance(on_cfg, dict):
        return False
    event_names = {event for event in on_cfg if isinstance(event, str)}
    if event_names & pr_events:
        return True
    if "push" in on_cfg:
        return _push_targets_default_branch(on_cfg.get("push"))
    return False


def _push_targets_default_branch(push_cfg: object) -> bool:
    if not isinstance(push_cfg, dict):
        return True
    branches = push_cfg.get("branches")
    if branches is not None:
        return any(_targets_default_branch(v) for v in _as_str_list(branches))
    ignored = push_cfg.get("branches-ignore")
    if ignored is not None and any(_targets_default_branch(v) for v in _as_str_list(ignored)):
        return False
    return True


def _targets_default_branch(branch_pattern: str) -> bool:
    pattern = branch_pattern.strip()
    if not pattern:
        return False
    if pattern in {"main", "master", "refs/heads/main", "refs/heads/master", "*", "**"}:
        return True
    return "default_branch" in pattern


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _iter_run_steps(workflow: dict):
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str):
                yield run


def _run_step_invokes_tool(run_script: str, run_pattern: str) -> bool:
    for line in run_script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.search(run_pattern, stripped):
            return True
    return False
