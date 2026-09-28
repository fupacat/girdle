---
type: decision
---

# Agent sandbox bootstrap: three tool-specific sub-checks, each honest about what it can't verify

## Context

`check_agent_sandbox_bootstrap` detects whether an AI coding agent's
isolated execution sandbox gets the same local enforcement (`pre-commit install`) a human contributor gets, across three tools with genuinely
different setup mechanisms.

## Decision

- **Copilot**: match the job-key pattern (`^\s*copilot-setup-steps:`),
  not a substring - GitHub only picks up `.github/workflows/copilot-setup-steps.yml`
  if the job is named exactly `copilot-setup-steps`; a substring check
  would false-positive on a comment merely mentioning the tool.
- **Claude Code**: recommend `SessionStart`, never `WorktreeCreate` -
  `WorktreeCreate` *replaces* Claude Code's default worktree creation
  entirely (a custom hook must recreate it or worktree creation breaks),
  fundamentally unlike Copilot's additive setup workflow. `SessionStart`
  is the safe additive equivalent. An existing `WorktreeCreate` still
  counts as evidence, but the check's recommendation text must never
  suggest adding one just for this - an earlier version did, and was
  corrected after review.
- **Codex**: only the local desktop `.codex/` environment is checked;
  cloud environments (configured entirely through OpenAI's web UI) are
  invisible to a local file scan and deliberately not checked, rather
  than risk a dishonest false-ABSENT. Since Codex's docs never specify an
  exact filename inside `.codex/`, the check requires the directory to
  exist *and be non-empty* - the most specific honest claim available.

## Alternatives considered

- **A single generalized check across all three tools** - rejected; each
  tool's setup mechanism has a genuinely different trust boundary (a
  fixed workflow job name vs. a hook-semantics distinction vs. a
  can't-verify-cloud-config limitation), not amenable to one shared
  pattern.

## Consequences

- If Claude Code's hook semantics change (e.g. `WorktreeCreate` becomes
  additive), this decision goes stale relative to its own reasoning even
  if the watched code hash doesn't change - re-verify the hooks docs
  before trusting the "never recommend WorktreeCreate" call as current.
- If OpenAI documents an exact filename inside `.codex/`, the
  non-emptiness check should tighten to that filename specifically, the
  same precision the other two sub-checks already have.

## Reference

Full design detail:
[[.agent-vault/context/agent-sandbox-bootstrap-design|agent-sandbox-bootstrap-design]]
(watches `src/girdle/hygiene.py#check_agent_sandbox_bootstrap`).
