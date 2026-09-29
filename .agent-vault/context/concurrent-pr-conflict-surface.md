---
type: context
---

# Concurrent-PR conflict surface - a shared root cause

Not committed scope yet - live design discussion, recorded so the
reasoning survives across sessions. This note ties together three
symptoms found separately and names the working hypothesis about what
they have in common; none of the three has an implementation plan yet.

## Goal

Merge velocity was high before these conflicts started showing up. The
goal isn't just "stop the conflicts" - it's to get back to that velocity
*with* a guarantee that what lands on `master` still works, rather than
trading speed for safety (or vice versa) the way slowing down the queue
or loosening checks would. Any fix proposed for the symptoms below should
be judged against both: does it remove the collision, and does it
preserve (or restore) throughput rather than just adding more serialized
gates.

**Evidence check (2026-09-29) - important correction**: the one sharp,
large velocity drop found in PR history (leads jumping from
single-digit/low-double-digit minutes to up to ~11.5 hours, PRs #93-104,
all `copilot-swe-agent`-authored, opened within one 17-minute window on
2026-09-28 15:35-15:52 UTC) was a **single concentrated incident** - a
burst of ~12 simultaneous Copilot PRs overwhelming the then-unbatched
single-lane `default` queue (no `batch_size` yet, full ruleset re-run per
PR, no `checks_timeout`) - not evidence of gradual, ongoing degradation
from the three design issues below. CI failure rate spiked to 27% in
that exact hour (vs. near-zero in adjacent hours) and recovered by
#109-114 as the queue drained, ~6 hours later. `batch_size: 3` was added
afterward, in PR #123, whose own commit message cites #93/#97/#98 stuck
behind a `-conflict` evaluation as the trigger - it's a *response* to
this incident, not its cause, and postdates it by hours. No PR in this
slowdown window showed a vault-check or index-conflict failure
specifically. Doesn't invalidate the three symptoms below (the
`AGENTS.md` churn evidence in particular shows a real, separate,
recurring cost - see that note), but the big velocity number itself
traces to queue congestion from a PR burst, not to any of the three
design issues on its own.

## The three symptoms

- [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]] -
  vault notes with content-hash `watches` go falsely stale when an
  unrelated concurrent PR (or a batched Mergify merge, see
  [[.agent-vault/ci/merge-pipeline|merge-pipeline]]) touches the same
  watched file, blocking CI for reasons unrelated to documentation
  accuracy.
- [[.agent-vault/context/generated-index-churn|generated-index-churn]] -
  the structural index embedded in `AGENTS.md` is regenerated wholesale
  from full-repo state and reordered by symbol count, so unrelated
  concurrent PRs produce literal merge conflicts in the same shared file.
- **`src/girdle/schema.py` as a hot file** - it's the declared
  single-source-of-truth for scan output (`ScanResult`/`EcosystemResult`),
  which makes it the natural place for every feature that adds a new
  scored dimension (dashboard scoring, audit results, hygiene checks,
  platform checks) to add a field. Ordinary hand-written-code merge
  conflicts, not a generated-artifact or hash-drift problem like the
  other two, but the same shape: one shared file, many concurrent
  editors, high conflict probability under batching. **Evidence check
  (2026-09-29, repo is 7 days old): nuanced, not fully confirmed.**
  By commit density, `schema.py` is #2 (0.063 commits/line), just behind
  `scan.py` (0.065) - part of a small hot cluster
  (`scan.py`/`schema.py`/`checks.py`), not uniquely singled out. By
  merged-PR touch count, `hygiene.py` actually leads (10 PRs) ahead of
  `schema.py` (5 PRs). One real same-day near-collision found: PR #93 and
  #94 both reworked scoring/percentages in `schema.py` ~5.5 hours apart
  on 2026-09-28 - two competing feature reworks landing in parallel, not
  steady organic field accretion. No explicit conflict-resolution commit
  found on `schema.py` itself (unlike the confirmed `AGENTS.md` conflict
  trail below). Read as: real hot-file pressure exists, but it's spread
  across a cluster of small "wiring" files, not concentrated uniquely on
  `schema.py` - worth broadening the decomposition question to
  `scan.py`/`checks.py`/`hygiene.py` too, not just `schema.py`.

## Working hypothesis

The common thread isn't any one mechanism (hashing, wholesale
regeneration, or organic feature growth) - it's that all three funnel
unrelated changes through one shared file/artifact, and Mergify's queue
(batching several PRs' speculative merges together, see
merge-pipeline note) multiplies how often unrelated changes actually
land close enough together to collide.

Eric's proposed direction: **decompose the application into smaller
modules**, so any given change touches a narrower slice of the codebase
and fewer PRs' diffs actually overlap on the same file - plus **CI
scoping rules** (not yet specified - candidates would be path-based
ownership/review scoping, or narrowing what a single PR/batch is allowed
to touch at once) as a second layer on top of decomposition rather than
instead of it.

**Complementary**: keep each PR's own change minimal - break tasks into
the smallest discrete changes practical, rather than one PR bundling a
whole feature (module decomposition narrows *where* collisions can
happen; minimal PRs narrow *how much* each one touches, so even within a
hot file two PRs are more likely to land on genuinely disjoint lines).
Two consequences flagged as probably necessary, not yet designed:

- **More coordination/sequencing** between PRs/agents - smaller PRs
  land more often, so whatever plans the work needs to know what order
  dependent pieces land in and what's already merged vs. still pending.
- **Some form of feature flagging** - a discrete change that's part of a
  larger feature will often need to merge before the feature is
  user-visible/complete, so incomplete-but-safe intermediate states need
  a way to exist on `master` without breaking anything - name/shape of
  that mechanism not decided (could be as light as an unused/dead code
  path behind a constant, or a real flag system; girdle has no existing
  feature-flag mechanism to build on).

## External validation (web research, 2026-09-29)

The minimal-PR/coordination/feature-flag direction matches established
practice, not a novel scheme:

- **Trunk-based development**: "integration pain scales with branch
  lifetime... merge conflicts nearly disappear when branches live for
  hours" ([GitKraken, 2026
  guide](https://gitkraken.com/blog/prevent-merge-conflicts-in-small-teams-2026-guide);
  [Optimizely
  glossary](https://www.optimizely.com/optimization-glossary/trunk-based-development)).
  Short-lived branches and small diffs are the standard lever for
  exactly the collision-probability problem this note is about - not
  just a style preference.
- **Feature flags as the standard enabler**: "feature flags let you
  merge incomplete code to main without exposing it to users... which
  keeps your branch close to main and dramatically reduces conflict
  risk" ([Unleash docs on trunk-based
  development](https://docs.getunleash.io/guides/trunk-based-development);
  [DevCycle](https://devcycle.com/blog/transitioning-to-trunk-based-development)).
  Confirms flagging is the expected companion to minimal PRs, not an
  extra complication layered on for no reason - the two are usually
  adopted together.
- **General framing** ([Jonathan Hall, "Avoid merge conflicts, don't
  manage them"](https://jhall.io/posts/2023-09-11-avoid-merge-conflicts/)):
  the goal is structuring work so conflicts are structurally less likely,
  not getting better at resolving them - the same framing already used
  in [[.agent-vault/context/generated-index-churn|generated-index-churn]]'s
  research section, reinforcing that decomposition + minimal PRs +
  feature flags is one coherent strategy, not three separate ideas.

Also useful vocabulary from Mergify's own docs (see
[[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]]):
an "RCV" trade-off (Reliability, Cost, Velocity - pick two). The Goal
above is implicitly asking for reliability + velocity, which per that
framing means accepting some CI cost as the dial to turn (parallel
speculative checks, not sequential validation or aggressive batching) -
worth stating explicitly when any of these fixes get scoped, so the
trade-off is chosen on purpose rather than by omission.

## Not yet decided

- Whether `schema.py` specifically should be split (e.g. per-category
  result types in their own modules, composed rather than one growing
  dataclass file) - no design done yet, and the module's own
  single-source-of-truth framing
  ([[.agent-vault/context/audit-design.md]],
  [[.agent-vault/decisions/girdle-audit-command-design.md]]) needs to
  survive any split intact.
- What "CI scoping rules" concretely means here - could be a Mergify
  queue_conditions change (e.g. don't batch PRs that touch the same
  hot file together), a CODEOWNERS-style serialization rule, or
  something else. Not scoped.
- Whether the vault-hash and index-churn fixes (both trending toward
  "compare against this PR's own diff, not global/rebased state" per the
  other two notes) are actually a *substitute* for decomposition here, or
  complementary - decomposition reduces how often collisions happen at
  all; the other two notes' fixes change how a collision is handled once
  it happens. Likely both are wanted, but not confirmed.

## Priority ranking, based on evidence (2026-09-29, revised)

All four related notes now have evidence attached. Ranked by confirmed
urgency, not by theoretical severity. **Revised** from the first pass:
[[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]
moved from "lowest urgency" to tied-highest after a follow-up search of
PR review comments (not just CI logs) found real occurrences the first
pass missed - see that note's evidence section.

1. \*\*[[.agent-vault/context/generated-index-churn|generated-index-churn]]
   and
   [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]
   - tied highest priority, both confirmed-acute, both point toward the
     same diff-scoped fix shape.\*\* Index-churn: 11+ explicit
     conflict-resolution commits on `AGENTS.md`, two forced empty-commit
     re-evaluations, dedicated Mergify bot automation built to fight it
     (worked example: `74f0730`). Vault-freshness: real rebase-staleness
     hits caught in code review (PR #123's Gitar/Copilot comments show the
     hash going stale purely from absorbing an unrelated master-merge
     change, not from PR #123's own edits), plus one reported batch
     bisected by the check failing on every composite speculative merge.
     Worth scoping and fixing together given the shared fix shape.
1. \*\*[[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]]
   - high priority.\*\* Confirmed concretely: one PR (#104) had its full
     `test` job (incl. SonarQube scan) run three times before merging.
     Also the mechanism that turned the one real velocity-drop incident
     below into an ~11.5-hour delay (no `checks_timeout`, full ruleset
     gating queue entry) - fixing this is what prevents a repeat, even
     though the incident itself wasn't caused by the other three issues.
1. **`schema.py` / hot-file decomposition - medium, and broader than
   scoped.** Real pressure confirmed, but spread across a small cluster
   (`scan.py`, `schema.py`, `checks.py`, and `hygiene.py` by PR-touch
   count) rather than concentrated on `schema.py` alone. Worth folding
   into the decomposition question as a cluster, not a single-file fix.

Also confirmed: the one large, sharp velocity drop found in PR history
(#93-104) was a single queue-congestion incident from a simultaneous
Copilot PR burst, not gradual degradation from these four issues - see
the "Goal" section's evidence note above.

## Related

- [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]
- [[.agent-vault/context/generated-index-churn|generated-index-churn]]
- [[.agent-vault/ci/merge-pipeline|merge-pipeline]]
- [[.agent-vault/ci/queue-entry-cost-and-timeouts|queue-entry-cost-and-timeouts]] -
  a fourth angle on the same velocity goal: the full ruleset gates queue
  *entry* (not just merge) for the `default` queue, and there's no
  `checks_timeout` bounding a stuck/conflicted branch.
