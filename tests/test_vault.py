import subprocess
from pathlib import Path

import pytest

from girdle.vault import (
    DanglingWatchError,
    WatchEntry,
    ack,
    check,
    current_hash,
    inject_vault_index,
    load_all_notes,
    load_note,
    reconcile,
    render_vault_index,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


_DEFAULT_GREET = 'def greet(name):\n    return f"hello {name}"\n'


def _write_example(root: Path, body: str = _DEFAULT_GREET) -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "example.py").write_text(body, encoding="utf-8")


def _write_note(root: Path, note_hash: str | None = None) -> Path:
    (root / ".agent-vault" / "context").mkdir(parents=True, exist_ok=True)
    note_path = root / ".agent-vault" / "context" / "greet-note.md"
    hash_line = f"hash: {note_hash}" if note_hash else "hash: null"
    note_path.write_text(
        "---\n"
        "type: context\n"
        "watches:\n"
        "  - path: src/example.py\n"
        "    symbol: greet\n"
        f"    {hash_line}\n"
        "stale: false\n"
        "---\n\n"
        "# greet() design note\n",
        encoding="utf-8",
    )
    return note_path


def test_load_note_parses_frontmatter(tmp_path: Path):
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    note = load_note(note_path)
    assert note.type == "context"
    assert note.stale is False
    assert len(note.watches) == 1
    assert note.watches[0].path == "src/example.py"
    assert note.watches[0].symbol == "greet"


def test_current_hash_symbol_level(tmp_path: Path):
    _write_example(tmp_path)
    watch = WatchEntry(path="src/example.py", symbol="greet")
    h1 = current_hash(tmp_path, watch)
    assert h1 is not None

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    h2 = current_hash(tmp_path, watch)
    assert h2 != h1


def test_current_hash_missing_symbol_is_none(tmp_path: Path):
    _write_example(tmp_path)
    watch = WatchEntry(path="src/example.py", symbol="nonexistent")
    assert current_hash(tmp_path, watch) is None


def test_current_hash_file_level_no_symbol(tmp_path: Path):
    _write_example(tmp_path)
    watch = WatchEntry(path="src/example.py")
    h1 = current_hash(tmp_path, watch)
    _write_example(tmp_path, 'def greet(name):\n    return "changed"\n')
    h2 = current_hash(tmp_path, watch)
    assert h1 != h2


def test_load_all_notes_skips_reserved_names(tmp_path: Path):
    _write_example(tmp_path)
    _write_note(tmp_path)
    (tmp_path / ".agent-vault" / "SCHEMA.md").write_text("schema", encoding="utf-8")
    (tmp_path / ".agent-vault" / "index.md").write_text("index", encoding="utf-8")
    notes = load_all_notes(tmp_path)
    assert len(notes) == 1


def test_ack_records_current_hash_and_stages(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    rel = ack(tmp_path, note_path)
    assert rel == ".agent-vault/context/greet-note.md"
    note = load_note(note_path)
    assert note.watches[0].hash is not None
    assert note.stale is False

    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=tmp_path,
        capture_output=True, text=True, check=True,
    ).stdout
    assert "greet-note.md" in staged


def test_check_blocks_when_note_not_updated(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    _git(tmp_path, "add", "src/example.py")

    result = check(tmp_path)
    assert result.reconciled == []
    assert len(result.blocking) == 1
    assert "greet-note.md" in result.blocking[0]
    assert "src/example.py#greet" in result.blocking[0]

    note = load_note(note_path)
    assert note.stale is True


def test_check_auto_reconciles_when_note_staged_too(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    with note_path.open("a", encoding="utf-8") as f:
        f.write("\nUpdated: now shouts.\n")
    _git(tmp_path, "add", "-A")

    result = check(tmp_path)
    assert result.blocking == []
    assert len(result.reconciled) == 1

    note = load_note(note_path)
    assert note.stale is False
    old_hash = current_hash(tmp_path, WatchEntry(path="src/example.py", symbol="greet"))
    assert note.watches[0].hash == old_hash


def test_check_skips_notes_without_watches(tmp_path: Path):
    (tmp_path / ".agent-vault" / "decisions").mkdir(parents=True)
    (tmp_path / ".agent-vault" / "decisions" / "some-decision.md").write_text(
        "---\ntype: decision\n---\n\n# A decision\n", encoding="utf-8"
    )
    _init_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    result = check(tmp_path)
    assert result.blocking == []
    assert result.reconciled == []


def test_check_does_not_reconcile_when_only_stale_marker_was_staged(tmp_path: Path):
    # Reproduces the bug: check() writes stale:true on block, unstaged. A
    # later blanket `git add -A` (no real edit) must NOT count as the
    # deliberate review that authorizes auto-reconcile.
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    _git(tmp_path, "add", "src/example.py")
    first = check(tmp_path)
    assert first.blocking and first.reconciled == []

    # Sweep up the hook's own unstaged stale:true write - no real edit.
    _git(tmp_path, "add", "-A")
    second = check(tmp_path)
    assert second.reconciled == []
    assert len(second.blocking) == 1


def test_reconcile_raises_on_dangling_watch(tmp_path: Path):
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    note = load_note(note_path)
    (tmp_path / "src" / "example.py").unlink()

    with pytest.raises(DanglingWatchError):
        reconcile(tmp_path, note)


def test_ack_raises_on_dangling_watch(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "src" / "example.py").unlink()

    with pytest.raises(DanglingWatchError):
        ack(tmp_path, note_path)


def test_check_blocks_dangling_watch_even_when_note_staged(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    (tmp_path / "src" / "example.py").unlink()
    with note_path.open("a", encoding="utf-8") as f:
        f.write("\nUpdated: symbol removed upstream.\n")
    _git(tmp_path, "add", "-A")

    result = check(tmp_path)
    assert result.reconciled == []
    assert len(result.blocking) == 1
    assert "dangling watch" in result.blocking[0]


def test_check_blocks_point_in_time_type_with_watches(tmp_path: Path):
    _write_example(tmp_path)
    (tmp_path / ".agent-vault" / "decisions").mkdir(parents=True)
    note_path = tmp_path / ".agent-vault" / "decisions" / "bad-decision.md"
    note_path.write_text(
        "---\n"
        "type: decision\n"
        "watches:\n"
        "  - path: src/example.py\n"
        "    symbol: greet\n"
        "    hash: null\n"
        "stale: false\n"
        "---\n\n"
        "# A decision that shouldn't watch anything\n",
        encoding="utf-8",
    )
    _init_repo(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    result = check(tmp_path)
    assert result.reconciled == []
    assert len(result.blocking) == 1
    assert "point-in-time" in result.blocking[0]


def test_ack_resolves_relative_root_and_note_path(tmp_path: Path, monkeypatch):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    monkeypatch.chdir(tmp_path)
    rel = ack(Path("."), Path(".agent-vault/context/greet-note.md"))
    assert rel == ".agent-vault/context/greet-note.md"
    assert load_note(note_path).watches[0].hash is not None


def test_render_vault_index(tmp_path: Path):
    _write_example(tmp_path)
    _write_note(tmp_path, note_hash="abc123")
    notes = load_all_notes(tmp_path)
    text = render_vault_index(tmp_path, notes)
    assert "context" in text
    assert "src/example.py#greet" in text
    assert "stale=False" in text


def test_load_note_without_frontmatter(tmp_path: Path):
    path = tmp_path / "plain.md"
    path.write_text("# Just a heading, no frontmatter\n", encoding="utf-8")
    note = load_note(path)
    assert note.type is None
    assert note.watches == []


def test_load_all_notes_no_vault_dir(tmp_path: Path):
    assert load_all_notes(tmp_path) == []


def test_current_hash_unsupported_extension_with_symbol(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("greet: hello\n", encoding="utf-8")
    watch = WatchEntry(path="notes.txt", symbol="greet")
    assert current_hash(tmp_path, watch) is None


def test_check_blocks_pure_rename_with_no_content_edit(tmp_path: Path):
    # A `git mv` with zero content change must not be mistaken for a
    # brand-new note (which would wrongly count as the deliberate review).
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    _git(tmp_path, "add", "src/example.py")

    new_dir = tmp_path / ".agent-vault" / "data-models"
    new_dir.mkdir(parents=True)
    new_path = new_dir / "greet-note.md"
    _git(tmp_path, "mv", str(note_path), str(new_path))

    result = check(tmp_path)
    assert result.reconciled == []
    assert len(result.blocking) == 1
    assert "greet-note.md" in result.blocking[0]


def test_check_auto_reconciles_rename_with_real_content_edit(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return f"HELLO {name}!!!"\n')
    _git(tmp_path, "add", "src/example.py")

    new_dir = tmp_path / ".agent-vault" / "data-models"
    new_dir.mkdir(parents=True)
    new_path = new_dir / "greet-note.md"
    _git(tmp_path, "mv", str(note_path), str(new_path))
    with new_path.open("a", encoding="utf-8") as f:
        f.write("\nReclassified and updated: now shouts.\n")
    _git(tmp_path, "add", "-A")

    result = check(tmp_path)
    assert result.blocking == []
    assert len(result.reconciled) == 1


def test_check_leaves_unchanged_notes_alone(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    ack(tmp_path, note_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    result = check(tmp_path)
    assert result.reconciled == []
    assert result.blocking == []


def test_check_auto_reconciles_brand_new_note_never_committed(tmp_path: Path):
    # No prior HEAD version of the note exists at all - authoring it in
    # this very commit is itself the deliberate review.
    _init_repo(tmp_path)
    _write_example(tmp_path)
    (tmp_path / "README.md").write_text("placeholder\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init, no note yet")

    _write_note(tmp_path)
    _git(tmp_path, "add", "-A")

    result = check(tmp_path)
    assert result.blocking == []
    assert len(result.reconciled) == 1


def test_inject_vault_index_separator_variants(tmp_path: Path):
    single_newline = tmp_path / "single.md"
    single_newline.write_text("# Existing\n", encoding="utf-8")
    result = inject_vault_index(single_newline, "note.md | context | stale=False | watches: -")
    assert result.startswith("# Existing\n\n<!-- girdle:vault-index:start -->")

    no_trailing_newline = tmp_path / "notrail.md"
    no_trailing_newline.write_text("# Existing", encoding="utf-8")
    result = inject_vault_index(
        no_trailing_newline, "note.md | context | stale=False | watches: -"
    )
    assert result.startswith("# Existing\n\n<!-- girdle:vault-index:start -->")


def test_inject_vault_index_creates_and_replaces_block(tmp_path: Path):
    target = tmp_path / "index.md"
    first = inject_vault_index(target, "note-a.md | context | stale=False | watches: -")
    assert "girdle:vault-index:start" in first
    assert "note-a.md" in first

    target.write_text(first, encoding="utf-8")
    second = inject_vault_index(target, "note-b.md | decision | stale=False | watches: -")
    assert "note-a.md" not in second
    assert "note-b.md" in second
