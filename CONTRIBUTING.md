# Contributing

girdle is a solo personal project, but the workflow below is the same one
used to develop it — useful if you're forking it or sending a PR.

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Running checks

```bash
ruff check .
mdformat --check --wrap keep $(git ls-files '*.md')
yamllint .
pytest
girdle index . --check AGENTS.md
girdle notes check .
```

All six also run automatically on local `git commit` via
`.pre-commit-config.yaml` (see the README's "Enforcement hooks" section)
and again in CI on push/PR - though CI's notes check is read-only
verification (no staged files in a clean checkout, so nothing
auto-reconciles there), catching a `--no-verify` bypass of the local
hook rather than re-running its auto-reconcile behavior. `mdformat` (no
`--check`) rewrites files in place; the pre-commit hook does this for
you, same as `ruff --fix`.

For GitHub Copilot coding-agent commits specifically, do **not** assume
the local pre-commit hook is an enforced gate: those commits are not
guaranteed to be created via local `git commit`. Treat CI status checks
as the authoritative enforcement boundary for agent-authored commits.

## Pull request scope

Keep each PR to one discrete, reviewable change - break a larger feature
into the smallest mergeable steps rather than landing it as one PR, and
land plumbing/refactoring separately from the behavior change it enables.
If a step needs to merge before the feature it's part of is complete or
user-visible, land it inert (unreferenced code, or gated behind a flag)
rather than holding the PR open until everything is ready. Rationale and
the merge-queue friction this addresses:
`.agent-vault/decisions/minimal-discrete-pr-policy.md`.

## Branch protection

`master` is protected, including for admins: changes land via a PR with
three passing status checks (`test`, `SonarCloud Code Analysis`, `Gitar`)
and one approving review. Direct `git push` to `master` will be rejected,
even from the repo owner — open a branch and PR instead.

Merging itself goes through Mergify's queue, not GitHub's native
auto-merge (disabled repo-wide) or a manual merge button. The required
review is satisfied by Gitar's automated review (or Mergify self-approving
for low-risk Dependabot bumps) rather than a human, since this is a
single-author repo. Full rationale for how Mergify, Gitar, SonarCloud,
Copilot, and GitHub Actions divide the work — and why — is in the
`.agent-vault/ci/merge-pipeline.md` vault note.

## Adding a new ecosystem detector

New ecosystem support = a new file in `src/girdle/detectors/` implementing
the `Detector` protocol (`detectors/base.py`), registered in
`detectors/registry.py`. See `AGENTS.md` and the `Agent-Ready Repository Design` vault note for the design rationale and the full detection matrix
before adding scoring behavior.

## Regenerating pinned dependencies

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
pip-compile --extra dev pyproject.toml -o requirements-dev.txt
```

## Regenerating the structural index

The `<!-- girdle:index:start -->` block in `AGENTS.md` is mechanically
generated, not hand-edited:

```bash
girdle index . --inject AGENTS.md
```

CI and the pre-commit hook both fail if this drifts from source.

## The vault (`.agent-vault/`)

Repo-scoped design rationale, decisions, research, and reference notes -
separate from AGENTS.md (operational instructions) and the structural index
(mechanically derived from code). Schema and note-type conventions:
`.agent-vault/SCHEMA.md`.

A note can declare `watches` entries (a file, optionally scoped to one
named top-level symbol) if it documents something that can drift out of
sync with the code - most notes (decisions, research, brainstorming) don't
need this at all. The pre-commit hook (`girdle notes check .`) blocks a
commit that changes a watched file/symbol without also updating the note
that watches it in the *same* commit; if the note's already part of the
commit, it auto-reconciles the recorded hash instead of blocking. To
confirm a note is still accurate without editing its prose, run
`girdle notes ack path/to/note.md` before committing.

Regenerate the vault's own catalog after adding/editing a note:

```bash
girdle notes index .
```
