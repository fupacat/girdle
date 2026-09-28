---
type: decision
---

# Merge pipeline: tool roles and the three merge paths

## Context

Getting a PR from open to merged has to satisfy a branch ruleset (three
required status checks, one approving review) through some combination of
five tools with genuinely overlapping capabilities: GitHub Actions,
SonarCloud, Gitar, Copilot, and Mergify. Left unassigned, this overlap
(Gitar and Copilot can both review and auto-fix; Copilot's native
auto-merge can compete with Mergify's queue) produces conflicts, not just
redundancy.

## Decision

- **GitHub Actions**: ground truth test/lint/coverage runner, nothing else.
- **SonarCloud**: static-analysis quality gate only.
- **Gitar**: the sole automated PR reviewer and CI-failure auto-fixer.
- **Copilot (PR reviewer)**: backup/manual-only second opinion, nothing
  automated depends on it.
- **Copilot (coding agent)** and **Dependabot**: PR authors only, not part
  of the pipeline itself.
- **Mergify**: the only merge orchestrator - three named queues
  (Dependabot / Dependabot-major / default), self-approves safe Dependabot
  bumps, nudges rebases, labels majors for review.
- GitHub's native "Allow auto-merge" is disabled repo-wide - a second,
  uncoordinated merge path would race against Mergify's queue.

Three merge paths follow from these roles: Dependabot patch/minor/security
-> Mergify self-approves -> `Dependabot` queue; Dependabot major -> real
approval required (Gitar or human) -> `Dependabot-major` queue; everything
else -> Gitar approves -> `default` queue.

## Alternatives considered

- **Consolidating onto GitHub-native tooling** (native merge queue +
  CodeQL + Copilot) to reduce vendor count - researched and rejected.
  GitHub's native merge queue hits the identical Dependabot-checks-don't-
  run-on-their-own-branch problem natively (2026 reports: CodeQL failing
  against the ephemeral merge-queue ref, `GITHUB_TOKEN` unable to enqueue
  PRs, bot PRs failing human-oriented template checks) - it relocates the
  problem, it doesn't remove it, while losing Mergify's per-queue
  granularity the three-path split depends on. CodeQL is also additive to
  SonarCloud (deep security analysis, no quality gate), not a replacement.
- **Running both Gitar and Copilot as automated reviewers/auto-fixers** -
  rejected: risk of two bots pushing competing fix commits to the same
  branch, duplicate findings, doubled Actions-minutes billing. Gitar
  chosen based on observed consistency; Copilot kept as manual fallback.

## Consequences

- The required-approval story is two different mechanisms depending on PR
  type (Mergify self-approve vs. Gitar/Copilot review), not one uniform
  rule - has to stay documented, not rediscovered from scratch.
- A PR sitting open across a `.mergify.yml`/`.gitar/` config change gets no
  automatic re-evaluation - bit this repo twice (PRs #19-22).

## Reference

Full rationale and the `branch_protection_injection_mode`/draft-PR
mechanism that makes Dependabot's queue entry actually work:
[[.agent-vault/ci/merge-pipeline|merge-pipeline]] (watches `.mergify.yml`).
