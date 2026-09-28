---
type: context
watches:
  - path: src/girdle/hygiene.py
    symbol: check_agent_sandbox_bootstrap
    hash: 97485092dd4ef47bc56cd01d2fd485eee4ce94b0fa735dabe40eecc1b7ac9b31
stale: false
---

# Agent sandbox bootstrap detection design

Raw source material: [[coding-agent-sandbox-bootstrap-conventions-2026-09-26]].

## Context

`check_agent_sandbox_bootstrap` (conditional on `precommit` already being
CONFIGURED - see `check_precommit`) detects whether an AI coding agent's
isolated execution sandbox gets the same local enforcement (`pre-commit install`) a human contributor gets. Three ecosystems are checked, each with
its own sub-check and its own non-obvious trust boundary:

- `_copilot_setup_steps_configured` — GitHub Copilot coding agent
- `_claude_sandbox_hook_configured` — Claude Code
- `_codex_local_environment_configured` — OpenAI Codex's local desktop app

## Decisions

**Copilot: match the job key, not the substring.** `.github/workflows/copilot-setup-steps.yml`
only gets picked up by GitHub's Copilot coding agent if the job is named
*exactly* `copilot-setup-steps` (confirmed via GitHub's own docs) and the file
is present on the default branch. A bare substring check on the file's text
would false-positive on a comment or doc mentioning the tool name without
actually configuring it - the check uses `re.search(r"(?m)^\s*copilot-setup-steps:", text)`,
a YAML mapping-key pattern, instead.

**Claude Code: recommend `SessionStart`, never `WorktreeCreate`.** Per Claude
Code's hooks docs, a `WorktreeCreate` hook *replaces* the default `git worktree` creation step entirely - a custom hook must create the worktree
itself and print its path as the last non-empty stdout line, or Claude Code
gets no path back and worktree creation breaks. This is fundamentally unlike
Copilot's additive `copilot-setup-steps.yml` (which runs *alongside* the
default job, not instead of it). `SessionStart` is the safe, additive
equivalent - it runs before an agent starts working without replacing
anything. The check still counts an existing `WorktreeCreate` hook as
evidence (a real custom creator could fold `pre-commit install` into its
full replacement logic), but the `recommendation` text must never tell a
user to add one just for this - an earlier version of this check did
exactly that and was corrected after review (see the PR #10 review thread
this note's `watches` hash tracks).

**Codex: local desktop `.codex/` is checked; cloud environments are not.**
OpenAI has two distinct environment-setup mechanisms:

- *Cloud* environments (chatgpt.com/codex/settings/environments) are
  configured entirely through OpenAI's web UI, not a repo-committed file -
  invisible to a local file scan, so checking for it would mean either a
  false ABSENT (dishonest) or no way to verify CONFIGURED. Deliberately not
  checked.
- *Local* desktop-app environments (per
  learn.chatgpt.com/docs/environments/local-environment) store their config
  inside a `.codex/` folder at the project root, which "can be checked into
  your project's Git repository" - this one is checked.

The docs never specify an exact filename inside `.codex/` (unlike Copilot's
fixed workflow path or Claude's `settings.json`), so `_codex_local_environment_configured`
can't verify content the way the other two sub-checks do. It requires the
directory to exist *and be non-empty* (`codex_dir.is_dir() and any(codex_dir.iterdir())`)
as the most specific honest claim available - a bare empty `.codex/` (a
stale leftover, or an unrelated tool reusing the name) does not count.

## Consequences

- If Claude Code's hook semantics change (e.g. `WorktreeCreate` becomes
  additive in a future version), this note goes stale relative to its own
  reasoning even if the watched hash doesn't change - re-verify the hooks
  docs before trusting the "never recommend WorktreeCreate" decision as
  still current.
- If OpenAI documents an exact filename inside `.codex/` in the future, the
  non-emptiness check should be tightened to look for that file specifically,
  the same precision the Copilot and Claude sub-checks already have.
