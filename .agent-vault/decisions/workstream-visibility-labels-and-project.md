---
type: decision
---

# Workstream visibility: status labels + one Project, not per-feature boards

## Context

The dependency-chain-of-issues pattern (issue #72 and its sub-issues) had
no way to see status of the whole collection "as it flows" other than
reading a vault note or asking in chat.

## Decision

Three labels (`status:blocked`, `status:ready`, `status:blocker`) applied
by automation, plus **one Project for the whole repo** (not one board per
feature/initiative), with the built-in `Status` field extended to a
5-state lifecycle (Blocked/Ready/In Progress/In Review/Done) and saved
views sliced by the Project's built-in `Parent issue` field for
per-initiative grouping.

## Alternatives considered

- **Milestones** - rejected outright. Just a closed/total count with a due
  date, no dependency-order concept at all.
- **A custom, live GitHub-Pages-published kanban** (reusing girdle's
  existing dashboard-publishing pattern) - could have rendered an actual
  dependency graph, which nothing else here does, but real build effort
  (new workflow logic + a rendering layer to build and maintain) for what
  was explicitly a "fluff"/nice-to-have request. Rejected in favor of the
  cheaper option.
- **A Claude Artifact kanban** - rejected. Keeping it live would mean
  either embedding a GitHub token client-side or manually refreshing it on
  a timer, neither of which is genuinely live/autonomous.
- **One Project board per feature/initiative** ("Epic" boards) - rejected.
  GitHub redesigned Projects v2 specifically around one item living in one
  place sliced into multiple views, replacing the older physical-board-
  per-thing model. A per-feature board would also have nowhere natural to
  put issues that don't belong to any initiative (confirmed directly:
  issue #14, pre-existing and unrelated, got swept into the same
  auto-assignment flow as the dashboard-scoring chain).
- **A separate custom "Initiative" field** - rejected once discovered (not
  assumed) that Projects v2 already ships a built-in `Parent issue` field
  that reflects the same tracking-parent relationship for free.

## Consequences

- GitHub Projects v2 has no native blocked-by dependency graph
  visualization as of 2026 (open, unshipped community feature request) -
  the label pair is a deliberate text-based stand-in for the relationship,
  not a full substitute for a graph view.
- Project-board tracking currently covers every open issue (matching
  issue #85's own repo-wide scope), not just issues in an active
  dependency chain - left open whether that should be scoped down.

## Reference

Full reasoning:
[[.agent-vault/brainstorm/workstream-visibility-2026-09-28|workstream-visibility-2026-09-28]].
[Project #3](https://github.com/users/fupacat/projects/3), created and
linked directly (GitHub object setup, not code). Implementation:
`.github/workflows/auto-assign-copilot.yml` (issues #106, #107) - no
`context/`-type note watches this file yet.
