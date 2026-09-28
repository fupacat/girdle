---
type: decision
---

# Gitar is the sole automated CI-failure auto-fixer, not Gitar and Copilot both

## Context

Both Gitar and Copilot can auto-fix CI failures and review PRs. Running
both automatically risks two bots pushing competing fix commits to the
same branch, duplicate/conflicting findings to triage, and doubled
Actions-minutes billing (Copilot code review consumes Actions minutes as
of mid-2026).

## Decision

Gitar is the sole automated reviewer and CI-failure auto-fixer, chosen for
observed consistency across this repo's PR history. Copilot's reviewer
stays available as a manual, on-demand second opinion, never a second
automated path. Enabled repo-wide via a Mergify rule that labels every
non-Dependabot PR `gitar-managed` on open (Dependabot excluded: a Gitar
fix commit pushed onto a Dependabot branch would make Dependabot stop
auto-managing it, the same reason Mergify's own `update` action is avoided
there too). Gitar's own auto-merge is deliberately never configured (no
`.gitar/config/merge.md`), so it can't arm a second merge path competing
with Mergify's queue.

## Alternatives considered

- **Both Gitar and Copilot auto-fixing** - rejected, see Context.
- **Gradual auto-apply ramp-up** (suggestion-mode first, then enable
  auto-commit for specific failure types) - explicitly rejected in favor
  of full automation from the start: "we're empowering gitar to autofix
  PR issues... full automation is the goal."

## Consequences

- Confirmed working live: Gitar found and fixed its own bugs across
  multiple PRs this session (e.g. PR #77's `reproducibility` miscategorization,
  PR #68's quarantine-gating bug), including once racing directly against
  a concurrent human/Claude Code fix for the same finding (PR #68) -
  reconciled via rebase, no data lost.
- A separate, unresolved gap: Gitar can approve a PR while its own
  required `Gitar` status check silently never posts on the current head
  SHA (confirmed PR #90) - not fixed, just documented and worked around
  with a same-SHA re-trigger mention.

## Reference

Full rationale and the label-rule mechanics:
[[.agent-vault/ci/merge-pipeline|merge-pipeline]] (watches `.mergify.yml`).
`.gitar/config/`, `.gitar/review/` (in-repo Gitar configuration, kept
alongside code rather than dashboard-only).
