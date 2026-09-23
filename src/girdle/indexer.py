"""Deterministic structural index: a compressed path -> {language, symbols}
manifest, mechanically generated (regex-based symbol extraction, no LLM in
the loop), flat, budget-capped. Content is structural facts only (paths,
symbol names) - never free text scraped from comments/docstrings, per the
design note's injection-safety stance (an untrusted file's docstring must
never become "trusted" instruction context just because it's near a symbol
name girdle extracted).

Ranking for budget truncation uses symbol count as a lightweight proxy for
"structurally significant" - this is NOT a real reference-graph/PageRank
signal like Aider's repo map. Flagged as a known limitation rather than
oversold.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BUDGET_TOKENS = 4000
CHARS_PER_TOKEN_ESTIMATE = 4  # crude approximation, not a real tokenizer

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "bin", "obj", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "vendor", ".idea", ".vscode", ".egg-info",
}

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
}

# Top-level-only patterns (no indentation before the keyword) to keep the
# index flat/compressed rather than enumerating every nested method.
SYMBOL_PATTERNS = {
    "python": [
        re.compile(r"^(?:async def|def|class)\s+(\w+)", re.MULTILINE),
    ],
    "javascript": [
        re.compile(r"^(?:export\s+)?(?:default\s+)?function\s*\*?\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^export\s+const\s+(\w+)\s*=", re.MULTILINE),
    ],
    "typescript": [
        re.compile(r"^(?:export\s+)?(?:default\s+)?function\s*\*?\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+(\w+)", re.MULTILINE),
        re.compile(r"^export\s+const\s+(\w+)\s*=", re.MULTILINE),
        re.compile(r"^(?:export\s+)?interface\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:export\s+)?type\s+(\w+)\s*=", re.MULTILINE),
    ],
    "go": [
        re.compile(r"^func\s+(?:\(\w+ \*?\w+\)\s+)?(\w+)", re.MULTILINE),
        re.compile(r"^type\s+(\w+)\s+(?:struct|interface)", re.MULTILINE),
    ],
    "rust": [
        re.compile(r"^(?:pub\s+)?fn\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:pub\s+)?struct\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:pub\s+)?enum\s+(\w+)", re.MULTILINE),
        re.compile(r"^(?:pub\s+)?trait\s+(\w+)", re.MULTILINE),
        re.compile(r"^impl(?:<[^>]*>)?\s+(?:\w+\s+for\s+)?(\w+)", re.MULTILINE),
    ],
    "java": [
        re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?"
                   r"(?:class|interface|enum|record)\s+(\w+)", re.MULTILINE),
    ],
    "csharp": [
        re.compile(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?"
                   r"(?:sealed\s+)?(?:class|interface|enum|record|struct)\s+(\w+)", re.MULTILINE),
    ],
}


@dataclass
class IndexEntry:
    path: str
    language: str
    lines: int
    symbols: list[str] = field(default_factory=list)


@dataclass
class RepoIndex:
    repo_root: str
    generated_at: str
    budget_tokens: int
    entries: list[IndexEntry] = field(default_factory=list)
    total_files_scanned: int = 0
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "repo_root": self.repo_root,
            "generated_at": self.generated_at,
            "budget_tokens": self.budget_tokens,
            "total_files_scanned": self.total_files_scanned,
            "truncated": self.truncated,
            "entries": [
                {"path": e.path, "language": e.language, "lines": e.lines, "symbols": e.symbols}
                for e in self.entries
            ],
        }


def _iter_source_files(root: Path):
    for dirpath, dirnames, filenames in _walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = Path(name).suffix
            if ext in LANGUAGE_BY_EXT:
                yield Path(dirpath) / name


def _walk(root: Path):
    yield from os.walk(root)


def _extract_symbols(text: str, language: str) -> list[str]:
    symbols: list[str] = []
    for pattern in SYMBOL_PATTERNS.get(language, []):
        symbols.extend(pattern.findall(text))
    # de-dupe while preserving first-seen order
    seen = set()
    ordered = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered


def build_index(repo_root: Path, budget_tokens: int = DEFAULT_BUDGET_TOKENS) -> RepoIndex:
    repo_root = repo_root.resolve()
    all_entries: list[IndexEntry] = []

    for file_path in _iter_source_files(repo_root):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        language = LANGUAGE_BY_EXT[file_path.suffix]
        symbols = _extract_symbols(text, language)
        all_entries.append(
            IndexEntry(
                path=str(file_path.relative_to(repo_root)).replace("\\", "/"),
                language=language,
                lines=text.count("\n") + 1,
                symbols=symbols,
            )
        )

    total_scanned = len(all_entries)

    # Rank by symbol count (proxy signal - see module docstring) as a
    # tiebreak-stable sort, then greedily fill the token budget.
    ranked = sorted(all_entries, key=lambda e: (-len(e.symbols), e.path))

    selected: list[IndexEntry] = []
    used_tokens = 0
    truncated = False
    for entry in ranked:
        entry_tokens = _estimate_tokens(_render_entry(entry))
        if used_tokens + entry_tokens > budget_tokens and selected:
            truncated = True
            break
        selected.append(entry)
        used_tokens += entry_tokens

    # Final display order is alphabetical by path - the ranking above only
    # decides *which* files survive the budget, not the manifest's order.
    selected.sort(key=lambda e: e.path)

    return RepoIndex(
        repo_root=str(repo_root),
        generated_at=(
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        ),
        budget_tokens=budget_tokens,
        entries=selected,
        total_files_scanned=total_scanned,
        truncated=truncated,
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _render_entry(entry: IndexEntry) -> str:
    symbols = ", ".join(entry.symbols)
    return f"{entry.path} | {entry.language} | {entry.lines}L | {symbols}"


def render_manifest(index: RepoIndex) -> str:
    lines = [_render_entry(e) for e in index.entries]
    if index.truncated:
        lines.append(
            f"# ... truncated to fit {index.budget_tokens}-token budget "
            f"({len(index.entries)}/{index.total_files_scanned} files shown)"
        )
    return "\n".join(lines)


MARKER_START = "<!-- girdle:index:start -->"
MARKER_END = "<!-- girdle:index:end -->"
_BLOCK_PATTERN = re.compile(
    re.escape(MARKER_START) + r"\n```\n(.*?)\n```\n" + re.escape(MARKER_END), re.DOTALL
)


def render_block(manifest_text: str) -> str:
    return f"{MARKER_START}\n```\n{manifest_text}\n```\n{MARKER_END}"


def inject_into(file_path: Path, manifest_text: str) -> str:
    """Returns the new full file content with the manifest inserted/replaced
    between markers - a mechanical, idempotent trigger (matches Claude Code's
    own file-access-bound loading model), never an agent-discretionary
    "should I regenerate this" decision. Creates the markers if absent.
    """
    block = render_block(manifest_text)
    content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    if MARKER_START in content and MARKER_END in content:
        return _BLOCK_PATTERN.sub(lambda _match: block, content)
    if not content or content.endswith("\n\n"):
        sep = ""
    elif content.endswith("\n"):
        sep = "\n"
    else:
        sep = "\n\n"
    return content + sep + block + "\n"


def is_stale(file_path: Path, manifest_text: str) -> bool:
    """True if file_path is missing the marker block, or its content has
    drifted from a freshly generated manifest. For a --check step in CI/
    hooks per the design note's observability/drift-detection requirement.
    """
    if not file_path.exists():
        return True
    content = file_path.read_text(encoding="utf-8")
    match = _BLOCK_PATTERN.search(content)
    if not match:
        return True
    return match.group(1) != manifest_text
