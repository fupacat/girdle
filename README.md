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

girdle index .                        # deterministic structural manifest (path/language/symbols)
girdle index . --inject AGENTS.md     # insert/update the manifest between markers in a file
girdle index . --check AGENTS.md      # exit nonzero if that file's manifest block is stale (for CI/hooks)
```

`girdle index` is a separate, mechanically-generated structural index — not
part of the verification score. It's a flat, budget-capped (`--budget-tokens`,
default 4000) path -> {language, line count, top-level symbols} manifest,
parsed with [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars
(Python, JS/TS/TSX, Go, Rust, Java, C#) rather than regex, so multi-line
signatures, decorators, and language-specific wrapping (TS interfaces/type
aliases, C# block namespaces) resolve correctly. Truncation ranking still
uses symbol count as a lightweight significance proxy (not a real reference-
graph/PageRank signal). Content is structural facts only (paths, symbol
names) — never free text scraped from comments or docstrings, since those
could originate from an untrusted fork. `--inject` and `--check` are the
mechanical regenerate/verify hooks for wiring this into a pre-commit hook or
CI step, as this repo's own `.github/workflows/ci.yml` does against its own
`AGENTS.md`.

## Development

`requirements.txt` / `requirements-dev.txt` are pinned via `pip-compile`
(from `pip-tools`) against `pyproject.toml`. Regenerate after changing
dependencies:

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
pip-compile --extra dev pyproject.toml -o requirements-dev.txt
```

### Enforcement hooks

`.pre-commit-config.yaml` wires ruff, pytest, and `girdle index --check
AGENTS.md` as zero-exception pre-commit gates, per the design note's
enforcement-hooks stance (hooks are deterministic; AGENTS.md/CLAUDE.md are
advisory). Activate once per clone:

```bash
pip install -e ".[dev]"
pre-commit install
```

These are `language: system` hooks — they run whatever `ruff`/`pytest`/
`girdle` resolve to on `PATH` at commit time, so make sure this repo's own
venv is active first (same precondition as `--run`, above). `--no-verify`
still bypasses them, per the design note's documented failure mode of
agents dropping to `--no-verify`/`git stash` under pressure — a hook
reduces but doesn't eliminate the need for a separate review step.

Exit code is nonzero if the weakest applicable category falls below
`--fail-under` (default: tier 1, "configured").

`--run` executes the scanned repo's own test/lint tooling to upgrade a
category from "configured" to "verified" (tier 2) — e.g. `pytest`,
`ruff check .`, `cargo test`, `dotnet test`. It runs arbitrary code from the
target repo, so it is opt-in only, never the default (see the security
section of the design note for why). It also assumes whatever
interpreter/toolchain is already active or on `PATH` is the right one for
the scanned repo — girdle does not install dependencies or activate
environments first, so run it from within the repo's own venv/toolchain
context for accurate results.

## Design

See the project's `AGENTS.md` and the `Agent-Ready Repository Design` vault
note for the scoring model and detection matrix this implements.
