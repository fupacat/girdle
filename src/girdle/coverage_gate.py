"""Detects whether coverage is enforced as a PR-scoped (diff/patch) gate in
CI, not just run and reported. Deliberately conditional on both "coverage"
and "ci_gating" already being configured for the same ecosystem: a gate is
meaningless with no coverage tool to gate, and meaningless with no CI to
enforce it in - checking either half in isolation would produce a
confusing, context-free finding.

Detection is entirely language-agnostic (unlike coverage/ci_gating
detection itself): Codecov, Coveralls, and diff-cover all live in the same
CI workflow files regardless of which ecosystem's code they're gating, so
this lives once in scan.py rather than duplicated per detector.

Scoped honestly to what's pattern-matchable:
- Codecov: a codecov.yml/.codecov.yml file plus an upload step in CI.
  Presence of "patch" in the config is noted as a bonus specificity signal,
  not required - Codecov's project-level status is also a real, if weaker,
  gate.
- Coveralls: a coveralls action/package invocation in CI.
- diff-cover: a `diff-cover` invocation in CI, with --fail-under extracted
  if present.
- SonarCloud/SonarQube: a sonar-project.properties (or .sonarcloud.properties)
  file plus a Sonar scan step/CLI invocation in CI. Weaker confirmation than
  Codecov's patch section by nature, not by laziness: "Coverage on New Code"
  is Sonar's *default* quality-gate condition, not something declared in the
  repo's own files - presence of Sonar plus a coverage report-path key
  (`...reportPaths`) is the strongest signal obtainable from static files
  alone; whether that gate condition is still enabled is Sonar-side state
  this module can't see.

Not attempted: a fully bespoke, homegrown diff-coverage script has no
stable signature to match against - reported as not found rather than
guessed at from generic git-diff/coverage co-occurrence.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text

CODECOV_UPLOAD_PATTERN = re.compile(r"codecov/codecov-action|codecov\.io/bash|\bcodecov\b")
COVERALLS_PATTERN = re.compile(r"coverallsapp/github-action|\bcoveralls\b")
DIFF_COVER_PATTERN = re.compile(r"diff-cover\b[^\n]*")
FAIL_UNDER_PATTERN = re.compile(r"--fail-under[=\s](\d+)")
SONAR_CI_PATTERN = re.compile(
    r"sonarcloud-github-action|sonarqube-scan-action|sonarsource/sonar-scan-action|"
    r"\bsonar-scanner\b",
    re.IGNORECASE,
)
SONAR_CONFIG_NAMES = ("sonar-project.properties", ".sonarcloud.properties")
SONAR_REPORT_PATH_PATTERN = re.compile(r"reportPaths", re.IGNORECASE)

CI_FILE_CANDIDATES = ("*.yml", "*.yaml")


def _ci_texts(root: Path) -> list[tuple[str, str]]:
    """(label, content) for every CI config file girdle's ci_gating checks
    already look at, so this reuses the same file set rather than a new
    detection surface.
    """
    texts = []
    wf_dir = root / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.y*ml"):
            texts.append((f".github/workflows/{wf.name}", read_text(wf) or ""))
    for name in (".gitlab-ci.yml", "azure-pipelines.yml"):
        p = root / name
        if p.exists():
            texts.append((name, read_text(p) or ""))
    return texts


def _first_existing_name(root: Path, names: tuple[str, ...]) -> str | None:
    for name in names:
        if (root / name).exists():
            return name
    return None


def _codecov_gate(root: Path, codecov_cfg: str | None, label: str, text: str) -> str | None:
    if not codecov_cfg or not CODECOV_UPLOAD_PATTERN.search(text):
        return None
    cfg_text = read_text(root / codecov_cfg) or ""
    if re.search(r"patch\s*:", cfg_text):
        return f"Codecov patch-coverage gate ({codecov_cfg} + {label})"
    return f"Codecov coverage tracking ({codecov_cfg} + {label}), patch status not confirmed"


def _sonar_gate(root: Path, sonar_cfg: str | None, label: str, text: str) -> str | None:
    if not sonar_cfg or not SONAR_CI_PATTERN.search(text):
        return None
    cfg_text = read_text(root / sonar_cfg) or ""
    if SONAR_REPORT_PATH_PATTERN.search(cfg_text):
        return (
            f"SonarCloud/SonarQube with a coverage report configured "
            f"({sonar_cfg} + {label}); 'Coverage on New Code' is Sonar's "
            "default quality gate but its current on/off state isn't "
            "visible in repo files"
        )
    return (
        f"SonarCloud/SonarQube scan found ({sonar_cfg} + {label}), but no "
        "coverage report path configured - coverage likely isn't being "
        "analyzed at all"
    )


def _diff_cover_gate(label: str, text: str) -> str | None:
    match = DIFF_COVER_PATTERN.search(text)
    if not match:
        return None
    fail_under = FAIL_UNDER_PATTERN.search(match.group(0))
    if fail_under:
        return f"diff-cover gate, --fail-under={fail_under.group(1)} ({label})"
    return f"diff-cover invoked without --fail-under ({label}) - not actually enforcing anything"


def _gate_in_text(
    root: Path, codecov_cfg: str | None, sonar_cfg: str | None, label: str, text: str
) -> str | None:
    return (
        _codecov_gate(root, codecov_cfg, label, text)
        or (f"Coveralls coverage tracking ({label})" if COVERALLS_PATTERN.search(text) else None)
        or _sonar_gate(root, sonar_cfg, label, text)
        or _diff_cover_gate(label, text)
    )


def detect_gate(root: Path) -> str | None:
    """Returns an evidence string describing the detected gate mechanism,
    or None if no known gate signature was found in CI config.
    """
    codecov_cfg = _first_existing_name(root, ("codecov.yml", ".codecov.yml"))
    sonar_cfg = _first_existing_name(root, SONAR_CONFIG_NAMES)

    for label, text in _ci_texts(root):
        gate = _gate_in_text(root, codecov_cfg, sonar_cfg, label, text)
        if gate:
            return gate

    return None
