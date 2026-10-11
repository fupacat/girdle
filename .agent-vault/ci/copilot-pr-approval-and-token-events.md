---
type: ci
reviewed_at: 2026-10-11
---

# Copilot PRs: who can approve, and why promotion needs a PAT

Two GitHub platform rules that shape how Copilot coding-agent PRs get merged
here. Both cost a debugging round on #512 and #514/#515; neither is visible
from the workflow files alone.

## The requester's approval does not satisfy the ruleset

GitHub does not count an approval from the person who asked Copilot to open
the PR toward a required review. The auto-assign flow assigns Copilot with
the owner's PAT (`COPILOT_ASSIGN_TOKEN`), so the owner is the requester on
every Copilot PR (the PR's `copilot_work_started` event is attributed to
them), and their approval leaves `reviewDecision: REVIEW_REQUIRED` and
`mergeStateStatus: BLOCKED`.

The PR still merges, because the two gates count differently:

- Mergify's `#approved-reviews-by>=1` counts the owner's approval, so the PR
  enters and passes the `light` queue.
- The `master` ruleset lists Mergify's app as a `pull_request`-mode bypass
  actor, so Mergify's merge succeeds despite the GitHub-side block.

So "blocked" in the GitHub UI is expected on an owner-approved Copilot PR; the
real gate is the Mergify queue. A merge path that is not Mergify (manual merge
button, native auto-merge) will not get through.

## Events made with `GITHUB_TOKEN` start no workflows

GitHub does not trigger workflow runs from events caused by `GITHUB_TOKEN`
(other than `workflow_dispatch`/`repository_dispatch`). A step that runs
`gh pr ready` with `GITHUB_TOKEN` therefore produces a `ready_for_review`
event that the Gemini review (`gemini-review-pr.yml`) never sees. That review
has usually already run once on the draft and skipped with `pr-is-draft`, so
the PR waits for a human with no automated review at all.

Every promotion of an agent draft therefore uses
`secrets.AGENT_PR_TOKEN || secrets.GITHUB_TOKEN` (both jobs in
`auto-merge-copilot.yml`, since #505 and #515). The fallback keeps the
workflow working without the secret, at the cost of this symptom returning.
Check for it by looking at who the `ready_for_review` event is attributed
to: the PAT's user is correct, `github-actions[bot]` means the PAT was not
used.

## Interaction

Even with the Gemini review firing, a PR that touches `.github/workflows/`,
`.mergify.yml`, `schema.py` or `detectors/base.py` is high-risk: Gemini
comments but does not approve. Those PRs always come down to the owner's
approval, which is the case covered by the first section.

Related: [[merge-pipeline]], [[gemini-agent]],
[[staged-pr-pipeline-checks-review-repair]].
