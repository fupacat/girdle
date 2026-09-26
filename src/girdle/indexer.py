"""Deterministic structural index: a compressed path -> {language, symbols}
manifest, mechanically generated via tree-sitter grammar parsing (no LLM in
the loop), flat, budget-capped. Content is structural facts only (paths,
symbol names) - never free text scraped from comments/docstrings, per the
design note's injection-safety stance (an untrusted file's docstring must
never become "trusted" instruction context just because it's near a symbol
name girdle extracted).

Only top-level definitions are extracted (one level of unwrapping through
decorators/export statements/block namespaces) to keep the index flat and
compressed, not a full symbol table - this is a deliberate scope choice,
independent of using a real parser instead of regex.

Ranking for budget truncation uses symbol count as a lightweight proxy for
"structurally significant" - this is NOT a real reference-graph/PageRank
signal like Aider's repo map. Flagged as a known limitation rather than
oversold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cache
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from girdle.fsutil import walk_excluding

DEFAULT_BUDGET_TOKENS = 4000
CHARS_PER_TOKEN_ESTIMATE = 4  # crude approximation, not a real tokenizer

# extension -> (display language, tree-sitter grammar name)
LANGUAGE_BY_EXT = {
    ".py": ("python", "python"),
    ".js": ("javascript", "javascript"),
    ".jsx": ("javascript", "javascript"),
    ".mjs": ("javascript", "javascript"),
    ".cjs": ("javascript", "javascript"),
    ".ts": ("typescript", "typescript"),
    ".tsx": ("typescript", "tsx"),
    ".go": ("go", "go"),
    ".rs": ("rust", "rust"),
    ".java": ("java", "java"),
    ".cs": ("csharp", "csharp"),
}


@cache
def _parser(grammar: str):
    return get_parser(grammar)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _name_of(node: Node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    return _text(name_node, source) if name_node else None


def _defs_python(root: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in root.children:
        node = child
        if node.type == "decorated_definition":
            inner = node.child_by_field_name("definition")
            if inner:
                node = inner
        if node.type in ("function_definition", "class_definition"):
            name = _name_of(node, source)
            if name:
                pairs.append((name, node))
    return pairs


_JS_DEF_TYPES = (
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "interface_declaration",
    "type_alias_declaration",
)


_JS_FUNCTION_VALUE_TYPES = ("arrow_function", "function", "function_expression")


def _defs_lexical_declaration(node: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for declarator in node.children:
        if declarator.type != "variable_declarator":
            continue
        value = declarator.child_by_field_name("value")
        if value is not None and value.type in _JS_FUNCTION_VALUE_TYPES:
            name = _name_of(declarator, source)
            if name:
                pairs.append((name, declarator))
    return pairs


def _unwrap_export(node: Node) -> Node | None:
    if node.type != "export_statement":
        return node
    return node.child_by_field_name("declaration")


def _defs_js_ts(root: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in root.children:
        node = _unwrap_export(child)
        if node is None:
            continue
        if node.type in _JS_DEF_TYPES:
            name = _name_of(node, source)
            if name:
                pairs.append((name, node))
        elif node.type == "lexical_declaration":
            pairs.extend(_defs_lexical_declaration(node, source))
    return pairs


def _defs_go_type_declaration(node: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for spec in node.children:
        if spec.type == "type_spec":
            name = _name_of(spec, source)
            if name:
                pairs.append((name, spec))
    return pairs


def _defs_go(root: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in root.children:
        if child.type in ("function_declaration", "method_declaration"):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                pairs.append((_text(name_node, source), child))
        elif child.type == "type_declaration":
            pairs.extend(_defs_go_type_declaration(child, source))
    return pairs


def _defs_rust(root: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in root.children:
        if child.type in ("function_item", "struct_item", "enum_item", "trait_item"):
            name = _name_of(child, source)
            if name:
                pairs.append((name, child))
        elif child.type == "impl_item":
            type_node = child.child_by_field_name("type")
            if type_node is not None:
                pairs.append((_text(type_node, source), child))
    return pairs


_JAVA_DEF_TYPES = (
    "class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
)


def _defs_java(root: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in root.children:
        if child.type in _JAVA_DEF_TYPES:
            name = _name_of(child, source)
            if name:
                pairs.append((name, child))
    return pairs


_CSHARP_DEF_TYPES = (
    "class_declaration", "interface_declaration", "struct_declaration",
    "enum_declaration", "record_declaration",
)


def _defs_csharp_from(node: Node, source: bytes) -> list[tuple[str, Node]]:
    pairs = []
    for child in node.children:
        if child.type in _CSHARP_DEF_TYPES:
            name = _name_of(child, source)
            if name:
                pairs.append((name, child))
        elif child.type == "namespace_declaration":
            body = child.child_by_field_name("body")
            if body is not None:
                pairs.extend(_defs_csharp_from(body, source))
    return pairs


_DEF_EXTRACTORS = {
    "python": _defs_python,
    "javascript": _defs_js_ts,
    "typescript": _defs_js_ts,
    "go": _defs_go,
    "rust": _defs_rust,
    "java": _defs_java,
    "csharp": _defs_csharp_from,
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
    for dirpath, _dirnames, filenames in walk_excluding(root):
        for name in filenames:
            ext = Path(name).suffix
            if ext in LANGUAGE_BY_EXT:
                yield Path(dirpath) / name


def _extract_symbol_pairs(
    source: bytes, display_language: str, grammar: str
) -> list[tuple[str, Node]]:
    extractor = _DEF_EXTRACTORS.get(display_language)
    if extractor is None:
        return []
    tree = _parser(grammar).parse(source)
    return extractor(tree.root_node, source)


def _extract_symbols(source: bytes, display_language: str, grammar: str) -> list[str]:
    return [name for name, _ in _extract_symbol_pairs(source, display_language, grammar)]


def find_symbol_source(
    source: bytes, display_language: str, grammar: str, name: str
) -> str | None:
    """Raw source text of a top-level symbol by name (first match), for the
    vault's per-symbol staleness hashing - reuses the same extraction used
    to build the structural index, just keeping the node instead of
    discarding it. Returns None if the language isn't supported or no
    top-level definition with that name exists.
    """
    for symbol_name, node in _extract_symbol_pairs(source, display_language, grammar):
        if symbol_name == name:
            return _text(node, source)
    return None


def build_index(repo_root: Path, budget_tokens: int = DEFAULT_BUDGET_TOKENS) -> RepoIndex:
    repo_root = repo_root.resolve()
    all_entries: list[IndexEntry] = []

    for file_path in _iter_source_files(repo_root):
        try:
            source = file_path.read_bytes()
        except OSError:
            continue
        display_language, grammar = LANGUAGE_BY_EXT[file_path.suffix]
        symbols = _extract_symbols(source, display_language, grammar)
        all_entries.append(
            IndexEntry(
                path=str(file_path.relative_to(repo_root)).replace("\\", "/"),
                language=display_language,
                lines=source.count(b"\n") + 1,
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
