---
type: context
---

# Vault watch/freshness model - redesign in progress

Not committed scope yet - this is a live design discussion, recorded so
the reasoning survives across sessions. Other open problems (see
"Related problems" below) may pull this in a different direction once
scoped, so don't treat the proposal below as settled until it's actually
implemented and this note is updated to match.

## Problem found

`vault.py`'s `check()`/`current_hash()` freshness model (whole-file or
whole-symbol content hash, compared against a hash stored in the note's
frontmatter) goes stale from causes that have nothing to do with the note
being wrong:

- **Rebase staleness**: PR B's own diff never touches a watched file, so
  B correctly never updates the note watching it - but if PR A merges
  first and changes that file, B's hash comparison (evaluated against
  current master, not against B's own merge-base) now mismatches through
  no fault of B's.
- **Batch staleness**: `.mergify.yml`'s `default` queue has `batch_size: 3`
  (see [[.agent-vault/ci/merge-pipeline.md|merge-pipeline]]) - Mergify
  tests several queued PRs together on one speculative
  `mergify/merge-queue/*` branch. Any one of them touching a watched file
  without the others knowing produces the same spurious mismatch, just
  more often.
- **No reconcile path on CI**: `check()`'s only non-blocking path
  requires a "staged in this commit" concept (`_staged_files()` in
  [vault.py:342](../../src/girdle/vault.py:342)), which only exists
  during a local commit. `ci.yml`'s read-only run has no such concept, so
  a mismatch on a PR branch or a master push is unconditionally blocking.
  Since #128/#129 the step is skipped on `mergify/merge-queue/*` branches
  as a stop-gap, so batch staleness no longer blocks the queue; rebase
  staleness on a PR's own branch still does.

## Evidence (subagent investigation + direct correction, 2026-09-29)

**Correction: the first pass under-counted this by looking in the wrong
place.** A subagent search of `ci.yml` run logs alone found only 3
notes-check failures, all same-PR reconciliation lag, and concluded "zero
confirmed occurrences" of the rebase/batch theory. Eric flagged (and a
follow-up search of PR *review comments* - `gh api repos/fupacat/girdle/pulls/comments`, which the CI-log search never
looked at - confirms) that the real signal shows up as code review
comments from Gitar/Copilot calling out hash drift after a rebase or
conflict resolution, not as a CI-log failure line. Several such
occurrences exist; the clearest is on **PR #123**
(`mergify: batch the default queue`):

- Copilot review comment (2026-09-29T00:24:39Z): "The recorded watch hash
  for `.mergify.yml` is incorrect... most likely because the agent
  commit didn't run local hooks."
- Gitar-bot review comment (2026-09-29T01:34:39Z), titled **"Vault watch
  hash for .mergify.yml is stale again after master merge"**: commit
  `495f050` set the correct hash for `.mergify.yml` as it stood in that
  commit; a later merge from master (`2f912b7`) pulled in *more*
  `.mergify.yml` changes (a Copilot conflict-nudge rule, unrelated to
  PR #123's own work) that PR #123 never touched itself; the hash was
  now stale purely from absorbing someone else's change. Fixed by Gitar
  in `0261064`.

This is the rebase-staleness mechanism described above, happening for
real, caught by code review rather than by the CI gate (which is
consistent with the design: `check()` only blocks on a mismatch, and
Gitar/Copilot's own review independently notices the same mismatch and
comments on it before/alongside that). Eric also reports one case of a
batch of PRs getting bisected because the notes-check failed on every
composite speculative merge Mergify tried - consistent with the
batch-staleness mechanism (no single PR in the batch is "guilty," so
bisection can't isolate one), though not independently re-confirmed via
API search in this pass (Mergify's queue-status comments in this repo
don't appear to record batch composition/failure detail retrievably,
and CI run logs for `mergify/merge-queue/*` branches sampled here all
show `success` - the failing batch attempt likely wasn't preserved as its
own logged run, or predates the sampled window).

**Revised conclusion**: this is an active, recurring problem, not
theoretical - just one whose evidence trail lives in PR review comments
rather than CI failure logs. Treat it as comparably urgent to
[[.agent-vault/context/generated-index-churn|generated-index-churn]],
not behind it - both are confirmed-real now, and both point toward the
same diff-scoped fix shape.

## External validation (web research, 2026-09-29)

Found an almost exact match for this problem and proposed fix elsewhere:
[kontourai/station#2923](https://github.com/kontourai/station/issues/2923)
("Scope documentation freshness to each PR's own changes instead of the
merge-queue candidate") describes the identical failure mode - a
freshness gate run against a synthesized merge-queue candidate fails a
PR because *another* PR's changes staled its cited sources - and
proposes the same three-way split independently arrived at below:

1. **PR time (strict)**: a PR that modifies a watched source must also
   touch the note/record citing it - checked against the PR's own diff.
1. **Merge queue (relaxed)**: evaluate freshness against the PR's
   `merge-base`, not the batch/queue candidate, so unrelated PRs never
   fail it - "catch staleness once, at PR time, in the PR that caused
   it, and never re-check it in the queue" (their framing, matches ours).
1. **Nightly/tracking-only**: a separate, non-blocking job on `master`
   reports residual staleness (a tracking issue, in their case) instead
   of failing a required check - something this note hadn't proposed;
   worth considering as a way to keep *some* ambient "is this actually
   still accurate" signal without reintroducing a blocking gate that
   fails for reasons outside a PR's control.

This is independent confirmation that the direction below is a known,
named pattern elsewhere, not a one-off scheme.

## Direction agreed so far

Eric's framing: gate at the point where a human/agent is actually
crafting the commit (pre-commit hook, or a single PR's own diff) - if
correct there, the note was accurate when pushed. Drift introduced later
purely by other merges landing is acceptable and shouldn't block anything.

Proposed replacement (not yet implemented):

- Drop the stored content hash entirely. `watches` entries become just a
  `path` (`symbol` optional, kept only if per-symbol granularity is still
  wanted).
- Pre-commit: if a staged file matches a watch's `path`, the note that
  watches it must also be staged in the same commit, or the commit
  blocks. No hash computation at all.
- CI/queue enforcement (replacing the current hash-vs-tree comparison):
  diff the ref against its real `git merge-base` with `master`, and apply
  the same rule - if the union of commits touches the watched path, the
  union must also touch the note. For a batched Mergify branch this
  naturally unions all batched PRs' diffs, so a note touched by *any* PR
  in the batch satisfies it - no false positive from unrelated concurrent
  edits, because nothing is compared against a stored, driftable hash.
- `ack`, `reconcile`, `DanglingWatchError`, and the `hash:`/`stale:`
  frontmatter fields all go away under this model - there's nothing
  persisted to dangle or restamp.

**Rejected**: a CI step that auto-restamps hashes post-merge. `master` is
protected with Mergify as the only bypass actor, so a bot pushing a
restamp commit directly isn't available without a new, wider bypass
grant; routing the restamp through its own PR just re-feeds it into the
same queue/batch machinery causing the original problem, and a restamp
computed against one HEAD can already be behind by the time it lands
given how close together batched merges land - chasing the head rather
than solving anything.

## Related problems

Eric flagged that there are other, separate problems in flight that may
influence this design and should be cross-linked here once scoped, rather
than deciding this one in isolation.

- [[.agent-vault/context/generated-index-churn|generated-index-churn]] -
  the structural index embedded in `AGENTS.md` has a similar
  concurrent-PR/batching problem, but produces literal git merge
  conflicts rather than a CI check failure. Not yet clear whether the
  two should share a fix shape (e.g. both move toward "don't compare
  regenerated whole-repo state, compare only this PR's own diff") or need
  genuinely different solutions - worth deciding both before implementing
  either, since a shared mechanism could avoid building two one-off
  fixes.
- [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]] -
  the synthesis note tying this, `generated-index-churn`, and `schema.py`
  as a hot file together as one root cause, plus the decomposition/CI
  scoping hypothesis.

## Related

- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the `batch_size: 3`
  decision and the `-conflict` queue-condition stuck-state history that
  first surfaced this class of problem.
- [[.agent-vault/SCHEMA.md|SCHEMA]] - current (pre-redesign) frontmatter
  shape this note proposes changing.
