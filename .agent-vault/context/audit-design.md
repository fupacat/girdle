---
type: context
watches:
  - path: src/girdle/audit.py
    symbol: run_audit
    hash: 5908a745e241e008ec03d81d532b1475578f2e54741c2007fb7852d775fcbbaf
stale: false
---

# `girdle audit` design

Raw source material for the rubric: the OKF vault's
`Agent-Ready Repository Design.md`, "Outline adopted for girdle" item 2 and
the detailed §2 self-audit caveat / "Refinement to girdle's planned
audit-subagent rubric" subsections - not duplicated here, this note only
covers girdle-specific implementation decisions.

## Decisions

**Top-level command, not a `scan --flag`/`ScanResult` field.** Every other
`ScanResult` field (`platform`, `hygiene`) is a deterministic fact - a live
API response, a local file's presence. `audit`'s output is a nondeterministic
LLM proposal (bucket classifications with rationale). Folding it into
`schema.py` would contradict that module's stated single-source-of-truth
claim for the *verification-infrastructure scoring model* specifically - the
independent architectural review verified that claim as sound, and this
keeps it that way. `notes` is the existing precedent for a fully independent
command group with its own concerns, unrelated to `ScanResult`.

**Extended `runner.run_check`, not `platform.py`'s `_run`.** Both existed
before this feature: `platform._run` is a bespoke, `gh`-specific subprocess
wrapper; `runner.run_check` already generalizes missing-binary + timeout
handling for arbitrary commands (used by `--run` tier-2 verification). Adding
optional `input: str | None` to `run_check` (to pipe the audit prompt via
stdin, avoiding CLI arg-length limits with large file content) was a smaller,
more honest extension than copying `platform._run`'s shape a third time. This
also closes a duplication the independent review flagged: before this
change, `runner.py` and `platform.py` had two competing, near-identical
subprocess helpers that never shared code.

**Reuses an already-authenticated agent CLI (`claude -p` by default), not
the Claude Agent SDK.** The SDK path (`claude-agent-sdk` / structured
outputs API) requires a separate `ANTHROPIC_API_KEY` and Anthropic API
billing - it cannot reuse an already-logged-in `claude` CLI session. That
would break the exact "girdle never manages credentials, reuses whatever the
user already authenticated via that tool's own CLI" stance `--platform`
established for `gh`. Confirmed via direct research before committing to
this design, not assumed.

**Two-layer JSON parsing, not a single `json.loads`.** `claude -p --output-format json` wraps the model's answer in an outer envelope; the
model's actual text response lives in a `result` field and must be parsed as
JSON again (the model was instructed to respond with pure JSON, but that's a
prompt instruction, not a guarantee). `parse_agent_output` reports a distinct
failure reason for each of the two parse layers, and skips one malformed
finding-array entry rather than failing the whole batch - the same
malformed-input tolerance pattern used elsewhere in girdle (e.g.
`hygiene.py`'s `_claude_sandbox_hook_configured` guarding `hooks`'s shape
after a successful JSON parse).

**`--agent-cmd` is an escape hatch, not a promise of full portability.**
Different agent CLIs (Codex, Copilot) have different headless-mode flags and
output shapes; girdle documents and defaults to one (`claude -p --output-format json`) and lets a user override the whole command, rather
than attempting to normalize output across every agent CLI's exact format.

**Never auto-applies anything.** Output is always a report for a human to
act on - migrating an instruction from prose to a lint rule or an agent hook
is a deliberate, reviewed action, not something `girdle audit` performs
itself.

## Consequences

- If the unmerged `copilot/add-agent-instructions-file-check` branch (adding
  a `check_agent_instructions` hygiene check with the same
  `AGENT_INSTRUCTIONS_LOCATIONS` tuple) lands, `audit.py`'s copy should be
  replaced with an import from `hygiene.py` rather than kept as a second,
  manually-synced copy.
- If Claude Code's `-p --output-format json` envelope shape changes,
  `parse_agent_output`'s outer-layer parsing breaks - this is an external
  contract girdle doesn't control, unlike everything else in its normal
  zero-auth checks.
