"""CLI-level coverage for `girdle notes {check,ack,index}` - vault.py's own
unit tests exercise the library functions directly, but the Click command
wiring (argument parsing, exit codes, DanglingWatchError -> clean message
rather than a traceback) is only exercised here.
"""

import subprocess
from pathlib import Path

from click.testing import CliRunner

from girdle.cli import main


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write_example(root: Path, body: str = 'def greet(name):\n    return "hi"\n') -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "example.py").write_text(body, encoding="utf-8")


def _write_note(root: Path) -> Path:
    (root / ".agent-vault" / "context").mkdir(parents=True, exist_ok=True)
    note_path = root / ".agent-vault" / "context" / "greet-note.md"
    note_path.write_text(
        "---\ntype: context\nwatches:\n  - path: src/example.py\n"
        "    symbol: greet\n    hash: null\nstale: false\n---\n\n# note\n",
        encoding="utf-8",
    )
    return note_path


def test_notes_check_passes_with_no_vault(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["notes", "check", str(tmp_path)])
    assert result.exit_code == 0


def test_notes_ack_then_check_passes(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    runner = CliRunner()
    ack_result = runner.invoke(main, ["notes", "ack", str(note_path), "--path", str(tmp_path)])
    assert ack_result.exit_code == 0
    assert "acknowledged:" in ack_result.output

    check_result = runner.invoke(main, ["notes", "check", str(tmp_path)])
    assert check_result.exit_code == 0


def test_notes_check_blocks_and_exits_nonzero(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")

    runner = CliRunner()
    runner.invoke(main, ["notes", "ack", str(note_path), "--path", str(tmp_path)])
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline hash")

    _write_example(tmp_path, 'def greet(name):\n    return "changed"\n')
    _git(tmp_path, "add", "src/example.py")

    result = runner.invoke(main, ["notes", "check", str(tmp_path)])
    assert result.exit_code == 1
    assert "stale:" in result.output


def test_notes_ack_reports_dangling_watch_cleanly(tmp_path: Path):
    _init_repo(tmp_path)
    _write_example(tmp_path)
    note_path = _write_note(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "src" / "example.py").unlink()

    runner = CliRunner()
    result = runner.invoke(main, ["notes", "ack", str(note_path), "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "error:" in result.output
    assert "dangling watch" in result.output


def test_notes_index_writes_catalog(tmp_path: Path):
    _write_example(tmp_path)
    _write_note(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["notes", "index", str(tmp_path)])
    assert result.exit_code == 0
    assert "updated" in result.output

    index_text = (tmp_path / ".agent-vault" / "index.md").read_text(encoding="utf-8")
    assert "greet-note.md" in index_text
