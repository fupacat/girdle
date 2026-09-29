---
type: ci
watches:
  - path: .mergify.yml
    hash: 602be50cdef89e9f8614226d7c30733b0585c548b4f6bc46d464247e85b35cbd
  - path: .github/workflows/ci.yml
    hash: 2dc5f004fcc0c314990a8f13bef729ac5aa0ca9e4890de537e82bd319f6c7667
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

- The single `test` job in [ci.yml](../../.github/workflows/ci.yml) -
  ruff, mdformat, yamllint, pytest+coverage, the structural-index check,
  the vault-notes check, and the SonarQube scan, all bundled - has to run
  and pass on the PR's own branch *before* it can even enter the queue.
- Then, because it's queued, Mergify re-runs the same full ruleset again
  on the speculative batch-merge branch to test the merge itself.
- So the heaviest checks run twice per PR that actually merges, and the
  second run is the expensive one to hold back, not the cheap one - the
  opposite of "streamline entry, defer expensive checks."

**SonarCloud's double-run is the same root cause as the first bullet, not
a separate mechanism.** Automatic Analysis is confirmed already disabled
(Eric), so that's ruled out. Instead: master's ruleset lists `test` and
`SonarCloud Code Analysis` as two separate required checks
([[.agent-vault/ci/merge-pipeline|merge-pipeline]]), and because
`default`'s injection mode gates *both* queue entry and the merge gate on
the full ruleset, the `test` job - which embeds the blocking
`SonarQube Scan` step (`sonar.qualitygate.wait=true`) - genuinely
executes in full, Sonar scan included, twice per PR that merges: once on
the PR's own branch to satisfy entry, and again on Mergify's speculative
batch-merge branch to satisfy the merge gate. Confirms the first bullet
rather than adding a new problem - SonarCloud is just the most visible
instance of the same double-run, since it's both an explicit required
check name and the most expensive step in the job.

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
- Whether splitting `ci.yml`'s single `test` job into a fast tier
  (lint/format/index/vault-notes) and a slower tier (pytest+coverage,
  SonarCloud) is worth doing independently of the injection-mode
  question, so a genuinely fast fail (e.g. a lint error) doesn't wait on
  the slow tier either.

## Related

- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the tool-roles
  decision and the `-conflict`/batch_size history this builds on.
- [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]] -
  the velocity-vs-guarantees goal this should be judged against.
