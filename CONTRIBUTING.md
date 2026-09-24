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
```

All three also run automatically on commit via `.pre-commit-config.yaml`
(see the README's "Enforcement hooks" section) and again in CI on push/PR.

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
