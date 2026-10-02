---
type: ci
watches:
  - path: .mergify.yml
    hash: f37fc708e75627efc880019119326fddb56a670f7a9d9ea2e9573655742f9097
stale: false
---

# Merge pipeline: tool roles and merge paths

## Context

girdle's `master` branch is protected by a GitHub ruleset requiring three
status checks (`test`, `SonarCloud Code Analysis`, `Gitar`) and one
approving review, with no bypass actors other than Mergify. Getting a PR
from open to merged therefore has to satisfy that ruleset through some
combination of GitHub Actions, SonarCloud, Gitar, Copilot, and Mergify -
five tools with genuinely overlapping capabilities (Gitar and Copilot can
both review, both auto-fix, and Copilot's native auto-merge can compete
with Mergify's queue). This note is the settled division of labor between
them, and the reasoning behind the non-obvious parts, so a future change
doesn't accidentally reintroduce a conflict already debugged once.

## Decision: tool roles

| Tool                          | Role                                                                                                                                                                                                               | Not responsible for                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| **GitHub Actions** (`ci.yml`) | Ground truth - runs ruff/mdformat/yamllint/pytest+coverage, girdle's own self-checks (index freshness, vault notes), triggers the SonarQube scan, deploys the Pages dashboard                                      | Review, merging                                                                                                  |
| **SonarCloud**                | Static-analysis quality gate - bugs, vulnerabilities, code smells, duplication, coverage-on-new-code. Required check                                                                                               | CI-failure auto-fix, approval, merging                                                                           |
| **Gitar**                     | AI PR review (required check) **and** the sole automated CI-failure auto-fixer (build/test/lint/flaky-test) - it pushes fix commits directly to the branch. Primary source of the required approving review        | Merging (its own auto-merge is deliberately never configured - see below)                                        |
| **Copilot (PR reviewer)**     | Backup/secondary reviewer only - can approve, but nothing requests it automatically. Exists as a manual fallback (`gh api .../requested_reviewers`) for a PR that's genuinely stuck, not a parallel automated path | CI-failure auto-fixing, merging                                                                                  |
| **Copilot (coding agent)**    | Opens PRs from assigned issues (`copilot/*` branches)                                                                                                                                                              | Everything else - it's a PR author, not part of the pipeline                                                     |
| **Dependabot**                | Opens dependency-bump PRs                                                                                                                                                                                          | Everything else - also just a PR author                                                                          |
| **Mergify**                   | The **only** merge orchestrator - four named queues, self-approves safe Dependabot bumps, nudges Dependabot rebases, labels majors for review                                                                      | Code quality judgment - it has no opinion on content, only on whether the required checks/approval already exist |

**Why not consolidate onto GitHub-native tooling** (native merge queue +
CodeQL + Copilot) instead of Mergify + SonarCloud + Gitar: researched and
rejected. GitHub's native merge queue creates the same
temporary-merge-branch mechanism Mergify's draft-PR trick replicates, but
2026-era reports show it hits the identical Dependabot-checks problem
below natively (CodeQL failing against the ephemeral merge-queue ref,
`GITHUB_TOKEN` unable to enqueue PRs, bot PRs failing human-oriented
template checks) - it doesn't remove the problem, it just moves it, while
losing Mergify's per-queue `queue_conditions`/`branch_protection_injection_mode`
granularity that the four-queue split below depends on. Separately,
CodeQL is deep security analysis, not a quality-gate/coverage-threshold/
duplication tool - it's additive to SonarCloud, not a replacement for it.

## Decision: the four merge paths

1. **Dependabot patch/minor/security** → Mergify auto-approves itself
   (satisfies the 1-review rule for genuinely low-risk bumps) → `Dependabot`
   queue → merged by Mergify.
1. **Dependabot major** → labeled `dependency-major-review`, **not**
   auto-approved - waits for a real approving review (Gitar or a human;
   `#approved-reviews-by>=1` gates queue *entry*, not just merge, so an
   unapproved major never blocks the train behind it) → `Dependabot-major`
   queue → merged by Mergify.
1. **Documentation-only PRs** → routed to the `docs` queue, which skips the
   pytest/SonarCloud checks that are unnecessary for documentation changes →
   merged by Mergify.
1. **Everything else** (human PRs, Copilot coding-agent PRs, agent-authored
   PRs like this session's own `ci/*`/`docs/*` branches) → Gitar reviews
   and approves (Copilot's reviewer is manual-only; the automatic "Copilot
   review for default branch" ruleset was disabled 2026-09-30 because it
   duplicated Gitar, re-ran on every push, and burned quota) →
   `default` queue → merged by Mergify.

GitHub's native "Allow auto-merge" repo setting is explicitly disabled
(`allow_auto_merge: false`) - it's a second, uncoordinated merge path that
would race against Mergify's queue (bypassing the speculative
queue-ahead-PR testing the queue does) if anyone armed it via the UI or
`gh pr merge --auto`.

## Decision: `branch_protection_injection_mode: merge` for both Dependabot queues

The default queue mode (`queue`) injects master's full ruleset into both
queue *entry* and the merge gate. For Dependabot PRs this was a genuine
deadlock: entry required `check-success=Gitar`/`SonarCloud`, but those
checks don't reliably run on a Dependabot-authored branch in the first
place (GitHub withholds some secrets from Dependabot-triggered workflow
runs, and Gitar/Sonar app permissions differ per-author) - confirmed live
as "Waiting for queue conditions" stuck forever. `branch_protection_injection_mode: merge`
injects the ruleset only at the merge gate, so entry is governed purely by
`queue_conditions`; combined with `max_checks_retries: 1` (which forces
Mergify to always build its own `mergify/merge-queue/*` draft branch,
authored as `mergify` rather than `dependabot[bot]`). That draft was
expected to get Gitar/SonarCloud checks, but it does not: Gitar skips drafts and
`sonar` is skipped on them, so both queues' `merge_conditions` now require only
`test` and the approval count (otherwise every Dependabot PR timed out after 30m,
#425-#432, issue #465). The `default` queue for
non-Dependabot PRs doesn't need this - Gitar/SonarCloud already run
natively on human/agent-authored branches.

## Decision: Gitar as the sole automated auto-fixer, not both

Gitar and Copilot can both auto-fix CI failures. Running both would risk
two bots pushing competing fix commits to the same branch, duplicate/
conflicting findings to triage, and doubled Actions-minutes billing (Copilot
code review consumes Actions minutes as of mid-2026). Gitar was chosen
based on observed consistency across this repo's own PR history (see
`.gitar/review/`, `.gitar/config/`) - Copilot stays available as a manual,
on-demand second opinion rather than a second automated reviewer.

Gitar's CI-failure auto-fix (build/test/lint/flaky-test) is opt-in per PR,
not a dashboard-wide default - it activates via the `gitar-managed` label
or a `gitar auto-apply:on` comment. `.mergify.yml`'s "enable Gitar
auto-apply on all PRs" rule applies that label to every PR on open, making
the automation blanket instead of a manual per-PR step - **except**
`author=dependabot[bot]`, which is excluded: a Gitar fix commit pushed onto
a Dependabot branch counts as "a commit from someone else," which makes
Dependabot stop auto-managing that branch (losing its own rebase/
conflict-resolution/version-refresh behavior - the same reason Mergify's
own `update` action is avoided in favor of an `@dependabot rebase`
comment). Gitar's own auto-merge (`.gitar/config/merge.md`) is deliberately
never created, so it can't arm a second merge path competing with
Mergify's queue.

**Gitar's "Skip draft PRs" setting is on** (dashboard setting, not in the
repo; re-enabled 2026-09-30). Draft versus ready is the phase signal in the
staged checks/review/repair pipeline (see the
`staged-pr-pipeline-checks-review-repair` decision note): Gitar reviews
only ready PRs, so it never reviews a Copilot PR mid-work or a Mergify
`mergify/merge-queue/*` speculative draft. The `light` queue nevertheless
still has an explicit `check-success=Gitar` merge condition; it was not
removed. Do not infer from the draft-skipping setting that Gitar is absent
from that queue's merge gate.

## Consequences

- A PR sitting open across a `.mergify.yml`/`.gitar/` config change gets no
  automatic re-evaluation - Gitar and the queue rules only (re-)trigger on
  a fresh push. A stale PR needs an explicit nudge (`@dependabot rebase`,
  or a manual push) after any change that would newly apply to it - this
  bit twice in this repo's own history (PRs #19-22 sat unreviewed for
  exactly this reason until nudged).
- **A distinct, separate failure mode from the one above**: Gitar can
  approve a PR (post its review, even auto-apply a fix commit) while its
  own required `Gitar` status check silently never posts on the current
  head SHA - the PR looks approved but Mergify's queue stays blocked on
  the missing check. Confirmed directly on PR #90: the commit right
  before Gitar's own auto-applied fix had a successful `Gitar` check;
  Gitar's own fix commit on top of it did not, and this persisted for
  ~2 hours until nudged. Not a permanent/categorical gap, though - PR
  #68's Gitar-authored commit got a clean check under broadly similar
  timing, so it isn't simply "Gitar never checks its own commits."
  Recoverable with a same-SHA `@gitar-bot` mention asking it to re-run -
  confirmed this resolves it without needing a new commit. Root cause
  (a webhook/queue race, possibly tied to rapid successive commits)
  isn't visible from this side and wasn't pinned down further - the
  symptom and the fix are what's actionable, not the mechanism.
- **A third, also-distinct gap, recurring**: Copilot can finish a PR
  (approved, all checks green) while never firing the
  `review_requested`/`ready_for_review` event `auto-merge-copilot.yml`
  depends on to promote it out of draft - first seen on PR #92, recurred
  on PR #114 (zero runs of the workflow existed for its branch despite a
  `review_requested` event appearing in the PR's own timeline; `CI` and
  other `pull_request`-triggered workflows fired normally in the same
  window, ruling out a general Actions outage). GitHub exposes no
  authoritative "Copilot finished coding" event - `review_requested` is an
  inferred proxy that other actors (CODEOWNERS auto-request, a teammate,
  Gitar's review flow) can also fire, and delivery to Actions isn't
  guaranteed. `auto-merge-copilot.yml` now has a second job
  (`fallback-sweep`, `schedule`-triggered every 15 minutes) that promotes
  any open Copilot-authored draft PR whose title no longer starts with
  `[WIP]` (Copilot's in-progress marker) and whose latest commit is at
  least 30 minutes old, independent of whether the event-driven job ever
  ran - the reactive job stays as the fast path, the sweep is the backstop.
- `.github/workflows/auto-assign-copilot.yml` (issue #85's auto-assignment
  automation, later extended to sync issue dependency labels and Project
  Status) needs a dedicated PAT in the `COPILOT_ASSIGN_TOKEN` secret, not
  the default `GITHUB_TOKEN` - the workflow calls both
  `replaceActorsForAssignable` and `updateProjectV2ItemFieldValue`, so the
  token needs **Read access to metadata**, and **Read and Write access to
  actions, code, issues, pull requests, and repository projects**.
  Discovered incrementally across PRs #90/#92 (token bootstrap and
  scope-error-handling fixes) rather than known upfront.
- The required-approval story is now two different mechanisms depending on
  PR type (Mergify self-approve for safe Dependabot bumps vs. Gitar/Copilot
  review for everything else) rather than one uniform rule - documented
  here and in `.mergify.yml`'s own rule comments so it isn't rediscovered
  from scratch.
- Copilot coding-agent PRs stacked against a moving `master` routinely drift
  into genuine content conflicts (not just a stale branch) as earlier PRs
  in the same batch merge - the "Keep PRs up to date" `update` rule can't
  fix that, and it doesn't self-resolve by dequeuing/requeuing either
  (confirmed live: requeuing PR #93 left it stuck on the unmet `-conflict`
  condition). Mergify's `conflict` pull-request attribute updates reactively
  off GitHub webhooks, so a `pull_request_rules` entry conditioned on
  `conflict` + `author=Copilot` reacts within seconds rather than needing a
  polling GitHub Actions workflow - it comments `@copilot` on the affected
  PR (Copilot's coding agent watches for mentions on PRs it authored and
  pushes fix commits in response, including conflict resolution). To avoid
  repeated nudges while still conflicted but allow a later re-conflict to
  nudge again, the rule adds a `conflict-nudged` label with the comment and
  only posts when that label is absent; a separate rule clears the label
  once the conflict is resolved. The hidden comment marker records the head
  commit SHA (`<!-- conflict-nudge:{{head.sha}} -->`) for context. The GitHub author `login` for these PRs is
  `Copilot` (a Bot-type user) - not `copilot-swe-agent[bot]` or
  `app/copilot-swe-agent`, both of which Mergify's `author=` condition
  rejects.
- The `@copilot` nudge comment above initially posted as `mergify[bot]` and
  was silently ignored - confirmed live on PRs #93/#98/#100, 16+ minutes
  with zero response, versus ~3.5 minutes for an identical mention posted
  by a human. GitHub's own docs explain why: "Copilot only responds to
  comments from people who have write access to the repository," and a
  GitHub App's own identity (`mergify[bot]`) doesn't count as a person with
  collaborator write access, regardless of the App's actual installation
  permissions. The rule now uses `bot_account: fupacat` on the `comment`
  action so the mention posts as a real collaborator - Eric explicitly
  approved this after Claude Code's classifier flagged the config change as
  identity-weakening (automation posting under his name without a human
  step each time). A dedicated automation user account (e.g.
  `girdle-automation`), invited as a collaborator and authorized in
  Mergify, is deferred to the backlog as the non-impersonating long-term
  fix - `bot_account` only works with a real User-type GitHub account with
  collaborator write access, not another bot/App identity.
- `.mergify.yml`, `.gitar/config/`, and `.gitar/review/` are kept in-repo
  rather than dashboard-only wherever Gitar/Mergify support it, specifically
  because a dashboard-only setting drifted once already (a Mergify
  dashboard UI edit silently reverted several hand-written `.mergify.yml`
  changes during a merge-conflict resolution) - in-repo config is git-diffable
  and reviewable the same way code is.
- Mergify's own `-conflict` queue condition can get **persistently** stuck
  unmet even when GitHub reports `mergeable: MERGEABLE` and a local
  `git merge` is a genuine no-op - not just transiently stale (fixable
  with an empty-commit push, as on PR #93), but stuck through repeated
  `@mergifyio refresh`, `@mergifyio dequeue` + `@mergifyio queue`, and
  multiple fresh pushes (PRs #97, #98, both 15-20+ minutes). The only
  workaround found: remove and let the conflict-nudge rule (above)
  re-add the `conflict-nudged` label, which forces a full rule
  re-evaluation - worked on #97, didn't on the first attempt for #98.
  `default` queue's `batch_size: 3` does not address this: the `-conflict`
  condition lives in the `queue development PRs` `pull_request_rule` and
  gates queue entry, while batching only applies to PRs already queued.
  Batching affects throughput, not this stuck evaluation.

## Related

- [[.agent-vault/decisions/merge-pipeline-tool-roles-and-paths|merge-pipeline-tool-roles-and-paths]]
- [[.agent-vault/decisions/dependabot-queue-branch-protection-injection-mode|dependabot-queue-branch-protection-injection-mode]]
- [[.agent-vault/decisions/gitar-as-sole-auto-fixer|gitar-as-sole-auto-fixer]]
- [[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]] -
  open question of whether `default` should adopt the Dependabot queues'
  `branch_protection_injection_mode: merge` to stop gating queue entry on
  the full ruleset, plus the (now fixed, 20m) `checks_timeout` on `default`.
