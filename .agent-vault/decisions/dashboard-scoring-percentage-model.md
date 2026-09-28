---
type: decision
---

# Dashboard scoring: percentage-of-checks-passed, not a rigid per-category ladder

## Context

Girdle's dashboard showed most categories as `configured` (yellow), reading
as a warning even on a well-built repo, because most categories have no
`verified` rung to climb to at all. An initial redesign explored a strict
bronze/silver/gold ladder per category (configured -> adequate -> aligned).

## Decision

Score = percentage of applicable checks passed, computed both per-category
and overall, not a rigid 3-rung ladder. Categories are many-to-many
groupings of checks (a check can count toward multiple categories, and
double-counting is intentional weighting, not deduplicated). Check
difficulty (basic/intermediate/advanced) is a static property of the check
itself, independent of category, and gates badge levels by passed checks at
difficulty bands, not by arbitrary percentage thresholds: bronze requires
all BASIC checks to pass, silver requires all BASIC and INTERMEDIATE checks
to pass, and gold requires all non-reserved checks to pass. Color model:
neutral by default (including a category at 0%), badge colors only once a
tier is earned, red reserved specifically for active-harm findings
(secrets, malicious agent instructions) - never for mere incompleteness.

## Alternatives considered

- **Strict bronze/silver/gold ladder per category** - rejected. Adding a
  new check later would mean deciding "is this now bronze, silver, or
  gold" for every category it touches - brittle, and doesn't accommodate
  checks of different weight without inventing per-rung criteria by hand.
- **Option A: pure color recolor, no new model** (stop coloring
  `configured` as alarm-yellow, keep existing absent/configured/verified
  labels) - considered as a quick interim fix, then dropped as moot once
  the percentage model was designed, since it answers the same complaint
  more completely.
- **Aggregate-only or per-category-only scoring** - rejected in favor of
  computing both; not an either/or.

## Consequences

- Extensibility: a new check just gets added to a category and a
  difficulty tier; scores recalculate. No per-category rung redesign
  needed each time.
- The two-ladder split (verification: `configured`->`verified` for
  execution-provable checks; alignment: the old bronze/silver/gold framing)
  is superseded as the overall scoring mechanism, though the underlying
  per-category adequate/aligned bars it produced are still valid and feed
  into this model as the check list itself.

## Reference

Full reasoning, market research (OpenSSF Scorecard/Best Practices Badge,
SonarQube, Socket.dev, Lighthouse), and the Factory.ai Agent Readiness
comparison:
[[.agent-vault/brainstorm/dashboard-scoring-tiers-2026-09-28|dashboard-scoring-tiers-2026-09-28]].
Living backlog of implementation work:
[[.agent-vault/context/dashboard-pillars-backlog|dashboard-pillars-backlog]].
Implementation: `src/girdle/checks.py` (issue #73) and
`src/girdle/schema.py`'s scoring additions (issue #74) - no `context/`-type
note watches these yet, which is itself a gap worth closing once the
scoring rework (issues #72, #75, #76) finishes landing.
