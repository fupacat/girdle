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
pytest
girdle index . --check AGENTS.md
girdle notes check .
```

All four also run automatically on commit via `.pre-commit-config.yaml`
(see the README's "Enforcement hooks" section); the first three also run
again in CI on push/PR (the notes check is commit-local only - see below).

## Branch protection

`master` is protected, including for admins: changes land via a PR with a
passing `test` status check (which itself fails if `ruff`, `pytest`, the
index-freshness check, or the SonarCloud Quality Gate fails). There's no
required-approving-review rule — GitHub always blocks self-approval, which
makes that rule unsatisfiable on a repo with one author. Direct `git push`
to `master` will be rejected, even from the repo owner — open a branch and
PR instead.

## Adding a new ecosystem detector

New ecosystem support = a new file in `src/girdle/detectors/` implementing
the `Detector` protocol (`detectors/base.py`), registered in
`detectors/registry.py`. See `AGENTS.md` and the `Agent-Ready Repository
Design` vault note for the design rationale and the full detection matrix
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
