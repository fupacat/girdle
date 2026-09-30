---
type: ci
watches:
  - path: .mergify.yml
    hash: 631a21fecd7f4a653193a9c64fd777f9f03078f276b1616007418f3ce0db7464
stale: false
---

# A separate merge queue for "light" (docs/CI-config-only) PRs

Implemented (see "Implementation" below) - kept as living documentation
of the design rather than converted to a `decision` note, since the
"Not yet decided" tuning questions are still genuinely open. Originally
scoped as documentation-only; broadened to also cover CI-config changes
(`.github/workflows/**`, `.mergify.yml`) once a real gap was found - see
"Broadened to include CI config" below. Proposed by Eric as a further,
targeted response to
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

Shipped in two steps (not split further per step - each one coherent,
per [[.agent-vault/decisions/minimal-discrete-pr-policy|minimal-discrete-pr-policy]]):
first as docs-only (`docs` queue/`docs_only` output), then broadened to
`light`/`light_diff` covering CI config too, once the mutual-exclusion
gap above was found. Current shape:

- `.mergify.yml`: `light` queue (`branch_protection_injection_mode: none`,
  `checks_timeout: 15m`, `merge_conditions: [check-success=test, check-success=Gitar, "#approved-reviews-by>=1"]` - no SonarCloud
  queue requirement; `none` stops the queue from inheriting the ruleset's
  checks, while CI still reports SonarCloud on the PR for GitHub's final
  merge). `queue light (docs/CI-config-only) PRs` rule using
  `-files ~= ^(?!(\.agent-vault/|.*\.md$|\.github/workflows/|\.mergify\.yml$)).*$`;
  `queue development PRs` gets the complementary
  `files ~= ^(?!...).*$` condition (at least one file outside all light
  patterns) so the two rules are mutually exclusive - no PR can match
  both, and no PR (light, mixed-light, or code) matches neither.
- `ci.yml`: `changes` job (pull_request-only) diffs `HEAD^1`..`HEAD`
  (Gitar later changed this from the original `base.sha`/`head.sha`
  approach - functionally equivalent, verified the substitution wasn't a
  silent regression like the one in
  [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]'s
  PR #128 incident) and outputs `light_diff`. The `test` job depends on
  it (`if: always()`, so a skipped/failed detection defaults to running
  everything) and gates only the `pytest` step on
  `light_diff != 'true'`. `SonarQube Scan` now runs for all
  non-Dependabot PRs (including light diffs) so
  `SonarCloud Code Analysis` always reports on protected-branch PRs.
  `ruff`/`mdformat`/`yamllint`/index/vault-notes checks stay
  unconditional - they're already the cheap part, scan the whole tree
  regardless of diff size, and (`yamllint` specifically) are exactly
  what validates a CI-config-only PR's own changed files. `test`'s own
  check-success is still meaningful for light PRs since those checks
  still ran.

Resolved the two "does this need a new queue" and "does the branch
ruleset block this" open questions above: yes, a fourth queue is the
right shape (matches the existing `Dependabot`/`Dependabot-major`/`default`
pattern rather than inventing a new mechanism), and no, the branch
ruleset doesn't block it - Mergify's bypass-actor status is exactly what
makes the Dependabot queues' lighter `merge_conditions` work today, and
`docs` uses the identical mechanism.

## Broadened to include CI config

Eric asked for the same treatment for CI-config changes
(`.github/workflows/**`, `.mergify.yml`) and specifically whether GitHub
Actions changes and Mergify config changes should be split into two
separate categories/queues. Recommendation: no - both share the exact
same reason for skipping SonarCloud/pytest (neither touches
`sonar.sources=src`/`sonar.tests=tests`), so splitting them would just
duplicate identical `merge_conditions` for no benefit.

**A real correctness gap was found while implementing this, not just a
style preference.** The natural first attempt - a third, separate
mutually-exclusive `ci`-only queue alongside `docs` - has a hole: a PR
touching *both* a doc file and `.mergify.yml` (a pattern this repo's own
PRs have used, e.g. #131 touched `.mergify.yml`/`ci.yml` alongside
`.agent-vault/*.md` notes) would match neither the docs-only nor the
ci-only condition (since "all files are docs" and "all files are
ci-config" are both false for a mixed set), and would therefore match no
queue rule at all - never getting queued. Fixed by merging into one
`light` category/queue covering both patterns with a single condition,
rather than two mutually-exclusive ones. Also confirmed
`check-success=test` should stay required even for CI-config-only PRs -
unlike `pytest`, the `test` job's `yamllint` step is exactly what
validates the YAML files such a PR touches, so it still carries real
signal even with `pytest` skipped.

Also verified: `yamllint`/`ruff`/`mdformat` all pass, `pytest` passes
(397 tests), and the light-file regex (`^(\.agent-vault/|.*\.md$|\.github/workflows/|\.mergify\.yml$)`)
was tested against both `grep -E` (used in `ci.yml`) and Python's `re`
(what Mergify itself uses) with matching results across doc-only,
ci-only, mixed-light, mixed-with-real-code, and a deliberate
false-positive-substring case (`scripts/not.mergify.yml.bak`).

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
