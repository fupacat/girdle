---
type: research
---

# Coding agent sandbox/environment bootstrap conventions (as of 2026-09-26)

Point-in-time findings from each vendor's own docs, gathered while building
`check_agent_sandbox_bootstrap` (`src/girdle/hygiene.py`). See
`context/agent-sandbox-bootstrap-design.md` for the resulting design
decisions - this note is the raw source material, not kept in sync with it.

## GitHub Copilot coding agent

- Setup runs from `.github/workflows/copilot-setup-steps.yml`; the job
  **must** be named exactly `copilot-setup-steps` or GitHub silently ignores
  the file (confirmed via GitHub's own docs).
- Must be present on the repo's default branch.
- Only certain job fields are customizable: `steps`, `permissions`,
  `runs-on`, `services`, `snapshot`, `timeout-minutes` (capped at 59).
- GitHub Actions workflows do **not** auto-trigger on Copilot's own commits
  by default - a hardcoded gate distinct from the standard fork-PR-approval
  gate (verified empirically: the `/approve` API endpoint explicitly refused
  a Copilot-authored run, saying "not from a fork pull request or queued by
  the Actions bot"). A repo admin must turn this off at Settings > Copilot >
  Coding agent > "Require approval for workflow runs" - UI-only, no
  REST/`gh` CLI endpoint found for it despite probing several plausible ones.

## OpenAI Codex

Two distinct, non-overlapping mechanisms:

- **Cloud environments** (chatgpt.com/codex/settings/environments): setup
  script + optional "maintenance" script (for cache-resumed containers),
  configured entirely through OpenAI's web UI. Not a repo-committed file -
  confirmed via direct fetch of OpenAI's own docs.
- **Local desktop-app environments**
  (learn.chatgpt.com/docs/environments/local-environment): configured
  through the ChatGPT desktop app's settings pane (`codex://settings`).
  Quotes from the page:
  - "Codex stores this configuration inside the `.codex` folder at the root
    of your project."
  - "You can check the generated file into your project's Git repository to
    share with others."
  - "Setup scripts run automatically when Codex creates a new worktree at
    the start of a new chat."
  - "Use this script to run any command required to configure your
    environment, such as installing dependencies or running a build
    process."
  - "If your setup is platform-specific, define setup scripts for macOS,
    Windows, or Linux to override the default."
  - The page does **not** specify an exact filename or format (YAML/JSON/
    TOML) for what's inside `.codex/`.

## Claude Code

- Real analog to Copilot's setup file is the `WorktreeCreate`/
  `WorktreeRemove` hook pair in `.claude/settings.json` - not `SessionStart`,
  which is a much looser "any session start" signal.
- Per Claude Code's own hook docs (confirmed via a review bot's finding,
  Gitar, during PR #10's review - consistent with this research): a
  `WorktreeCreate` hook **replaces** the default `git worktree` creation step
  entirely. A custom hook must create the worktree itself and print the
  resulting path as the last non-empty stdout line, or Claude Code gets no
  path back and worktree creation breaks.
