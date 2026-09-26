"""The repo-scoped knowledge vault (`.agent-vault/`): notes for decisions,
design context, research, brainstorming, data models, diagrams, CI, and
environment/deployment concerns - separate from AGENTS.md (which is
operational instructions) and the structural index (which is mechanically
derived from code, never hand-written).

Only some notes describe something that can drift out of sync with the
code: a `context`/`design`/`data-model`/`ci` note may declare `watches`
entries (a file, optionally scoped to one named top-level symbol via the
same tree-sitter extraction the structural index uses). Point-in-time notes
(`decision`, `research`, `brainstorm`) never do - they're a historical
record, not living documentation, so nothing here enforces freshness on
them.

Staleness is a hash comparison, not a git diff: each watch entry records
the hash of what it watched as of the last time a human/agent reviewed it.
`check()` (the pre-commit entry point) recomputes the current hash and
compares - if it's now part of the same commit as the note itself, it's
auto-reconciled (recompute, rewrite, re-stage); if the note wasn't touched
at all, the commit blocks and the note is marked `stale: true` so a later
session discovers the gap even if the block is never manually cleared.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from girdle.indexer import LANGUAGE_BY_EXT, find_symbol_source

VAULT_DIR = ".agent-vault"
RESERVED_NOTE_NAMES = ("SCHEMA.md", "index.md")

NOTE_TYPES = (
    "decision", "context", "research", "brainstorm",
    "data-model", "diagram", "ci", "environment", "deployment",
)

_FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


@dataclass
class WatchEntry:
    path: str
    symbol: str | None = None
    hash: str | None = None


@dataclass
class Note:
    file_path: Path
    type: str | None = None
    stale: bool = False
    reviewed_at: str | None = None
    watches: list[WatchEntry] = field(default_factory=list)
    raw_frontmatter: dict = field(default_factory=dict)
    body: str = ""


class _IndentedDumper(yaml.SafeDumper):
    """PyYAML's default dumper writes `key:\\n- item`, not `key:\\n  - item`
    - mdformat-frontmatter (and most other YAML tooling) indents block
    sequences under their parent key. Matching that here means girdle's own
    writes (ack/check reconcile) don't fight a markdown/YAML formatter's
    output on every subsequent run.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text
    data = yaml.safe_load(match.group(1)) or {}
    return data, text[match.end():]


def _render_frontmatter(data: dict, body: str) -> str:
    yaml_text = yaml.dump(data, Dumper=_IndentedDumper, sort_keys=False).rstrip("\n")
    return f"---\n{yaml_text}\n---\n{body}"


def load_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    data, body = _parse_frontmatter(text)
    watches = [
        WatchEntry(path=w["path"], symbol=w.get("symbol"), hash=w.get("hash"))
        for w in (data.get("watches") or [])
    ]
    return Note(
        file_path=path,
        type=data.get("type"),
        stale=bool(data.get("stale", False)),
        reviewed_at=data.get("reviewed_at"),
        watches=watches,
        raw_frontmatter=data,
        body=body,
    )


def load_all_notes(root: Path) -> list[Note]:
    vault = root / VAULT_DIR
    if not vault.is_dir():
        return []
    return [
        load_note(path)
        for path in sorted(vault.rglob("*.md"))
        if path.name not in RESERVED_NOTE_NAMES
    ]


def current_hash(root: Path, watch: WatchEntry) -> str | None:
    """The hash a watch entry *should* have right now, from the working
    tree - None if the watched file/symbol no longer exists (a dangling
    reference, itself worth surfacing as a mismatch rather than ignoring).
    """
    target = root / watch.path
    if not target.exists():
        return None
    source = target.read_bytes()
    if watch.symbol is None:
        return hashlib.sha256(source).hexdigest()
    ext = target.suffix
    if ext not in LANGUAGE_BY_EXT:
        return None
    display_language, grammar = LANGUAGE_BY_EXT[ext]
    text = find_symbol_source(source, display_language, grammar, watch.symbol)
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _note_rel(root: Path, note: Note) -> str:
    return str(note.file_path.relative_to(root)).replace("\\", "/")


def _write_note(note: Note) -> None:
    data = dict(note.raw_frontmatter)
    data["watches"] = [
        {"path": w.path, **({"symbol": w.symbol} if w.symbol else {}), "hash": w.hash}
        for w in note.watches
    ]
    data["stale"] = note.stale
    note.file_path.write_text(_render_frontmatter(data, note.body), encoding="utf-8")


def _git_add(root: Path, rel_path: str) -> None:
    subprocess.run(["git", "add", rel_path], cwd=root, check=False)


def _staged_files(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    return set(result.stdout.splitlines())


def reconcile(root: Path, note: Note) -> None:
    """Recompute and record the current hash for every watch entry and
    clear `stale` - the shared step behind both auto-reconcile (note edited
    in the same commit) and an explicit `ack` (note confirmed unchanged).
    """
    for watch in note.watches:
        watch.hash = current_hash(root, watch)
    note.stale = False
    _write_note(note)


@dataclass
class CheckResult:
    reconciled: list[str] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)


def check(root: Path) -> CheckResult:
    """Pre-commit entry point. A note whose watched hash no longer matches
    is either auto-reconciled (it's part of this same commit - someone
    already touched it) or reported as blocking (it wasn't, so the commit
    would otherwise ship a code change with a now-unverified note).
    """
    staged = _staged_files(root)
    result = CheckResult()
    for note in load_all_notes(root):
        if not note.watches:
            continue
        mismatched = [w for w in note.watches if current_hash(root, w) != w.hash]
        if not mismatched:
            continue
        rel = _note_rel(root, note)
        if rel in staged:
            reconcile(root, note)
            _git_add(root, rel)
            result.reconciled.append(rel)
        else:
            note.stale = True
            _write_note(note)
            targets = ", ".join(
                f"{w.path}#{w.symbol}" if w.symbol else w.path for w in mismatched
            )
            result.blocking.append(f"{rel}: watches changed ({targets})")
    return result


def ack(root: Path, note_path: Path) -> str:
    """Confirm a note is still accurate without editing its prose: records
    the current watched hash(es), clears `stale`, and stages the note."""
    note = load_note(note_path)
    reconcile(root, note)
    rel = _note_rel(root, note)
    _git_add(root, rel)
    return rel


VAULT_INDEX_MARKER_START = "<!-- girdle:vault-index:start -->"
VAULT_INDEX_MARKER_END = "<!-- girdle:vault-index:end -->"
# The optional blank line after the start marker matches what a markdown
# formatter (mdformat) naturally inserts before a fenced code block - see
# the identical note on indexer.py's own _BLOCK_PATTERN.
_VAULT_INDEX_BLOCK_PATTERN = re.compile(
    re.escape(VAULT_INDEX_MARKER_START) + r"\n?\n```\n(.*?)\n```\n\n?"
    + re.escape(VAULT_INDEX_MARKER_END),
    re.DOTALL,
)


def render_vault_index(root: Path, notes: list[Note]) -> str:
    lines = []
    for note in notes:
        rel = _note_rel(root, note)
        watches = "; ".join(
            f"{w.path}#{w.symbol}" if w.symbol else w.path for w in note.watches
        ) or "-"
        lines.append(f"{rel} | {note.type or '?'} | stale={note.stale} | watches: {watches}")
    return "\n".join(lines)


def inject_vault_index(file_path: Path, index_text: str) -> str:
    block = f"{VAULT_INDEX_MARKER_START}\n\n```\n{index_text}\n```\n\n{VAULT_INDEX_MARKER_END}"
    content = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    if VAULT_INDEX_MARKER_START in content and VAULT_INDEX_MARKER_END in content:
        return _VAULT_INDEX_BLOCK_PATTERN.sub(lambda _m: block, content)
    if not content or content.endswith("\n\n"):
        sep = ""
    elif content.endswith("\n"):
        sep = "\n"
    else:
        sep = "\n\n"
    return content + sep + block + "\n"
