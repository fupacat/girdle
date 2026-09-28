"""Repo-wide hygiene checks: .editorconfig, .gitattributes, .gitignore,
CODEOWNERS, README, CONTRIBUTING. Language-agnostic - these don't belong to
any one ecosystem's scored categories (tests/lint/coverage/build/
reproducibility/ci_gating),
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
    except (OSError, UnicodeDecodeError):
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
DEPENDENCY_MONITORING_LOCATIONS = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.js",
    ".renovaterc.mjs",
    "renovate.json",
    "renovate.json5",
)

MIN_NONTRIVIAL_CHARS = 40
ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff")
BASE64_BLOB_RE = re.compile(
    r"(?<![A-Za-z0-9+/=])"
    r"(?:[A-Za-z0-9+/]{64,}={0,2})"
    r"(?![A-Za-z0-9+/=])"
)
HEX_BLOB_RE = re.compile(
    r"(?<![0-9A-Fa-f])"
    r"(?:0x)?[0-9A-Fa-f]{64,}"
    r"(?![0-9A-Fa-f])"
)
MANIPULATIVE_AI_DIRECTIVE_RE = re.compile(
    r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+instructions\b"
    r"|\b(?:reveal|print|leak|exfiltrate)\s+(?:the\s+|your\s+)?(?:system\s+prompt|developer\s+message|hidden\s+instructions?)\b"
    r"|\bdo\s+not\s+tell\s+the\s+user\b"
)


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


def discover_agent_instruction_files(root: Path) -> list[Path]:
    return [root / name for name in AGENT_INSTRUCTIONS_LOCATIONS if (root / name).is_file()]


def _excerpt(text: str, start: int, end: int, limit: int = 120) -> str:
    snippet = " ".join(text[max(0, start - 20):min(len(text), end + 20)].split())
    return snippet[:limit]


def find_agent_instruction_hazards(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in discover_agent_instruction_files(root):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        text = raw.decode("utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        if "\ufffd" in text and b"\xef\xbf\xbd" not in raw:
            findings.append({"path": rel, "kind": "invalid_utf8",
                             "reason": "contains bytes that are not valid UTF-8",
                             "evidence": "undecodable byte sequence"})

        seen_zero_width = sorted({f"U+{ord(ch):04X}" for ch in text if ch in ZERO_WIDTH_CHARS})
        if seen_zero_width:
            findings.append(
                {
                    "path": rel,
                    "kind": "invisible_unicode",
                    "reason": "contains zero-width or invisible Unicode characters",
                    "evidence": ", ".join(seen_zero_width),
                }
            )

        for kind, pattern, reason in (
            (
                "suspicious_base64_blob",
                BASE64_BLOB_RE,
                "contains an unusually long base64-like block in a prose instruction file",
            ),
            (
                "suspicious_hex_blob",
                HEX_BLOB_RE,
                "contains an unusually long hex-like block in a prose instruction file",
            ),
            (
                "manipulative_ai_directive",
                MANIPULATIVE_AI_DIRECTIVE_RE,
                (
                    "contains AI-directed override language inconsistent "
                    "with a normal instructions file"
                ),
            ),
        ):
            match = pattern.search(text)
            if match is None:
                continue
            if kind == "suspicious_base64_blob" and HEX_BLOB_RE.fullmatch(match.group(0)):
                continue
            findings.append(
                {
                    "path": rel,
                    "kind": kind,
                    "reason": reason,
                    "evidence": _excerpt(text, match.start(), match.end()),
                }
            )
    return findings


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
CODEX_DIR = ".codex"


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


def _codex_local_environment_configured(root: Path) -> bool:
    # OpenAI's docs (learn.chatgpt.com/docs/environments/local-environment)
    # say only that "Codex stores this configuration inside the .codex
    # folder at the root of your project" and that the generated file "can
    # [be] check[ed]... into your project's Git repository" - no exact
    # filename is documented, so this checks that the directory exists AND
    # holds something, rather than trusting a bare/empty .codex/ (which
    # could be a stale leftover or an unrelated tool reusing the name) the
    # way the Copilot and Claude sub-checks trust an actual job key or
    # hooks key, not just a file's mere existence. This is the *local*
    # desktop-app environment feature, distinct from Codex's cloud
    # environments (chatgpt.com/codex/settings/environments), which are
    # configured entirely through OpenAI's web UI and stay invisible to a
    # local file scan - that cloud path is deliberately not checked here.
    codex_dir = root / CODEX_DIR
    return codex_dir.is_dir() and any(codex_dir.iterdir())


def check_agent_sandbox_bootstrap(root: Path, precommit: CategoryResult) -> CategoryResult:
    """Whether an agent's isolated execution sandbox (GitHub Copilot coding
    agent, Claude Code cloud/worktree sessions, OpenAI Codex's local
    desktop environment) gets wired into the same local enforcement
    pre-commit gives a human contributor. Conditional on pre-commit itself
    being configured - same shape as scan.py's coverage gate check: nothing
    to bootstrap into an empty sandbox otherwise, so checking this in
    isolation would be noise, not a finding.

    Codex's *cloud* environment setup script is deliberately not checked -
    it's configured through OpenAI's own web UI
    (chatgpt.com/codex/settings/environments), not a repo-committed file,
    so it's invisible to a local file scan and would be dishonest to score.
    The local desktop environment (.codex/) is different and is checked.
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
    if _codex_local_environment_configured(root):
        evidence.append(CODEX_DIR)

    if not evidence:
        return CategoryResult(
            Tier.ABSENT,
            reason=(
                "pre-commit is configured but not wired into any agent sandbox bootstrap - "
                "no copilot-setup-steps job, Claude Code SessionStart/WorktreeCreate hook, "
                "or .codex/ local environment found"
            ),
            recommendation=(
                "Add .github/workflows/copilot-setup-steps.yml (job named "
                "`copilot-setup-steps`) running your dependency install then "
                "`pre-commit install`, a `SessionStart` hook in .claude/settings.json "
                "doing the same (a custom `WorktreeCreate` hook can also run it, but only "
                "if it also creates the worktree itself and prints its path - that hook "
                "replaces Claude Code's default worktree creation rather than running "
                "alongside it, so don't add one just for this), or a Codex local "
                "environment (ChatGPT desktop app settings -> .codex/) with a setup script "
                "that runs `pre-commit install`, so an agent's isolated sandbox gets the "
                "same local enforcement a human contributor's `pre-commit install` gives "
                "them."
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
    return CategoryResult(Tier.CONFIGURED, evidence=[found.relative_to(root).as_posix()])


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
            evidence=[found.relative_to(root).as_posix()],
            reason="README exists but appears to be an empty stub",
            recommendation="Flesh out the README: project description, setup, and usage.",
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[found.relative_to(root).as_posix()])


def check_agent_instructions(root: Path) -> CategoryResult:
    found = discover_agent_instruction_files(root)
    if not found:
        return CategoryResult(
            Tier.ABSENT, reason="no agent instructions file found",
            recommendation=(
                "Add an AGENTS.md describing build/test commands and code-style "
                "conventions so agentic tools (Claude Code, Copilot, Codex, Cursor, "
                "and others) can operate effectively in this repo."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[found[0].relative_to(root).as_posix()])


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
    return CategoryResult(Tier.CONFIGURED, evidence=[found.relative_to(root).as_posix()])


def check_dependency_monitoring(root: Path) -> CategoryResult:
    found = _first_existing(root, DEPENDENCY_MONITORING_LOCATIONS)
    if found is None:
        return CategoryResult(
            Tier.ABSENT, reason="no dependency monitoring config found",
            recommendation=(
                "Configure automated dependency updates (e.g. GitHub Dependabot or "
                "Renovate) to keep dependencies fresh and reduce security risk."
            ),
        )
    return CategoryResult(Tier.CONFIGURED, evidence=[found.relative_to(root).as_posix()])


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
            "agent_instructions": check_agent_instructions(root),
            "readme": check_readme(root),
            "contributing": check_contributing(root),
            "dependency_monitoring": check_dependency_monitoring(root),
        }
    )
