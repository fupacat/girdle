"""The repo-scoped knowledge vault (`.agent-vault/`): notes for decisions,
context, research, brainstorming, data models, diagrams, CI, and
environment/deployment concerns - separate from AGENTS.md (which is
operational instructions) and the structural index (which is mechanically
derived from code, never hand-written).

Freshness enforcement is keyed on whether a note declares `watches`
entries, not on its `type` - a note may watch a file, optionally scoped to
one named top-level symbol via the same tree-sitter extraction the
structural index uses. Point-in-time types (`decision`, `research`,
`brainstorm`, see POINT_IN_TIME_TYPES) are historical record rather than
living documentation, so `watches` on one of those is a configuration
error `check()` reports rather than something to enforce.

Staleness is a hash comparison, not a git diff: each watch entry records
the hash of what it watched as of the last time a human/agent reviewed it.
A missing/unresolvable watch target (file deleted, symbol renamed) is a
dangling reference, not a "matches nothing so nothing to report" case -
`current_hash` returning None always counts as needing attention, and
`reconcile`/`ack` refuse to silently record a null hash for it.

`check()` (the pre-commit entry point) recomputes the current hash and
compares - if the note is part of the same commit AND its content beyond
mechanical hash/stale bookkeeping actually changed since HEAD, it's
auto-reconciled (recompute, rewrite, re-stage). A `stale: true` write the
hook itself made, later swept up by an unrelated `git add -A`, does not
count as that deliberate edit - otherwise a plain retry would silently
re-approve a note nobody reviewed. If neither condition holds, the commit
blocks and the note is marked `stale: true` so a later session discovers
the gap even if the block is never manually cleared.
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

# These are historical record, not living documentation - `watches` on one
# of these is a configuration error, not something check() should enforce.
POINT_IN_TIME_TYPES = ("decision", "research", "brainstorm")


class DanglingWatchError(Exception):
    """Raised by reconcile()/ack() when asked to record a hash for a watch
    entry whose target (file or symbol) can't currently be resolved -
    refusing rather than silently writing `hash: null`, which would look
    identical to "matches" on every future check() and never surface again.
    """

    def __init__(self, note_rel: str, dangling: list[WatchEntry]):
        targets = ", ".join(_describe_watch(w) for w in dangling)
        super().__init__(f"{note_rel}: dangling watch(es) - target not found ({targets})")
        self.note_rel = note_rel
        self.dangling = dangling


def _describe_watch(w: WatchEntry) -> str:
    return f"{w.path}#{w.symbol}" if w.symbol else w.path

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


def _content_signature(data: dict, body: str) -> tuple[dict, str]:
    """Everything about a note EXCEPT the mechanical hash/stale bookkeeping
    fields check()/reconcile() themselves write - so comparing two
    signatures answers "did a human/agent actually edit this note", not
    "did any byte of this file change".
    """
    scrubbed = {k: v for k, v in data.items() if k != "stale"}
    watches = scrubbed.get("watches")
    if watches:
        scrubbed["watches"] = [{k: v for k, v in w.items() if k != "hash"} for w in watches]
    return scrubbed, body


def _rename_source(root: Path, rel: str) -> str | None:
    """The staged rename's source path, if `rel` is the destination of a
    detected `git mv` in this commit - so a pure rename isn't mistaken for
    a brand-new note with no HEAD baseline to compare against.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-M"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R") and parts[2] == rel:
            return parts[1]
    return None


def _show_at_head(root: Path, rel: str) -> tuple[dict, str] | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    data, body = _parse_frontmatter(result.stdout)
    return _content_signature(data, body)


def _head_signature(root: Path, rel: str) -> tuple[dict, str] | None:
    """The note's content signature as of HEAD, or None if there's truly no
    prior baseline to compare against (a brand-new note, or no commits at
    all) - in which case authoring it in this commit already IS the
    deliberate review. A note that was only `git mv`'d resolves against its
    old path's HEAD content instead of being treated as brand-new, so a
    pure rename with no actual edit doesn't count as one.
    """
    sig = _show_at_head(root, rel)
    if sig is not None:
        return sig
    source_rel = _rename_source(root, rel)
    if source_rel is not None:
        return _show_at_head(root, source_rel)
    return None


def _meaningfully_edited(root: Path, note: Note, rel: str) -> bool:
    head_sig = _head_signature(root, rel)
    if head_sig is None:
        return True
    return _content_signature(note.raw_frontmatter, note.body) != head_sig


def reconcile(root: Path, note: Note) -> None:
    """Recompute and record the current hash for every watch entry and
    clear `stale` - the shared step behind both auto-reconcile (note edited
    in the same commit) and an explicit `ack` (note confirmed unchanged).
    Raises DanglingWatchError, without writing anything, if any watch
    target can't currently be resolved - there's no valid hash to record.
    """
    current = {id(w): current_hash(root, w) for w in note.watches}
    dangling = [w for w in note.watches if current[id(w)] is None]
    if dangling:
        raise DanglingWatchError(_note_rel(root, note), dangling)
    for watch in note.watches:
        watch.hash = current[id(watch)]
    note.stale = False
    _write_note(note)


@dataclass
class CheckResult:
    reconciled: list[str] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)


def check(root: Path) -> CheckResult:
    """Pre-commit entry point. A note whose watched hash no longer matches
    is either auto-reconciled (it's part of this same commit AND its
    content beyond hash/stale bookkeeping actually changed since HEAD) or
    reported as blocking. A dangling watch (target no longer resolvable)
    always blocks, regardless of staging - there's no valid hash to
    reconcile to. A point-in-time note (decision/research/brainstorm)
    declaring `watches` at all is a configuration error, reported
    unconditionally.
    """
    root = root.resolve()
    staged = _staged_files(root)
    result = CheckResult()
    for note in load_all_notes(root):
        rel = _note_rel(root, note)

        if note.type in POINT_IN_TIME_TYPES and note.watches:
            result.blocking.append(
                f"{rel}: type '{note.type}' is point-in-time and must not declare "
                "watches (only context/data-model/diagram/ci/environment/deployment can)"
            )
            continue

        if not note.watches:
            continue

        dangling = [w for w in note.watches if current_hash(root, w) is None]
        if dangling:
            note.stale = True
            _write_note(note)
            result.blocking.append(
                f"{rel}: dangling watch(es) - target not found "
                f"({', '.join(_describe_watch(w) for w in dangling)})"
            )
            continue

        mismatched = [w for w in note.watches if current_hash(root, w) != w.hash]
        if not mismatched:
            continue

        if rel in staged and _meaningfully_edited(root, note, rel):
            reconcile(root, note)
            _git_add(root, rel)
            result.reconciled.append(rel)
        else:
            note.stale = True
            _write_note(note)
            targets = ", ".join(_describe_watch(w) for w in mismatched)
            result.blocking.append(f"{rel}: watches changed ({targets})")
    return result


def ack(root: Path, note_path: Path) -> str:
    """Confirm a note is still accurate without editing its prose: records
    the current watched hash(es), clears `stale`, and stages the note.
    Raises DanglingWatchError if a watch target can't currently be
    resolved - fix or remove that watch entry first."""
    root = root.resolve()
    note_path = note_path.resolve()
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
        watches = "; ".join(_describe_watch(w) for w in note.watches) or "-"
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
