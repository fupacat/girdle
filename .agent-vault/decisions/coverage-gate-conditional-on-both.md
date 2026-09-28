---
type: decision
---

# Coverage gate check fires only when both coverage AND ci_gating are already configured

## Context

Girdle scores "coverage" (is a coverage tool configured) and "ci_gating"
(does CI run tests) as separate categories per ecosystem. A natural
follow-up question is whether coverage is actually *enforced* as a
PR-scoped gate (Codecov patch status, Coveralls, `diff-cover --fail-under`,
SonarCloud's "Coverage on New Code" condition), not just measured.

## Decision

The gate check only runs, and only ever produces a finding, when **both**
coverage and ci_gating are already tier >= CONFIGURED for that ecosystem.
Neither half is checked or reported in isolation. Verbatim from the design
discussion that settled this: "that particular piece should belong to
either the coverage check or the ci check but it's conditional on both,
there's no point in flagging coverage gate if there's no ci config and
vice versa."

## Alternatives considered

- **Reporting coverage-gate status independently of whether CI/coverage
  are configured at all** - rejected: a repo with no CI config would see
  a "you're not gating coverage" recommendation that's pure noise - adding
  a gate presupposes CI already exists to run it in.

## Consequences

- A repo with coverage tooling but no CI sees nothing about gating either
  - same reasoning, mirrored.
- `coverage_gate.detect_gate` stays fully language-agnostic, living once
  in `scan.py` rather than duplicated per ecosystem detector, since
  Codecov/Coveralls/diff-cover/Sonar config files live in CI workflow
  files regardless of which ecosystem's code they're gating.

## Reference

Full design detail:
[[.agent-vault/context/coverage-gate-design|coverage-gate-design]] (watches
`src/girdle/scan.py#_check_coverage_gate`).
