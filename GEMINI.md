# Gemini Coding Agent Guidelines

This repository uses [AGENTS.md](AGENTS.md) as the single source of truth for agent guidelines and repo architecture.

## Repository Invariants:

1. **Always run formatting and pre-commit checks**:
   - `girdle index . --inject AGENTS.md` (keep index in sync if files/symbols change)
   - `girdle notes check .` (find stale `.agent-vault/` notes; `girdle notes ack <note>` only after comparing the note with your change)
   - `pre-commit run --all-files`
1. **Never open or finish an empty PR**: If requested work already exists on master, state so clearly.
1. **Discrete, minimal diffs**: Keep changes scoped strictly to the requested issue.
1. **Draft PRs**: All automated agent pull requests must be created as Draft PRs to avoid racing the automated review and merge queue systems (Gitar and Mergify).
