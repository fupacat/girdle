---
type: decision
---

# PRs move through checks, review, and repair as separate, non-overlapping phases

## Context

A day of driving roughly fifteen concurrent Copilot PRs through the merge
queue (2026-09-29, see the OKF vault note "Merge Queue Operations -
Mergify and Copilot Fan-Out Failure Modes") showed the same pattern
repeatedly: several things acting on one PR at once. CI, Gitar's review,
Copilot's reviewer, Gitar's CI auto-fix, the Copilot coding agent's own
pushes, master-sync merges, and Mergify's queue entry all raced each
other. Results: approvals dismissed by a later push and Mergify dequeuing
in the gap, red checks on reviews of code that was about to change,
speculative queue drafts burning full CI on PRs that were not settled,
and empty or half-finished PRs reaching the queue.

## Decision

Each PR is in exactly one phase at a time. Draft versus ready is the
mutual-exclusion signal, because Gitar already skips drafts and Mergify
already requires `-draft`.

1. **Checks (draft).** The author (Copilot) pushes; cheap checks run
   first (lint, `mdformat`, `yamllint`, Mergify config validation, notes
   and index checks), then the full suite. Nothing reviews a draft.
1. **Promote.** A workflow marks the PR ready only when every check is
   green, the diff is non-empty, and there is no conflict.
1. **Review (ready).** Gitar reviews once, on a head that will not
   change under it. Review runs only after all checks are done.
1. **Verdict.**
   - No blocking findings: the approval stands and the PR is eligible to
     queue.
   - Findings: the PR is converted back to draft and the findings are
     handed to the repair actor.
1. **Repair (draft).** Exactly one repair actor pushes fixes, then the PR
   returns to step 1. Repair is capped (two cycles), after which the PR is
   labelled `manual` for a human.

Queue entry requires all of: ready, approved on the current head, all
required checks green, no conflict, at least one changed file. Master is
merged into a PR once, at queue time, through the existing "Keep PRs up to
date" rule, not by the author proactively; the author merges master only
to resolve a real conflict.

## Consistency with existing decisions

- [[.agent-vault/decisions/gitar-as-sole-auto-fixer|gitar-as-sole-auto-fixer]]
  stands (Gitar is the sole automated reviewer and CI-failure auto-fixer): Gitar reviews and
  repairs; Copilot's reviewer stays a manual second opinion, and the
  Copilot coding agent is the author and conflict resolver, idle while a
  PR is in review, so the two never push at the same time.
- [[.agent-vault/decisions/minimal-discrete-pr-policy|minimal-discrete-pr-policy]]
  (PRs are scoped to one discrete change) governs how this is rolled out: one small PR per
  piece, in dependency order.
- [[.agent-vault/decisions/approval-flow-master-sync-no-review-reset|approval-flow-master-sync-no-review-reset]]
  (conflict-only master syncs must not reset approval state) is
  complemented, not replaced. Under this pipeline, repair pushes happen before approval and
  the single master sync happens at queue time, so
  `dismiss_stale_reviews_on_push` can stay on and the approval gap that
  motivated turning it off is much narrower. The ruleset choice is still
  a maintainer decision outside the repo.

## Alternatives considered

- **Keep reacting per incident with hotfixes** - rejected: each fix moved
  the bottleneck (empty PRs, then Gitar check, then Sonar, then config
  validity, then conflicts and approvals) without removing the
  simultaneous-actors cause.
- **Turn off stale-review dismissal only** - narrower and cheaper, but
  leaves reviews running against half-finished code and full CI running on
  unsettled PRs; it treats a symptom.
- **GitHub-native merge queue instead of Mergify** - already evaluated and
  rejected for other reasons, see the merge-pipeline note.

## Consequences and open items

- Each repair cycle re-runs the full suite, so the cycle cap and
  cancelling superseded runs matter for cost.
- Comments that hand findings to the Copilot coding agent only work from
  a user with write access; a workflow token comment is ignored (the same
  identity constraint behind the dedicated automation account work). Gitar
  as the repair actor avoids this for the common case.
- To verify before relying on it: whether Copilot's reviewer skips drafts
  (Gitar does), and that converting a queued PR to draft dequeues it
  cleanly.
- Rollout, in order: author-side pre-commit and no proactive master sync;
  CI cancel-in-progress and a fast-check-first split that keeps the
  required `test` check name; Gitar draft-skip re-enabled (a Gitar
  settings change, not in the repo); promote-when-green workflow;
  review-verdict workflow with the repair cap; queue-entry conditions
  tightened to match. Each is its own issue and PR.
