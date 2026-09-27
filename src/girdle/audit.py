"""Fresh-subagent prose audit of AGENTS.md-style instruction files.

Opt-in, external-agent-CLI-dependent, gracefully degrades to unavailable -
same trust-model shape as platform.py's live `gh` check, except the external
tool here is an agent CLI (default: `claude -p`) rather than `gh`. Every
other girdle check is a zero-auth, deterministic local file read; this one
shells out and parses a nondeterministic LLM response, so its output is
always a proposal to review, never applied automatically.

"Fresh subagent" specifically means a brand-new subprocess invocation with
no access to or memory of any existing conversation - never the current
session grading its own prose. LLM self-critique literature is consistently
negative on same-session self-review (self-preference bias, generator/
evaluator sharing failure modes), so this only counts as a real audit when
invoked as an independent process.

Reuses whatever agent CLI session is already authenticated (default:
`claude`), the same "girdle never manages credentials" stance --platform
takes with `gh auth login` - not the Claude Agent SDK/Anthropic API, which
would require a separate ANTHROPIC_API_KEY and billing surface girdle
doesn't own.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from girdle.hygiene import AGENT_INSTRUCTIONS_LOCATIONS
from girdle.runner import run_check

DEFAULT_AGENT_CMD = ["claude", "-p", "--output-format", "json"]
DEFAULT_TIMEOUT = 300

AUDIT_PROMPT_TEMPLATE = """\
You are auditing an AGENTS.md-style instruction file for an AI coding agent.
You are a fresh reviewer with no memory of writing this file - review it
adversarially, not charitably.

For each distinct instruction/rule in the file below, classify it into
exactly one bucket:

1. DETERMINISTIC TOOL EXISTS: a formatter, linter rule, .editorconfig,
   .gitattributes, or pre-commit hook already enforces this (or trivially
   could). Cite the SPECIFIC tool/config (e.g. "ruff rule E501",
   ".editorconfig indent_size", "pre-commit black hook").
2. AGENT HOOK FITS: no repo-level deterministic tool applies, but an agent
   tool hook (e.g. a PostToolUse gate) could mechanically enforce it. Name
   the specific hook mechanism. Note this is non-portable across agent CLIs.
3. STAYS IN PROSE: neither applies - a judgment call, a fact true today but
   not permanently, or below "production incident" severity. Do not
   recommend migrating it.

Respond with ONLY a JSON array, no other text, no markdown code fences,
matching exactly this schema:
[
  {{"excerpt": "verbatim quoted instruction, <=200 chars",
   "bucket": 1,
   "rationale": "one or two sentences",
   "citation": "specific tool/config/hook name, or empty string for bucket 3"}}
]
("bucket" is 1, 2, or 3 - an integer, not the string shown above)

FILE: {path}
---
{content}
---
"""


@dataclass
class AuditFinding:
    excerpt: str
    bucket: int
    rationale: str
    citation: str


@dataclass
class AuditResult:
    available: bool
    reason: str | None = None
    target: str = ""
    findings: list[AuditFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        if not self.available:
            return {"available": False, "reason": self.reason, "target": self.target}
        return {
            "available": True,
            "target": self.target,
            "findings": [
                {
                    "excerpt": f.excerpt,
                    "bucket": f.bucket,
                    "rationale": f.rationale,
                    "citation": f.citation,
                }
                for f in self.findings
            ],
        }


def _invoke_agent(prompt: str, agent_cmd: list[str], cwd: Path, timeout: int):
    return run_check(agent_cmd, cwd=cwd, timeout=timeout, input=prompt)


def parse_agent_output(stdout: str) -> tuple[list[AuditFinding] | None, str | None]:
    """Two-layer parse: `claude -p --output-format json` wraps the model's
    answer in an outer envelope with a `result` field holding the model's
    raw text, which must itself be parsed as JSON - two independent failure
    points, each reported with a distinct reason rather than crashing.
    """
    try:
        outer = json.loads(stdout)
    except json.JSONDecodeError as e:
        return None, f"agent output was not valid JSON: {e}"
    result_text = outer.get("result") if isinstance(outer, dict) else None
    if not isinstance(result_text, str):
        return None, "agent output missing string result field"
    try:
        inner = json.loads(result_text)
    except json.JSONDecodeError as e:
        return None, f"agent result was not valid JSON (model ignored format instruction): {e}"
    if not isinstance(inner, list):
        return None, "agent result JSON was not a list of findings"
    findings = []
    for item in inner:
        try:
            findings.append(
                AuditFinding(
                    excerpt=item["excerpt"],
                    bucket=int(item["bucket"]),
                    rationale=item["rationale"],
                    citation=item.get("citation", ""),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip one malformed entry, don't fail the whole batch
    return findings, None


def audit_file(path: Path, repo_root: Path, agent_cmd: list[str], timeout: int) -> AuditResult:
    target = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
    exe = agent_cmd[0]
    if shutil.which(exe) is None:
        return AuditResult(available=False, reason=f"{exe} not found on PATH", target=target)
    if not path.is_file():
        return AuditResult(available=False, reason=f"{target} not found", target=target)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return AuditResult(available=False, reason=f"failed to read {target}: {e}", target=target)
    prompt = AUDIT_PROMPT_TEMPLATE.format(path=target, content=content)
    outcome = _invoke_agent(prompt, agent_cmd, cwd=repo_root, timeout=timeout)
    if not outcome.ran:
        return AuditResult(available=False, reason=outcome.reason, target=target)
    if not outcome.passed:
        return AuditResult(
            available=False, reason=outcome.reason or "agent invocation failed", target=target
        )
    findings, error = parse_agent_output(outcome.stdout)
    if error is not None:
        return AuditResult(available=False, reason=error, target=target)
    return AuditResult(available=True, target=target, findings=findings or [])


def discover_instruction_files(repo_root: Path) -> list[Path]:
    return [
        repo_root / name for name in AGENT_INSTRUCTIONS_LOCATIONS if (repo_root / name).is_file()
    ]


def run_audit(
    repo_root: Path,
    files: list[Path] | None = None,
    agent_cmd: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[AuditResult]:
    targets = files if files else discover_instruction_files(repo_root)
    cmd = agent_cmd or DEFAULT_AGENT_CMD
    return [audit_file(p, repo_root, cmd, timeout) for p in targets]
