---
type: ci
watches:
  - path: .github/workflows/gemini-agent.yml
    hash: 42ff82c7aaabdb970f3ee6550d650d39e1eb1cdb9a32671462e54cb46d09108e
  - path: .github/workflows/gemini-agent-pr.yml
    hash: d0adeb0b8e4075fa9f38d3703160cdf26d011382d67059692ee019518ccae0e1
  - path: .github/scripts/report-agent-failure.sh
    hash: bc4b12791212df508b3bc75e43a8e1fc7ed9a86c655526db5f79a104ca9571e9
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

A `report-failure` job in both workflows runs `.github/scripts/report-agent-failure.sh`
when the agent or publish job fails: it comments with the run link, the failed step's
name (from the job metadata, readable mid-run) and, when the model step failed, the
first error line, and labels the target `agent:failed`. An OpenRouter credit or
spend-limit error (HTTP 402, "insufficient credits", "key limit exceeded") also
removes the trigger label so the run is not simply re-triggered into the same
failure; a rate limit is reported as such.

**The model failure is classified in the agent job, not by the reporter.** A run's job
logs cannot be read through the API until the whole run has completed, and the
reporter runs inside the run, so it cannot classify from the log (the first reports
had no error line, and a spend limit could never have been detected). The agent job
has the model's output on disk: the aider step tees it to a file, an
`if: failure()` step runs `classify-agent-failure.sh` (shared helpers in
`agent-failure-lib.sh`), and the result is exposed as the `failure_kind` and
`failure_error` job outputs that the reporter reads. The error text is untrusted (it
can echo model output or issue text): truncated, stripped of control characters and
backticks, `@` defused. **aider exits 0 on a provider error** (a bad model id, exhausted credits, a rate limit:
it prints `litellm.BadRequestError: OpenrouterException ...` and carries on), which
made the forced bad-model run look like "the agent changed nothing". So after the
patch step, when nothing was produced, a `--silent` classification checks the
output for a provider error and, only then, fails the job with the real reason; a run
that simply had nothing to change is left alone. The OpenRouter user id is scrubbed
from the posted text. A failure in any other step or job is reported as a plain
failure with its step name. A comment posted by `GITHUB_TOKEN` does not itself
trigger a run. `workflow_dispatch` accepts a `model` override (also how to force a
real model error for a test).

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

The first real task (#412: add `permissions` to a `ci.yml` job) produced the correct
change, which the publisher correctly refused because it edits `.github/workflows/`:
**workflow-file tasks are out of scope for this agent** (and the PAT lacks the `workflows`
scope GitHub would require anyway); it is for `src/`, `tests/` and docs. The same patch
also carried a note-frontmatter flip the agent never made: `girdle notes check`
rewrites `stale: false` -> `stale: true` in a stale note as a side effect, and the
hygiene step's checks ran before the patch was collected. The fixer pass now skips the
check-only hooks and whatever the checks write is discarded (issue mode: `git checkout -- .`; PR mode: snapshot the tree and `read-tree --reset` back).

## Not verified end to end

Everything above was tested by exercising the workflows' own shell scripts on
toy git repos and by unit tests that pin the security properties; none of it has
run on Actions with a real model call yet. The first real run (a
`workflow_dispatch` against a throwaway issue, then an `@gemini` on the
resulting PR, then a forced failure) is the remaining acceptance step and
spends OpenRouter credit.
