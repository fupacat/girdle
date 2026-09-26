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

girdle scan . --platform               # also check live GitHub branch protection via `gh`

girdle align .                          # dry-run: show what would be added to .editorconfig/.gitattributes/.gitignore
girdle align . --write                  # apply it
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

### Alignment (`girdle align`)

Unlike every other command, `align` writes to the scanned repo — it's the
one place girdle moves from read-only scanner to file writer, which is why
it's dry-run by default and requires `--write` to apply anything. It only
derives settings from formatter config *already present* in the repo
(Black/ruff-format/Prettier/rustfmt), never invents an opinion from
scratch, and is deliberately conservative: it only appends new
`.editorconfig` sections/`.gitattributes` lines/`.gitignore` patterns that
are provably absent, never edits an existing section or line. If detected
formatters disagree on line endings, that's reported as a conflict and
left alone rather than guessed. Go is excluded from `.editorconfig`
derivation since gofmt has no config file to detect a preference from.

## Development

`requirements.txt` / `requirements-dev.txt` are pinned via `pip-compile`
(from `pip-tools`) against `pyproject.toml`. Regenerate after changing
dependencies:

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
pip-compile --extra dev pyproject.toml -o requirements-dev.txt
```

### Platform-level enforcement (`--platform`)

`--platform` checks live GitHub branch protection (required reviews, required
status checks, `enforce_admins`, force-push/signature policy) via the `gh`
CLI, reusing whatever `gh auth login` session is already active. This is a
different trust category from every other check girdle does: everything
else is a local file read with zero auth and zero network; this one is a
live authenticated API call. It's opt-in only, never part of the default
scan, and girdle never implements its own OAuth flow or asks a user to
newly authorize it — if `gh` isn't installed or isn't authenticated, the
check reports `available: false` with a reason and the rest of the scan
proceeds normally.

Branch protection lives on GitHub's side, not in the repo's files, so this
genuinely can't be answered by static analysis. A repo declaring its
*intended* protection as versioned policy-as-code (e.g. a committed
`.github/settings.yml` for the Probot Settings app, or a Terraform
GitHub-provider config) would be a separate, complementary, zero-auth
signal — not yet implemented, but it stays inside girdle's normal trust
model in a way a live API check never can, and is the right answer for
scanning someone else's repo without asking them to authorize anything.

### Enforcement hooks

`.pre-commit-config.yaml` wires ruff, pytest, and `girdle index --check AGENTS.md` as zero-exception pre-commit gates, per the design note's
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
