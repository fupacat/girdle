---
type: context
---

# Dashboard scoring redesign - backlog

Living checklist of candidate work items surfaced by
[[.agent-vault/brainstorm/dashboard-scoring-tiers-2026-09-28|dashboard-scoring-tiers-2026-09-28]]
(the narrative brainstorm - read that for the *why* behind each item).
Nothing here is committed scope; this is "known candidates," not a
roadmap. Update status inline as items move (`todo` -> `in-progress` ->
`done`, or `dropped` with a one-line reason) rather than deleting rows,
so the record of what was considered and why survives.

## New checks (surfaced while calibrating difficulty tiers)

- [in-progress] **Malicious/poisoned agent instructions detection** -
  [issue #80](https://github.com/fupacat/girdle/issues/80), unassigned
  (depends on #73). Routes through the same active-harm/red bucket as
  secrets detection, not the percentage/badge model. `find_agent_instruction_hazards`
  scans discovered instruction files for zero-width Unicode characters,
  unusually long base64-like or hex-like blobs, and concrete manipulative
  directives: requests to ignore prior instructions, reveal system/developer
  messages or hidden instructions, or conceal information from the user.
- [in-progress] **SAST/static-analysis-configured check** -
  [issue #79](https://github.com/fupacat/girdle/issues/79), unassigned
  (depends on #73). Distinct from `lint`.

## New pillars (from the Factory.ai Agent Readiness comparison)

- [in-progress] **Build System** - [issue #78](https://github.com/fupacat/girdle/issues/78),
  unassigned (depends on #73). Confirm whether girdle already scores
  deterministic build commands, or whether this is a genuine gap.
- [ ] **Debugging & Observability** (structured logging, tracing,
  metrics) - genuine gap, no existing girdle category. Needs its own
  design pass (what's deterministically checkable here - structured
  logging library present? a tracing/APM config file? this hasn't been
  scoped at all yet).
- [ ] **Task Discovery** (infrastructure for an agent to autonomously
  find and scope work - distinct from human-facing issue templates)
  - genuine gap, new angle, not scoped at all yet.

## Alignment-ladder infrastructure

- [ ] Shared command-extraction-and-diff mechanism (README/CONTRIBUTING/
  agent-instructions alignment) - scope is settled (presence + staleness
  of referenced names/paths, not command-syntax validation - see the
  brainstorm note), implementation not started.
- [ ] Per-category "adequate"/"aligned" checks for README, CONTRIBUTING,
  CODEOWNERS, `.gitignore`, dependency monitoring, agent instructions,
  agent sandbox bootstrap, structural index - bars are defined
  (brainstorm note), none implemented yet. LICENSE moved to its own
  filed issue, see below.
- [in-progress] Three alignment-check candidates, surfaced while
  enumerating every existing category against the code directly:
  `ci_gating` vs. `tests` - [issue #81](https://github.com/fupacat/girdle/issues/81);
  `reproducibility` lockfile drift - [issue #82](https://github.com/fupacat/girdle/issues/82);
  `precommit` vs. CI - [issue #83](https://github.com/fupacat/girdle/issues/83).
  All unassigned, depend on #74.
- [in-progress] LICENSE presence/adequate/aligned, including the
  `licensee`-style deterministic license-text fingerprinting question -
  [issue #84](https://github.com/fupacat/girdle/issues/84), unassigned
  (depends on #73).
- [ ] `platform.py`'s branch-protection/ruleset checks don't fit the tier
  model at all today - separate `PlatformResult` structure, not
  `CategoryResult`/tier-based. Decide whether to unify it into the same
  category/tier system or leave it as its own thing.
- [ ] Design/decision-notes category - needs its own lower-confidence
  presentation design (can't use the same flat absent/configured/aligned
  claim as everything else - see brainstorm note's reasoning).

## Personal/machine-local artifact detection

- [ ] Detector design for known personal-config patterns per tool
  (`.claude/settings.local.json`, `.idea/`, `.DS_Store`, `Thumbs.db`,
  etc.) - routes through `ScanResult.warnings`, settled.
- [ ] Secrets detection - **bigger scope question than the rest of this
  list**: a real implementation (entropy/pattern-based scanning) is a
  different order of engineering than a gitignore-style presence check.
  Routes through the existing category min-gate when found (settled),
  but the detection mechanism itself isn't designed.

## Deferred community-standards cluster

- [ ] SECURITY.md, CODE_OF_CONDUCT.md, issue/PR templates, FUNDING.yml -
  named, explicitly lower priority than LICENSE (no legal-ambiguity
  consequence). Not scoped further than "add to taxonomy eventually."

## Presentation / visual design

- [x] Aggregate-vs-per-category scoring - **resolved**: compute both,
  percentage per category and percentage overall, not an either/or (see
  brainstorm note's percentage-of-checks-passed model).
- [x] Color model - **resolved**: neutral by default (including
  `absent`), badge colors only once a badge tier is earned, red reserved
  specifically for active-harm findings (secrets, malicious agent
  instructions) rather than mere incompleteness.
- [in-progress] The actual percentage/badge-tier dashboard
  implementation - filed as [issue #72](https://github.com/fupacat/girdle/issues/72)
  (tracking) with four ordered sub-issues:
  [#73](https://github.com/fupacat/girdle/issues/73) (check registry,
  assigned to Copilot, PR #77 open), [#74](https://github.com/fupacat/girdle/issues/74)
  (percentage computation), [#75](https://github.com/fupacat/girdle/issues/75)
  (color-state logic), [#76](https://github.com/fupacat/girdle/issues/76)
  (dashboard template). All dependency links are now real GitHub
  `blockedBy` relations (set via `addBlockedBy`, verified against the
  live GraphQL schema), not just prose - see
  [issue #85](https://github.com/fupacat/girdle/issues/85) below.
- [in-progress] **Auto-assign unblocked issues to Copilot on a timer** -
  [issue #85](https://github.com/fupacat/girdle/issues/85), assigned to
  Copilot. A scheduled GH Actions workflow that queries `blockedBy` on
  open unassigned issues and assigns anything unblocked - once this
  lands, moving the #72 chain forward stops needing manual
  reassignment after each merge. Researched first: GitHub's
  `blockedBy`/`blocking` `IssueConnection` fields and the
  `addBlockedBy`/`removeBlockedBy` mutations are real and confirmed via
  direct schema introspection (search results disagreed with each other
  on the mutation name - `addIssueDependency` does not exist despite
  appearing in some sources).

## Already unblocked / in motion

- [x] Wire `--run` into the `pages` CI job so `tests`/`lint`/`coverage`
  can actually show `verified` - [issue #69](https://github.com/fupacat/girdle/issues/69),
  filed and assigned to Copilot. Still directly useful under the new
  model too - `verified` still needs to mean something within whichever
  category counts `tests`/`lint`/`coverage`.
- [dropped] **"Option A" dashboard color fix** - dropped, not shipped.
  Originally: stop coloring `configured` as alarm-yellow, no new labels/
  detection, dashboard template/CSS only. Superseded by the fuller
  percentage/tier model above, which answers the same original complaint
  more completely - confirmed moot rather than worth shipping as an
  interim step.

## Related

- [[.agent-vault/brainstorm/dashboard-scoring-tiers-2026-09-28|dashboard-scoring-tiers-2026-09-28]] -
  the narrative reasoning behind every item above.
