"""Best-effort extraction of a coverage percentage from a coverage tool's
own stdout, for languages where that's a stable, well-documented format.

Deliberately scoped to what's reliably parseable without touching a report
file on disk:
- Python (coverage.py, via pytest-cov): the `TOTAL ... XX%` summary line.
- Go (`go test -cover`): the `coverage: XX.X% of statements` line.
- Rust (cargo-tarpaulin): the `XX.XX% coverage` summary line.
- JS/TS (istanbul-based reporters - nyc, jest's default): the `All files`
  row of the default text-summary table, if that reporter is what ran.

Explicitly NOT attempted: Java (JaCoCo) and .NET (coverlet) don't print a
percentage to stdout by default - they write an XML/HTML report file, which
would need locating and parsing a report format, not stdout. Left as a
known gap rather than guessed at.
"""

from __future__ import annotations

import re

_PYTHON_TOTAL = re.compile(r"^TOTAL\s+(?:\d+\s+){1,3}(\d+)%", re.MULTILINE)
_GO_COVERAGE = re.compile(r"coverage:\s+([\d.]+)%\s+of statements")
_RUST_TARPAULIN = re.compile(r"([\d.]+)%\s+coverage")
_JS_ALL_FILES = re.compile(r"All files\s*\|\s*([\d.]+)")

PARSERS = {
    "python": lambda out: _first_match(_PYTHON_TOTAL, out),
    "go": lambda out: _first_match(_GO_COVERAGE, out),
    "rust": lambda out: _first_match(_RUST_TARPAULIN, out),
    "javascript": lambda out: _first_match(_JS_ALL_FILES, out),
    "typescript": lambda out: _first_match(_JS_ALL_FILES, out),
}


def _first_match(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return f"{match.group(1)}%" if match else None


def parse_percentage(language: str, stdout: str) -> str | None:
    parser = PARSERS.get(language)
    if parser is None:
        return None
    return parser(stdout)
