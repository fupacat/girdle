"""Repo-wide hygiene checks: .editorconfig, .gitattributes, .gitignore,
CODEOWNERS, README, CONTRIBUTING. Language-agnostic - these don't belong to
any one ecosystem's four categories (tests/lint/reproducibility/ci_gating),
so they're reported as their own top-level section, same pattern as
platform.py, and for the same reason: it's a different kind of signal, not
blended into overall_min/overall_avg.

All checks are local file reads only - same zero-auth trust model as the
verification-infra detectors, unlike platform.py's live API call, so this
runs as part of every default scan with no opt-in flag.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from girdle.tiers import CategoryResult, Tier


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# language -> gitignore patterns a healthy repo in that ecosystem usually has.
# Checked as substrings of .gitignore lines, not exact matches, since authors
# write these many different ways (node_modules/, /node_modules, **/node_modules).
EXPECTED_IGNORE_PATTERNS = {
    "python": ["__pycache__", ".venv"],
    "javascript": ["node_modules"],
    "typescript": ["node_modules"],
    "rust": ["target"],
    "java": ["target", "build", ".gradle"],
    "dotnet": ["bin", "obj"],
}

GITIGNORE = ".gitignore"

README_NAMES = ("README.md", "README.rst", "README.txt", "README")
CONTRIBUTING_LOCATIONS = (
    "CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md",
)
CODEOWNERS_LOCATIONS = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")

MIN_NONTRIVIAL_CHARS = 40


@dataclass
class HygieneResult:
    checks: dict[str, CategoryResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {name: cat.to_dict() for name, cat in self.checks.items()}


def _first_existing(root: Path, candidates: tuple[str, ...]) -> Path | None:
    for name in candidates:
        path = root / name
        if path.exists():
            return path
    return None


def check_editorconfig(root: Path) -> CategoryResult:
    path = root / ".editorconfig"
    if not path.exists():
        return CategoryResult(
            Tier.ABSENT, reason="no .editorconfig found",
            recommendation=(
                "Add a .editorconfig to enforce consistent indentation/line-endings "
                "across editors."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[".editorconfig"])


def check_gitattributes(root: Path) -> CategoryResult:
    path = root / ".gitattributes"
    if not path.exists():
        return CategoryResult(
            Tier.ABSENT, reason="no .gitattributes found",
            recommendation=(
                "Add a .gitattributes file (e.g. `* text=auto`) for consistent line "
                "endings across platforms."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[".gitattributes"])


def check_precommit(root: Path) -> CategoryResult:
    path = root / ".pre-commit-config.yaml"
    if not path.exists():
        return CategoryResult(
            Tier.ABSENT, reason="no .pre-commit-config.yaml found",
            recommendation=(
                "Add a .pre-commit-config.yaml to run fast local checks before commits."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[".pre-commit-config.yaml"])


COPILOT_SETUP_STEPS = ".github/workflows/copilot-setup-steps.yml"
CLAUDE_SETTINGS = ".claude/settings.json"


def _copilot_setup_steps_configured(root: Path) -> bool:
    copilot_setup = root / ".github" / "workflows" / "copilot-setup-steps.yml"
    if not copilot_setup.exists():
        return False
    text = _read_text(copilot_setup) or ""
    # A job KEY, not just the substring anywhere - a comment or doc
    # mentioning "copilot-setup-steps" must not count as configured.
    return bool(re.search(r"(?m)^\s*copilot-setup-steps:", text))


def _claude_sandbox_hook_configured(root: Path) -> bool:
    claude_settings = root / ".claude" / "settings.json"
    if not claude_settings.exists():
        return False
    try:
        data = json.loads(_read_text(claude_settings) or "{}")
    except ValueError:
        data = {}
    # `hooks` in valid, parseable JSON can still be the wrong shape
    # (null, a list, a string) - guard the type before .get()'ing into
    # it, the same malformed-input tolerance the JSON-parse guard above
    # already aims for, just one level deeper.
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return False
    # SessionStart is the safe, additive match: it runs alongside
    # Claude Code's default worktree creation, same as copilot-setup-
    # steps.yml runs alongside a job. WorktreeCreate is NOT equivalent -
    # per Claude Code's docs it *replaces* the default `git worktree`
    # step entirely (the hook itself must create the worktree and print
    # its path as stdout's last line), so it's still counted as
    # evidence a custom creator could fold pre-commit setup into, but
    # it must never be the thing we recommend adding.
    return bool(hooks.get("SessionStart") or hooks.get("WorktreeCreate"))


def check_agent_sandbox_bootstrap(root: Path, precommit: CategoryResult) -> CategoryResult:
    """Whether an agent's isolated execution sandbox (GitHub Copilot coding
    agent, Claude Code cloud/worktree sessions) gets wired into the same
    local enforcement pre-commit gives a human contributor. Conditional on
    pre-commit itself being configured - same shape as scan.py's coverage
    gate check: nothing to bootstrap into an empty sandbox otherwise, so
    checking this in isolation would be noise, not a finding.

    OpenAI Codex's environment setup script is deliberately not checked -
    it's configured through OpenAI's own web UI, not a repo-committed file,
    so it's invisible to a local file scan and would be dishonest to score.
    """
    if precommit.tier != Tier.CONFIGURED:
        return CategoryResult(
            Tier.ABSENT,
            reason=(
                "no .pre-commit-config.yaml to bootstrap into an agent's sandbox "
                "in the first place"
            ),
        )

    evidence = []
    if _copilot_setup_steps_configured(root):
        evidence.append(COPILOT_SETUP_STEPS)
    if _claude_sandbox_hook_configured(root):
        evidence.append(CLAUDE_SETTINGS)

    if not evidence:
        return CategoryResult(
            Tier.ABSENT,
            reason=(
                "pre-commit is configured but not wired into any agent sandbox bootstrap - "
                "no copilot-setup-steps job or Claude Code SessionStart/WorktreeCreate hook "
                "found"
            ),
            recommendation=(
                "Add .github/workflows/copilot-setup-steps.yml (job named "
                "`copilot-setup-steps`) running your dependency install then "
                "`pre-commit install`, or a `SessionStart` hook in .claude/settings.json "
                "doing the same (a custom `WorktreeCreate` hook can also run it, but only "
                "if it also creates the worktree itself and prints its path - that hook "
                "replaces Claude Code's default worktree creation rather than running "
                "alongside it, so don't add one just for this), so an agent's isolated "
                "sandbox gets the same local enforcement a human contributor's "
                "`pre-commit install` gives them."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=evidence)


def check_gitignore(root: Path, languages: set[str]) -> CategoryResult:
    path = root / GITIGNORE
    if not path.exists():
        return CategoryResult(
            Tier.ABSENT, reason=f"no {GITIGNORE} found",
            recommendation=f"Add a {GITIGNORE}.",
        )
    content = _read_text(path) or ""
    missing_patterns: list[str] = []
    for language in sorted(languages):
        for pattern in EXPECTED_IGNORE_PATTERNS.get(language, []):
            if pattern not in content and pattern not in missing_patterns:
                missing_patterns.append(pattern)
    if missing_patterns:
        return CategoryResult(
            Tier.ABSENT,
            evidence=[GITIGNORE],
            reason=f"missing common patterns for this stack: {', '.join(missing_patterns)}",
            recommendation=(
                f"Add {', '.join(missing_patterns)} to {GITIGNORE} for your "
                f"{'/'.join(sorted(languages)) or 'detected'} stack."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[GITIGNORE])


def check_codeowners(root: Path) -> CategoryResult:
    found = _first_existing(root, CODEOWNERS_LOCATIONS)
    if found is None:
        return CategoryResult(
            Tier.ABSENT, reason="no CODEOWNERS file found",
            recommendation=(
                "Add a CODEOWNERS file (repo root, .github/, or docs/) to route "
                "review requests automatically."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[str(found.relative_to(root))])


def check_readme(root: Path) -> CategoryResult:
    found = _first_existing(root, README_NAMES)
    if found is None:
        return CategoryResult(
            Tier.ABSENT, reason="no README found",
            recommendation="Add a README.md describing the project, setup, and usage.",
        )
    content = (_read_text(found) or "").strip()
    if len(content) < MIN_NONTRIVIAL_CHARS:
        return CategoryResult(
            Tier.ABSENT,
            evidence=[str(found.relative_to(root))],
            reason="README exists but appears to be an empty stub",
            recommendation="Flesh out the README: project description, setup, and usage.",
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[str(found.relative_to(root))])


def check_contributing(root: Path) -> CategoryResult:
    found = _first_existing(root, CONTRIBUTING_LOCATIONS)
    if found is None:
        return CategoryResult(
            Tier.ABSENT, reason="no CONTRIBUTING file found",
            recommendation=(
                "Add a CONTRIBUTING.md describing how to set up, test, and submit "
                "changes."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[str(found.relative_to(root))])


def build_hygiene(root: Path, languages: set[str]) -> HygieneResult:
    precommit = check_precommit(root)
    return HygieneResult(
        checks={
            "editorconfig": check_editorconfig(root),
            "gitattributes": check_gitattributes(root),
            "precommit": precommit,
            "agent_sandbox_bootstrap": check_agent_sandbox_bootstrap(root, precommit),
            "gitignore": check_gitignore(root, languages),
            "codeowners": check_codeowners(root),
            "readme": check_readme(root),
            "contributing": check_contributing(root),
        }
    )
