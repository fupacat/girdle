---
type: ci
watches:
  - path: .mergify.yml
    hash: 5cb09b7babf697c61997853bb77c7b3a3fe5dcd9dfd9ffd00be42eda3a9cbc1b
  - path: .github/workflows/ci.yml
    hash: d30758de4c7d3e77fc981c06ac77a4b9c4bc278ed51744666571438b6bab2a89
stale: false
---

# CI is too expensive per queue entry, and has no timeout floor for stuck/conflicted branches

Not committed scope yet - live design discussion, recorded so the
reasoning survives across sessions. Related to
[[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]]'s
velocity goal - this is about CI/queue cost specifically, as opposed to
that note's PR-shape/decomposition angle.

## Problem found

**Full ruleset gates queue *entry*, not just merge, for the `default`
queue.** Per [[.agent-vault/ci/merge-pipeline|merge-pipeline]]'s own
notes, the Dependabot queues deliberately use
`branch_protection_injection_mode: merge` specifically to avoid this -
but the `default` queue (everything else: human/agent/Copilot PRs) uses
the default `queue` mode, which injects master's full ruleset
(`test`, `SonarCloud Code Analysis`, `Gitar`, 1 approval) into both
`queue_conditions` and `merge_conditions` (`.mergify.yml`'s `default`
queue rule has no explicit `merge_conditions`/`queue_conditions` beyond
`author!=dependabot[bot]` - it's all coming from the injected ruleset).
Concretely this means:

- The `test` job in [ci.yml](../../.github/workflows/ci.yml) is now an
  aggregate status check over `cheap-checks` and `pytest`. `cheap-checks`
  runs the lint/format, Mergify config, structural-index, and vault-notes
  checks; `pytest` runs pytest+coverage and is skipped for light PRs and
  drafts. The aggregate status accepts pytest being skipped only for light
  diffs or draft PRs. For a non-draft PR with a non-light diff, the expensive
  pytest tier runs on the PR's own branch before it can enter the queue.
- SonarQube runs in a separate `sonar` job, rather than inside `test`.
  It is skipped for light PRs, drafts, and Dependabot PRs; for other PRs
  it remains a separate required check alongside the aggregate `test`
  status.
- Then, because it's queued, Mergify re-runs the required checks again
  on the speculative batch-merge branch to test the merge itself. Thus
  the expensive pytest and Sonar tiers can still run on both the PR branch
  and the speculative branch; splitting the jobs does not change the
  queue-entry-vs-merge gating behavior.

**SonarCloud's double-run has the same queue-entry-vs-merge root cause,
though it is no longer part of the `test` job.** Automatic Analysis is
confirmed already disabled (Eric), so that's ruled out. Master's ruleset
lists `test` and `SonarCloud Code Analysis` as two separate required checks
([[.agent-vault/ci/merge-pipeline|merge-pipeline]]). The workflow now runs
SonarQube in a separate `sonar` job, gated on the cheap checks and coverage
job and skipped for light diffs, drafts, and Dependabot PRs. Because
`default`'s injection mode gates *both* queue entry and the merge gate on
the full ruleset, eligible PRs run the Sonar scan on their own branch to
satisfy entry and again on Mergify's speculative batch-merge branch to
satisfy the merge gate. SonarCloud remains the most visible instance of
the same cross-branch duplication because it is both an explicit required
check and an expensive tier.

**No `checks_timeout` on the `default` queue.** The `Dependabot` and
`Dependabot-major` queue rules both set `checks_timeout: 30m`; the
`default` queue rule sets none - unbounded. Combined with the already-
documented persistent `-conflict` stuck-condition bug
([[.agent-vault/ci/merge-pipeline|merge-pipeline]]'s Consequences
section - PRs #97/#98 stuck 15-20+ minutes even after refresh/dequeue/
requeue), a check that never finishes on a conflicted speculative branch
has nothing bounding how long it occupies one of the 7
`max_parallel_checks` slots. That plausibly explains "tests don't seem to
finish on a conflicted branch" - not necessarily pytest hanging, but the
queue-level check evaluation never timing out and getting stuck exactly
like the documented `-conflict` cases.

## Evidence (subagent investigation, 2026-09-29)

**Double-run claim: CONFIRMED, concretely - and it's a floor, not a cap.**
Of the last 100 `ci.yml` runs in a ~7-hour window, only 3 ran on
`mergify/merge-queue/*` branches versus 78 `pull_request` + 22 `push`.
Traced PR #104 end-to-end:

- Its own branch ran `test` once, 71s, passing.
- Mergify then speculatively batch-tested it with #102 on one
  `mergify/merge-queue/*` ref: `test` ran again, 79s.
- After a reshuffle, it was tested alone on a second
  `mergify/merge-queue/*` ref: `test` ran a **third** time, 78s.
- Only then merged to master.

So this specific PR got the full `test` job (ruff/pytest/coverage/
SonarQube scan) three times, not the theorized two - batch reshuffling
adds runs beyond the entry+merge floor. Check-runs on the PR's own head
SHA show exactly **one** `SonarCloud Code Analysis` entry, confirming
Automatic Analysis is off and the duplication is entirely cross-branch
(own branch vs. each speculative merge branch), not same-SHA
duplication - matches this note's SonarCloud explanation exactly.

**Timeout/stuck-conflict claim: not directly observable in this window,
not contradicted either.** All 3 sampled `mergify/merge-queue/*` runs
completed normally (~78-81s, same as a normal PR-branch run) - no run
hung or ran long. The sampled window was ~7 hours and evidently
non-conflicted, not one covering the #97/#98 stuck-`-conflict` incidents
already documented in
[[.agent-vault/ci/merge-pipeline|merge-pipeline]]. The `mergify` CLI
wasn't installed in the investigation environment, so `mergify events`/
`queue show` history (which would show fresh `-conflict`/timeout
occurrences) couldn't be pulled - that needs either installing the CLI
or a Mergify API token. Recommend doing that before treating the
timeout gap as more than the existing #97/#98 precedent.

## External validation (web research, 2026-09-29)

Mergify's own documentation names the fix already proposed here as a
first-class pattern, and adds two more worth adopting:

- **"Two-step CI"** ([Mergify performance
  docs](https://docs.mergify.com/merge-queue/performance/)): "preliminary
  tests: fast checks run when a PR is created or updated, gating entry
  into the queue" vs. "pre-merge tests: exhaustive checks run just before
  merge." This is exactly the `branch_protection_injection_mode: merge`
  change already flagged as undecided above - Mergify treats it as the
  standard way to avoid the double-run this note found on PR #104, not a
  Dependabot-specific workaround.
- **Dynamic batch sizing** ([Mergify batches
  docs](https://docs.mergify.com/merge-queue/batches/)): instead of a
  fixed `batch_size: 3`, specify a `min`/`max` range - batches stay small
  (cheap to bisect) when the queue is light and grow toward `max` when it
  backs up. Directly relevant to the batch-bisection case Eric reported
  on [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]
  and to the #93-104 PR-burst incident in
  [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]] -
  a fixed batch size that's fine under normal load can still make a
  burst worse.
- **Bisection is already automatic**: per the same docs, a failing batch
  splits (bounded by `max_parallel_checks`, minimum two), retests splits
  in parallel, and isolates down to single PRs without manual
  intervention - confirms Eric's reported batch-bisection behavior is
  expected Mergify behavior, not a malfunction; the problem is specifically
  that *no* PR in a hash/index-churn-caused batch failure is actually
  guilty, so bisection burns CI cycles finding that out every time.
- **Framing for the timeout question**: Mergify's docs describe an "RCV"
  trade-off (Reliability, Cost, Velocity - pick two): parallel speculative
  checks favor reliability+velocity at the cost of wasted CI runs;
  sequential validation favors reliability+cost at the cost of velocity;
  batching favors velocity+cost at the risk of hidden failures. Useful
  vocabulary for stating explicitly which two this repo is choosing when
  picking a `checks_timeout` value and batch shape, rather than picking
  implicitly by omission (today's gap, per this note's "no checks_timeout"
  finding).

## Not yet decided

- Whether `default` should move to `branch_protection_injection_mode: merge`
  like the Dependabot queues, so queue *entry* only needs cheap/fast
  checks and the full ruleset gates the merge itself (checks would then
  run once, at the point that actually matters) - or whether that mode
  change has side effects specific to non-Dependabot PRs that haven't
  been checked (the Dependabot rationale for `merge` mode was about
  secrets/permissions differing per-author, which doesn't obviously apply
  here).
- What `checks_timeout` value the `default` queue should get, and what
  should happen on timeout (dequeue and report, vs. retry) - not scoped.
- The fast/slow split has since been implemented in `ci.yml`:
  `cheap-checks` runs independently of the pytest and Sonar tiers, while
  the aggregate `test` job reports the required CI status. This makes
  cheap failures fail faster, but does not by itself change the queue's
  entry-vs-merge check injection behavior.

## Related

- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the tool-roles
  decision and the `-conflict`/batch_size history this builds on.
- [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]] -
  the velocity-vs-guarantees goal this should be judged against.
