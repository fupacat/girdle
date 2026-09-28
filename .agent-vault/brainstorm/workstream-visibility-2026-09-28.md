---
type: brainstorm
---

# Workstream visibility: labels + one Project, not per-feature boards

Checkpoint of a separate discussion from the same session as
[[.agent-vault/brainstorm/dashboard-scoring-tiers-2026-09-28|dashboard-scoring-tiers-2026-09-28]] -
kept as its own note deliberately, not folded into that one, since it's
a distinct initiative (issue/PR workflow visibility, not the dashboard
scoring model) that happened to come up while working the same session.

## Where this started

Prompted by watching the dependency-chain-of-issues pattern (#72 and its
sub-issues) actually run this session: is there a better way to see
status of a collection of issues "as they flow" than reading the vault
backlog note or asking in chat?

## Milestones: ruled out quickly

Just a closed/total issue count with a due date - no concept of
dependency order at all. Wouldn't show anything the vault backlog
checklist doesn't already show better.

## Live custom kanban page: considered, not chosen

Reusing girdle's existing GitHub Pages dashboard-publishing pattern (a
scheduled workflow emits a JSON snapshot, a static page renders it) was
floated as a way to get an actually-live, actually-autonomous board that
*could* render the dependency graph GitHub Projects can't. Rejected in
favor of the lighter option below - real build effort (new workflow logic

- a whole rendering layer to build and maintain) for a "fluff" feature,
  when a much cheaper option gets most of the value.

Also ruled out: a Claude Artifact kanban. Keeping it live would mean
either embedding a GitHub token client-side (bad practice) or manually
refreshing it via `ArtifactData` on some cadence - not actually live,
and polling on a timer for something event-driven is exactly the
wasteful pattern to avoid.

## Decision: labels + one Project with saved views

Chosen direction, combining two native GitHub mechanisms rather than
building anything custom:

**Labels** (`status:blocked`, `status:ready`, `status:blocker`) - a
text-based stand-in for the one thing GitHub Projects still can't do:
render the dependency relationship itself. Verified before assuming:
GitHub Projects v2 has no native blocked-by graph visualization as of
2026 (open, unshipped community feature request). The label pair doesn't
draw an arrow, but it spells the relationship out per-card, which is
most of the value for far less build effort than a custom graph
renderer.

**One Project for the whole repo, not one board per feature/initiative.**
This matches how GitHub actually redesigned Projects v2 - a single item
living in one place, sliced into multiple filtered/grouped *views*
(board/table/roadmap), replacing the older "physical board per thing"
model precisely because it scales better and doesn't fragment status
reporting. Concrete reasons this fits girdle specifically:

- Cross-initiative reality already exists - issue #14 (a pre-existing,
  unrelated issue) got swept into the same auto-assignment flow as the
  dashboard-scoring chain (#72) this session. A per-feature board would
  have nowhere natural to put that.
- Zero new ceremony per feature - a saved view is just a filter/group;
  a new physical board means new setup (and re-wiring automation to
  target it) every time.
- The automation stays simple - one Project ID to write into, not
  per-initiative routing logic.

**No separate "Initiative" field needed.** [Project #3](https://github.com/users/fupacat/projects/3)
(created directly, linked to the repo) already has a **built-in**
`Parent issue` field - discovered while listing the project's default
fields, not assumed - which auto-reflects each issue's tracking-parent
relationship (the same native sub-issue mechanism #72/#105 already use)
with zero automation required. One less thing to keep in sync.

**`Status` field extended, not duplicated.** Every new Project already
ships a default `Status` single-select field (`Todo`/`In Progress`/`Done`) -
`"Status"` is a reserved name, `field-create` refuses a duplicate.
Extended the existing field's options instead, via
`updateProjectV2Field`'s `singleSelectOptions` (a full replacement, safe
here since the project had zero items yet): `Blocked`, `Ready`,
`In Progress`, `In Review`, `Done`.

## Implementation, filed as tickets

[Issue #105](https://github.com/fupacat/girdle/issues/105) (tracking,
same shape as #72) with two sequenced sub-issues (both extend
`.github/workflows/auto-assign-copilot.yml`, sequenced to avoid two
Copilot sessions touching the same file concurrently rather than a hard
logical dependency):

1. [#106](https://github.com/fupacat/girdle/issues/106) - status labels,
   reusing #85's existing `blockedBy` computation plus a new `blocking`
   walk for the `status:blocker` case
1. [#107](https://github.com/fupacat/girdle/issues/107) - Project board
   sync, richer new logic (PR-linkage-derived `In Progress`/`In Review`/
   `Done` states, not just the blocked/ready computation alone)

GitHub-object setup (the Project itself, its fields, the three labels)
was done directly rather than routed through a Copilot issue - this is
GitHub metadata/object creation, not repo code, same category as the
issue-filing and assignment work done directly all session.

## Open, not yet resolved

- Saved views (grouped/filtered by `Parent issue`, by `Status`) are a
  one-time manual Project UI setup, not automated - not yet actually
  configured, just planned.
- Whether Project-board tracking should cover *every* open issue
  (current design, matching #85's own repo-wide scope) or be scoped down
  to only issues under an active dependency chain - not revisited since
  the earlier, similar question about #85's own scope was left open too.

## Related

- [[.agent-vault/brainstorm/dashboard-scoring-tiers-2026-09-28|dashboard-scoring-tiers-2026-09-28]] -
  the initiative whose #72 chain prompted this discussion; kept separate
  per this note's own reasoning about not conflating initiatives.
- [[.agent-vault/context/dashboard-pillars-backlog|dashboard-pillars-backlog]] -
  the sibling backlog-style note for the other initiative; this note
  doesn't have one of its own since the scope here is small enough (one
  tracking issue, two sub-issues) not to need a separate living checklist.
