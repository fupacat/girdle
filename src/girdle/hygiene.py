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
AGENT_INSTRUCTIONS_LOCATIONS = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")

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


def check_agent_instructions(root: Path) -> CategoryResult:
    found = _first_existing(root, AGENT_INSTRUCTIONS_LOCATIONS)
    if found is None:
        return CategoryResult(
            Tier.ABSENT, reason="no agent instructions file found",
            recommendation=(
                "Add an AGENTS.md describing build/test commands and code-style "
                "conventions so agentic tools (Claude Code, Copilot, Codex, Cursor, "
                "and others) can operate effectively in this repo."
            ),
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
    return HygieneResult(
        checks={
            "editorconfig": check_editorconfig(root),
            "gitattributes": check_gitattributes(root),
            "precommit": check_precommit(root),
            "gitignore": check_gitignore(root, languages),
            "codeowners": check_codeowners(root),
            "agent_instructions": check_agent_instructions(root),
            "readme": check_readme(root),
            "contributing": check_contributing(root),
        }
    )
