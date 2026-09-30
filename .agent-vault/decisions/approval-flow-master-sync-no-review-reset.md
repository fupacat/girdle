---
type: decision
---

# Conflict-only master syncs must not reset PR approval state

## Context

The repository's `master` protection rules require one approving review,
and the GitHub ruleset also has `dismiss_stale_reviews_on_push: true`.
For Copilot PRs that are rebased or merged from `master` to resolve a
conflict, the head SHA changes even when the effective diff against
`master` is unchanged. GitHub can treat that as a fresh push and dismiss
existing reviews, leaving a brief period where Mergify sees
`#approved-reviews-by<1` and dequeues the PR even though the code under
review did not meaningfully change.

This is the churn pattern behind issue #256: a conflict-only update to an
already-approved Copilot PR causes a temporary approval gap, followed by a
manual `@mergifyio requeue` once the review is re-added. With several
Copilot PRs stacked behind a moving `master`, the queue churn becomes a
real throughput problem even when no actual review-worthy code change was
made.

## Decision

Conflict-only pushes that only update the branch to the latest `master`
without changing the semantic diff under review must not reset approval
state or trigger a queue dequeue.

This decision is intentionally documented in-repo but implemented in the
GitHub/Mergify settings outside the repo, since the actual branch ruleset
configuration is not stored in this repository. The policy choice is:

- keep an approval valid across a conflict-only sync/rebase; only a real
  code change should reset the review state;
- do not require a transient re-review race to keep the queue alive;
- prevent branch-sync events from invalidating an approval when the semantic
  diff is unchanged; a queue-entry gate cannot preserve approval or prevent
  dequeue when GitHub's required-review condition becomes unsatisfied.

A Mergify condition based on a review-settled marker such as
`label=gitar-approved` (or an equivalent review-stable signal) plus a short
debounce can delay queue entry until review state settles, but it cannot
prevent GitHub from dismissing stale approvals on push or stop an already
queued PR from being dequeued when the required approval disappears. It is
not a fix for this churn. The direct operational workaround is to disable
stale-review dismissal in the ruleset; this preserves approvals across
conflict-only syncs, but also means GitHub will not automatically invalidate
an approval after a real code change.

## Alternatives considered

- **Keep `dismiss_stale_reviews_on_push: true` and rely on Gitar to re-review**
  - Rejected: it creates a temporary approval hole, lets Mergify dequeue a
    still-valid PR, and adds avoidable churn.
- **Turn off stale review dismissal entirely**
  - Preferred operational workaround: it prevents GitHub from clearing the
    approval on a conflict-only sync, so the required-review condition does
    not lapse and trigger dequeue. The tradeoff is that GitHub also keeps an
    approval after a real code change; enforcing re-review only for meaningful
    diff changes requires additional automation or a future platform feature.
- **Have Mergify re-approve when the diff vs `master` is unchanged**
  - Valid fallback, but still couples a queue policy to a bot-driven
    review-game and extra state. It works, but it is more complex than
    protecting the review from being invalidated in the first place.
- **Make queue entry wait for `label=gitar-approved` + short debounce**
  - Not sufficient to preserve approval or prevent dequeue: this controls
    queue entry only and cannot override GitHub's dismissal of stale reviews
    or the required-review merge gate. It may supplement the operational
    workaround, but must not be treated as its replacement.

## Consequences

- With stale-review dismissal disabled, a conflict-only master-sync update
  does not clear the approval and trigger a queue-dequeue/requeue loop.
- Reviewers are not asked to re-approve solely because the branch was
  refreshed to absorb `master` changes, but GitHub will also retain approval
  after real code changes unless additional automation enforces re-review.
- The repo keeps the design rationale visible here, while the concrete
  GitHub Ruleset/Mergify settings remain a maintainer-side operational
  decision rather than an in-repo code change.

## References

- [[.agent-vault/ci/merge-pipeline|merge-pipeline]]
- [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]]
- [[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]]
