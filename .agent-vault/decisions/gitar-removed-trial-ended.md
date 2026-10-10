---
type: decision
---

# Gitar is removed: its trial ended

Supersedes [[.agent-vault/decisions/gitar-as-sole-auto-fixer|gitar-as-sole-auto-fixer]]
and the Gitar roles in
[[.agent-vault/decisions/merge-pipeline-tool-roles-and-paths|merge-pipeline-tool-roles-and-paths]].

## Context

Gitar was the sole automated reviewer, approver and CI-failure auto-fixer. On
2026-10-10 its bot began answering every PR with a free-plan notice and posted no
review or approval, so PRs sat at `REVIEW_REQUIRED` with nobody to approve them.
`master`'s ruleset requires only `test`, `SonarCloud Code Analysis` and one
approving review. Gitar was never a required status check, so removing it breaks
no ruleset condition; what disappears is the approver.

## Decision

Remove Gitar and replace each of its roles with something the repo already
runs or controls:

- **CI-failure repair**: the `@gemini` PR-mode workflow, following
  `.github/review/repo-check-repairs.md` (moved from `.gitar/instructions/`).
- **Review and approval**: a Gemini review workflow that posts the approving
  review. Not built yet; until it exists, a human approves non-Dependabot PRs.
  Mergify still self-approves safe Dependabot bumps.
- **Risk triage and review conventions**: kept as plain guidance in
  `.github/review/`, readable by any reviewer.

The Mergify rule that labelled every PR `gitar-managed` is deleted. Copilot's
reviewer stays a manual second opinion, as before.

## Alternatives considered

- **Pay for Gitar**: rejected by the maintainer; the trial is over and the same
  work can be done with tools already in the repo.
- **Copilot as approver**: its reviewer only leaves `COMMENTED` reviews, so it
  cannot satisfy the approval requirement.
- **Remove the approval requirement from the ruleset**: out of scope here; it is
  a maintainer decision about the ruleset, not a repo change.

## Consequences

- Until the Gemini review workflow lands, every non-Dependabot PR needs a human
  approval, and Mergify's queue will wait for it.
- Older notes still describe Gitar in the past tense of their own time; this note
  is the current position.
