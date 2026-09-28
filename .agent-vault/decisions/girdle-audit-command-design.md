---
type: decision
---

# `girdle audit`: a separate command group, not a `ScanResult` field

## Context

`girdle audit` uses an LLM to review agent-instruction files (AGENTS.md/
CLAUDE.md/etc.) and propose bucket classifications with rationale -
fundamentally different from every other `ScanResult` field, which is a
deterministic fact (a live API response, a local file's presence).

## Decision

Top-level command, not a `scan --flag`/`ScanResult` field - folding it in
would contradict `schema.py`'s single-source-of-truth claim for the
*verification-infrastructure scoring model* specifically, which an
independent architectural review verified as sound. `notes` is the
existing precedent for a fully independent command group unrelated to
`ScanResult`. Output is always a report for a human to act on; the command
never auto-applies anything. Reuses an already-authenticated agent CLI
(`claude -p` by default, overridable via `--agent-cmd`) rather than the
Claude Agent SDK, to preserve the "girdle never manages credentials"
stance `--platform` established for `gh`.

## Alternatives considered

- **A `ScanResult` field / `scan --audit` flag** - rejected, see Decision.
- **Claude Agent SDK instead of the CLI** - rejected: requires a separate
  `ANTHROPIC_API_KEY` and Anthropic API billing, can't reuse an
  already-logged-in `claude` CLI session. Confirmed via direct research
  before committing, not assumed.
- **`platform.py`'s bespoke `_run` subprocess wrapper** - rejected in
  favor of extending `runner.run_check` (already generalizes missing-
  binary + timeout handling, used by `--run` tier-2 verification) with
  optional stdin input - closed a duplication an independent review had
  flagged between `runner.py` and `platform.py`.
- **Normalizing output across every agent CLI's format** - rejected;
  `--agent-cmd` is documented as an escape hatch, not a portability
  promise, since Codex/Copilot have different headless-mode flags/shapes.

## Consequences

- Two-layer JSON parsing is required (`claude -p --output-format json`
  wraps the model's answer in an outer envelope) - an external contract
  girdle doesn't control; if Claude Code's envelope shape changes, the
  outer-layer parsing breaks.
- If the unmerged `copilot/add-agent-instructions-file-check` branch lands,
  `audit.py`'s copy of `AGENT_INSTRUCTIONS_LOCATIONS` should become an
  import from `hygiene.py` rather than a second manually-synced copy.

## Reference

Full design detail: [[.agent-vault/context/audit-design|audit-design]]
(watches `src/girdle/audit.py#run_audit`).
