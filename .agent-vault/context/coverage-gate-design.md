---
type: context
watches:
  - path: src/girdle/scan.py
    symbol: _check_coverage_gate
    hash: da4168078e876430317f7261515f8b7b5e96c60316945bb5124a1a1bd5951d61
stale: false
---

# Coverage gate is conditional on both coverage AND ci_gating

## Context

Girdle already scores "coverage" (is a coverage tool configured) and
"ci_gating" (does CI run tests) as separate categories per ecosystem. A
natural follow-up question is whether coverage is actually *enforced* as a
PR-scoped gate (Codecov patch status, Coveralls, `diff-cover --fail-under`,
SonarCloud's "Coverage on New Code" condition) rather than just measured
and reported.

## Decision

The gate check only runs, and only ever produces a finding, when **both**
coverage and ci_gating are already tier >= CONFIGURED for that ecosystem.
Neither half is checked or reported in isolation.

Verbatim from the design discussion that settled this: "that particular
piece should belong to either the coverage check or the ci check but it's
conditional on both, there's no point in flagging coverage gate if there's
no ci config and vice versa."

## Consequences

- A repo with no CI config never sees a "you're not gating coverage"
  recommendation - that finding would be noise with no actionable single
  fix (adding a gate presupposes CI already exists to run it in).
- A repo with coverage tooling but no CI likewise sees nothing about
  gating - same reasoning, mirrored.
- The gate-detection logic (`coverage_gate.detect_gate`) stays fully
  language-agnostic and lives once in `scan.py`, rather than being
  duplicated per ecosystem detector, since Codecov/Coveralls/diff-cover/
  Sonar config files live in CI workflow files regardless of which
  ecosystem's code they're gating.
