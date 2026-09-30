---
type: ci
watches:
  - path: .github/workflows/gemini-agent.yml
    hash: 3a48239a8e06a99aa7aff58d5d34f99f15944db5ba5fa7775b3e0dd9400469a8
  - path: .github/workflows/gemini-agent-pr.yml
    hash: b44f78c8ef41ff38bf9a96bc93f7cd747d75ee30592333af84ef04f4fce5af74
  - path: .github/scripts/report-agent-failure.sh
    hash: 0155cf0fcae6d7789f6be52408192f004808f0941b6e491c5b756c7e0b7b4641
stale: false
---

# Gemini coding agent (OpenRouter): how it is built and why

A second autonomous implementer next to the Copilot cloud agent, running in
GitHub Actions through [Aider](https://aider.chat) against a Gemini model on
OpenRouter. Built in six small PRs (#382, #385, #388, #391, #394/#396, and the
failure-reporting one) after the first version (#373) turned out to have
blocking bugs and security gaps. Two workflows share one trust model.

## Workflows

- `gemini-agent.yml` - **issue mode.** Triggered by the `agent:gemini` label on
  an issue, an `@gemini` comment on an issue, or `workflow_dispatch`. Opens a
  draft PR on `gemini/issue-N` labelled `agent-pr`.
- `gemini-agent-pr.yml` - **PR mode.** A trusted `@gemini` comment on an
  `agent-pr` PR from a `gemini/` branch changes that PR (conflict resolution,
  review findings, follow-ups). Two repair cycles (`repair:1`, `repair:2`), then
  the PR is labelled `manual`.

## Trust model (why the jobs are split)

- **The model key and the push token never share a job.** The agent job holds
  `OPENROUTER_API_KEY` with a read-only `GITHUB_TOKEN` and no persisted git
  credentials; its only output is a small patch artifact. The publish job holds
  the push token (`AGENT_PR_TOKEN`, a fine-grained PAT with contents and
  pull-requests write only) and never runs the model. PRs opened with
  `GITHUB_TOKEN` would not get CI, which is why a PAT is used.
- **Only text from trusted people reaches the model.** The comment trigger needs
  a trusted commenter and a trusted issue author (`OWNER`/`MEMBER`/
  `COLLABORATOR`); the label trigger needs a trusted issue author (labelling
  already needs triage access). A secret-free `reject-untrusted` job refuses
  the rest. Issue text is fenced behind a per-run random marker, truncated to
  20 kB, and the model is told not to obey it.
- **The publisher validates the patch** before applying it: non-empty, at most
  1 MB, and no change to `.github/workflows/` (agent-authored workflow changes
  need a human).
- **Actions are pinned to full commit SHAs.**
- **PR mode never executes code from the PR branch.** The branch was written by
  an earlier model run, and an `issue_comment` workflow is privileged, so: all
  tooling is installed from a checkout of the default branch; the PR head is a
  separate worktree only read and edited as files; aider gets empty trusted
  config/env files (a `.aider.conf.yml` or `.env` on the branch could run
  commands with the key) plus `--no-auto-test --no-auto-lint`; hygiene runs
  direct formatters, not `pre-commit` (its hooks include pytest); and the
  publisher has **no working tree from the branch at all** - it builds the
  commit with git plumbing on a temporary index and pushes a fast-forward.
  CodeQL (`actions/untrusted-checkout`) flagged each earlier shape, and it is
  not a required check: check it on any change to these workflows.
- **Master is merged into a PR only for a real conflict.** The agent computes the
  merge with `git merge-tree` (no working-tree change; a clean merge is never
  applied, since a proactive sync dismisses approvals). The agent and the
  publisher must pass the two commits **by SHA** in the same order: conflict
  marker labels derive from the arguments, and a mismatch makes the resolution
  patch fail to apply.

## Integration with the rest of the pipeline

- The Copilot sync (`auto-assign-copilot.yml`) skips issues labelled `manual` or
  `agent:gemini`.
- The promote-when-green sweep also considers drafts on a `gemini/` branch that
  carry `agent-pr` (both are required), still only when checks are green, the
  diff is non-empty and there is no conflict.
- Mergify routes a promoted Gemini PR like any other non-Dependabot PR. The
  conflict nudge stays Copilot-only; Gemini conflicts go through PR mode.
- Labels: `agent:gemini` (hand an issue over), `agent-pr`, `repair:1`,
  `repair:2`, `agent:failed`, plus the existing `manual`.

## Failure reporting

A `report-failure` job in both workflows runs
`.github/scripts/report-agent-failure.sh` when the agent or publish job fails:
it comments with the run link, the failed step's name (from the job metadata, available at
once) and the first `##[error]` line from the failed job's log (fetched through the
API and retried briefly, since the log can lag the job; truncated,
backticks and control characters stripped, `@` defused, since the log can echo
model output or issue text) and labels the target `agent:failed`. An OpenRouter
credit or spend-limit error (HTTP 402, "insufficient credits", "key limit
exceeded") also removes the trigger label so the run is not simply re-triggered
into the same failure; a rate limit is reported as such. The comment posted by
`GITHUB_TOKEN` does not itself trigger a run.

## Setup (names only; never put values in this repo)

- Secrets: `OPENROUTER_API_KEY` (set a spending limit on the key in OpenRouter),
  `AGENT_PR_TOKEN` (fine-grained PAT: contents + pull-requests write, this repo
  only). Optional variable: `GEMINI_MODEL` (default
  `openrouter/google/gemini-2.5-pro`).
- Do not reuse `COPILOT_ASSIGN_TOKEN`: it is a broad classic PAT.

## Acceptance-run findings

The first real run (issue #400, label trigger) failed at the Aider step with
`unrecognized arguments: --no-dirty-check` (the flag is `--no-dirty-commits`; a
test now pins every flag passed to aider to a verified list) and proved the
failure reporter: it commented and labelled `agent:failed`, but without the
error line, because the job log was not yet available when the reporter ran
(now retried, and the failed step name is always shown). Also seen: one label
application produced two `labeled` events, and the second run sat pending behind
the job-level concurrency group and would have repeated the model spend; it was
cancelled by hand, so duplicate triggers are a known cost.

The second acceptance pass (issue mode on #400 -> PR #403, then `@gemini` on the
PR) passed issue mode end to end (the agent created the file, the publisher opened a
draft `agent-pr` PR) and found three more defects in PR mode: `aider --config` rejects
an empty file (it must be a YAML mapping, so the stub is `{}`); comments and labels on a PR returned 403
("Resource not accessible by integration") with `issues: write` alone, in both the
GraphQL (`gh issue comment/edit`) and the REST form, so the PR-mode resolve, publish
and report-failure jobs now hold `pull-requests: write` (none of them runs the model
or code from the branch; the agent job stays read-only), and the `repair:N` label is
applied before the push so a labelling failure can never leave an uncounted push;
and aider appends `.aider*` to
`.gitignore` unless the repo already ignores it (now committed).

## Not verified end to end

Everything above was tested by exercising the workflows' own shell scripts on
toy git repos and by unit tests that pin the security properties; none of it has
run on Actions with a real model call yet. The first real run (a
`workflow_dispatch` against a throwaway issue, then an `@gemini` on the
resulting PR, then a forced failure) is the remaining acceptance step and
spends OpenRouter credit.
