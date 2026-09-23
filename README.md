# girdle

Scores a repository's agent-readiness verification infrastructure — tests,
lint/type-checking, reproducible builds, and CI gating — across common
language ecosystems (JS/TS, Python, Go, .NET, Rust, Java, and their major
toolchain variants).

Agent-first by default: `girdle scan` emits structured JSON (or a compact
human table on a TTY). `girdle dashboard` renders the same scan data as a
standalone HTML report.

## Usage

```bash
pip install -e .
girdle scan .              # static analysis, JSON if piped
girdle scan . --run        # also execute test/lint tooling for tier-2 verification
girdle dashboard .          # writes girdle-report.html
```

## Development

`requirements.txt` / `requirements-dev.txt` are pinned via `pip-compile`
(from `pip-tools`) against `pyproject.toml`. Regenerate after changing
dependencies:

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
pip-compile --extra dev pyproject.toml -o requirements-dev.txt
```

Exit code is nonzero if the weakest applicable category falls below
`--fail-under` (default: tier 1, "configured").

## Design

See the project's `AGENTS.md` and the `Agent-Ready Repository Design` vault
note for the scoring model and detection matrix this implements.
