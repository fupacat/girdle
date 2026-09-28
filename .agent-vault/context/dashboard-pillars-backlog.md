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

- [ ] **Malicious/poisoned agent instructions detection** - checking
  AGENTS.md/CLAUDE.md/etc. for injection-style content (hidden
  instructions, suspicious encoded blocks). Routes through the same
  active-harm/red bucket as secrets detection, not the percentage/badge
  model.
- [ ] **SAST/static-analysis-configured check** - distinct from `lint`.
  Girdle dogfoods SonarCloud itself but doesn't score "does a repo have
  CodeQL/Semgrep/similar configured" as its own category today.

## New pillars (from the Factory.ai Agent Readiness comparison)

- [ ] **Build System** - confirm whether girdle already scores
  deterministic build commands under an existing per-ecosystem check, or
  whether this is a genuine gap. Lowest-effort item on this list - a
  verification question, not new design.
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
  CODEOWNERS, `.gitignore`, dependency monitoring, LICENSE, agent
  instructions, agent sandbox bootstrap, structural index - bars are
  defined (brainstorm note), none implemented yet.
- [ ] Three more alignment-check candidates, surfaced while enumerating
  every existing category against the code directly (not previously
  named anywhere): `ci_gating` vs. `tests` (does the CI-detected test
  command match `tests`'s own configured command?), `reproducibility`
  (does the lockfile match the manifest - no version drift?), and
  `precommit` vs. CI (does pre-commit wire the *same* checks CI actually
  runs, or a silently diverging subset?).
- [ ] `platform.py`'s branch-protection/ruleset checks don't fit the tier
  model at all today - separate `PlatformResult` structure, not
  `CategoryResult`/tier-based. Decide whether to unify it into the same
  category/tier system or leave it as its own thing.
- [ ] `licensee`-style deterministic license-text fingerprinting -
  evaluate whether a suitable library exists for girdle's Python stack,
  or whether this means shelling out / vendoring license-text data.
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
- [ ] The actual percentage/badge-tier dashboard implementation - this is
  now the real scope, superseding the smaller "Option A" color-only fix
  below. Needs: per-category and overall percentage computation
  (checks can belong to multiple categories, double-counting is
  intentional), the three-tier check-difficulty system (basic/
  intermediate/advanced, draft assignment in the brainstorm note), the
  neutral/red/badge color states, and the per-category "what's left"
  outstanding-items list the user asked for as the actionable output.

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
