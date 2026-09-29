---
type: ci
watches:
  - path: .mergify.yml
    hash: 45266356e5012d95af4a63431ee41b48a4f2498a3ce75551a00c2fe6f1136803
stale: false
---

# A separate merge queue for documentation-only PRs

Implemented (see "Implementation" below) - kept as living documentation
of the design rather than converted to a `decision` note, since the
"Not yet decided" tuning questions are still genuinely open. Proposed by
Eric as a further, targeted response to
[[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]]:
that note already established that the `default` queue runs the full
`test` job (SonarQube scan included) 2-3x per merged PR because entry and
merge are both gated on the full ruleset. A documentation-only PR (the
kind this very investigation has been producing - PRs #126, #129, #130)
pays that same cost for changes that can't affect `pytest`, coverage, or
SonarCloud's analysis at all.

## Proposed design

- **Routing**: a new `pull_request_rules` entry that matches when every
  changed file is under `.agent-vault/**` or `*.md` (plus
  `.github/pull_request_template.md`, `CONTRIBUTING.md`, `README.md` -
  anything already covered by the existing `mdformat` check in `ci.yml`)
  and routes the PR into a new `docs` queue instead of `default`.
- **Lighter CI**: a fast job/step path that runs only prose-relevant
  checks - `mdformat --check`, `girdle notes check .` (already fast,
  already docs-scoped), `girdle index . --check AGENTS.md` (only
  relevant if the index block itself is touched) - and skips
  `pytest`/coverage and the `SonarQube Scan` step entirely, since neither
  can find anything in a documentation-only diff.
- **Light bot review**: still Gitar (already applied to every non-
  Dependabot PR via the `gitar-managed` label rule - no change needed
  there), but the `docs` queue's `merge_conditions` would not require
  `check-success=SonarCloud Code Analysis` or `check-success=test` the
  way `default`'s injected ruleset does - only the lighter prose-lint
  check and Gitar's review.

## Open questions

- **Mergify condition syntax for "all changed files match a
  path/pattern" - verified.** Per
  [Mergify's conditions docs](https://docs.mergify.com/conditions/#attributes):
  `files ~= <regex>` is true if *any* changed file matches; `files *= <glob>`
  is the glob-pattern equivalent. To require *every* changed file matches,
  negate a lookahead: `-files ~= ^(?!pattern)` reads as "no file fails to
  match pattern." For this repo's multi-pattern case (`.agent-vault/**`,
  `*.md`, the PR template), one condition covers it:
  `-files ~= ^(?!(\.agent-vault/|.*\.md$)).*$` - "no changed file is
  outside `.agent-vault/` and doesn't end in `.md`" (`.github/pull_request_template.md`
  already ends in `.md` so needs no separate clause).
- **Does this need a new queue at all, or just different
  `merge_conditions` on a `files`-scoped `pull_request_rules` match
  within the existing `default` queue mechanics?** Mergify supports
  routing to different named queues per rule (as this repo already does
  for `Dependabot`/`Dependabot-major`/`default`), so a fourth `docs`
  queue is the natural fit, but worth confirming there isn't a lighter
  mechanism (e.g. just varying `merge_conditions` by a `files` condition
  within one queue) before adding a fourth queue's worth of config.
- **Mixed PRs**: a PR that touches both code and docs (common - most of
  this session's own PRs cited vault notes alongside a code/config
  change) doesn't qualify and correctly falls through to `default` -
  worth confirming that's the intended behavior (it is, per the
  motivation above: the lighter path is only safe when nothing else
  could be affected) rather than something to special-case.
- **Does the existing branch ruleset (`test`, `SonarCloud Code Analysis`,
  `Gitar` required checks) block this regardless of queue?** Master's
  ruleset lists Mergify as the only bypass actor, so Mergify merging
  through the `docs` queue without those checks green is exactly the
  same mechanism the `Dependabot` queues already rely on
  (`branch_protection_injection_mode: merge` with queue-specific
  `merge_conditions` that don't include the full ruleset) - not a new
  risk, but worth stating explicitly since it's easy to assume the
  branch ruleset applies uniformly regardless of Mergify config.

## Implementation

Shipped as a single change (not split further - one coherent feature,
per [[.agent-vault/decisions/minimal-discrete-pr-policy|minimal-discrete-pr-policy]]):

- `.mergify.yml`: new `docs` queue (`branch_protection_injection_mode: merge`,
  `checks_timeout: 15m`, `merge_conditions: [check-success=test, check-success=Gitar, "#approved-reviews-by>=1"]` - no SonarCloud
  requirement). New `queue documentation-only PRs` rule using the
  verified `-files ~= ^(?!(\.agent-vault/|.*\.md$)).*$` condition;
  `queue development PRs` gets the complementary `files ~= ^(?!...).*$`
  condition (at least one non-doc file) so the two rules are mutually
  exclusive - no PR can match both.
- `ci.yml`: new `changes` job (pull_request-only) diffs
  `base.sha`..`head.sha` and outputs `docs_only`. The `test` job depends
  on it (`if: always()`, so a skipped/failed detection defaults to
  running everything) and gates the `pytest` step and the `SonarQube Scan` step on `docs_only != 'true'`. `ruff`/`mdformat`/`yamllint`/index/
  vault-notes checks stay unconditional - they're already the cheap part
  and scan the whole tree regardless of diff size. `test`'s own
  check-success is still meaningful for docs-only PRs since those checks
  still ran.

Resolved the two "does this need a new queue" and "does the branch
ruleset block this" open questions above: yes, a fourth queue is the
right shape (matches the existing `Dependabot`/`Dependabot-major`/`default`
pattern rather than inventing a new mechanism), and no, the branch
ruleset doesn't block it - Mergify's bypass-actor status is exactly what
makes the Dependabot queues' lighter `merge_conditions` work today, and
`docs` uses the identical mechanism.

## Not yet decided

- Whether the queue needs its own `batch_size` tuning - left unset
  (defaults to no batching) for now; could reasonably batch more
  aggressively than code changes since collision risk within pure-docs
  PRs is lower, though
  [[.agent-vault/context/generated-index-churn|generated-index-churn]]
  says otherwise for anything touching `AGENTS.md`'s index block
  specifically. Revisit once there's real docs-queue traffic to tune
  against, rather than guessing ahead of evidence.

## Related

- [[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]] -
  the finding this design responds to.
- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the existing
  three-queue (`Dependabot`/`Dependabot-major`/`default`) structure this
  would extend to four.
