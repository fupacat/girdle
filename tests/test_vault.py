import subprocess
from pathlib import Path

from girdle.vault import (
    WatchEntry,
    ack,
    check,
    current_hash,
    load_all_notes,
    load_note,
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


def test_render_vault_index(tmp_path: Path):
    _write_example(tmp_path)
    _write_note(tmp_path, note_hash="abc123")
    notes = load_all_notes(tmp_path)
    text = render_vault_index(tmp_path, notes)
    assert "context" in text
    assert "src/example.py#greet" in text
    assert "stale=False" in text
