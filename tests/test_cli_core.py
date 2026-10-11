import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

import girdle.cli as cli
from girdle.cli import main
from girdle.vault import DanglingWatchError, WatchEntry


def _minimal_repo(root: Path) -> None:
    (root / "requirements.txt").write_text("click==8.1.7\n", encoding="utf-8")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def test_scan_json_output_and_fail_under_exit_codes(tmp_path: Path):
    _minimal_repo(tmp_path)
    runner = CliRunner()

    ok = runner.invoke(main, ["scan", str(tmp_path), "--json", "--fail-under", "0"])
    assert ok.exit_code == 0
    data = json.loads(ok.output)
    assert data["repo_root"] == str(tmp_path)

    fail = runner.invoke(main, ["scan", str(tmp_path), "--json", "--fail-under", "2"])
    assert fail.exit_code == 1


def test_scan_human_output_when_tty(tmp_path: Path, monkeypatch):
    _minimal_repo(tmp_path)

    class _FakeSys:
        class _TTY:
            @staticmethod
            def isatty():
                return True

        stdout = _TTY()
        exit = staticmethod(sys.exit)

    monkeypatch.setattr(cli, "sys", _FakeSys)

    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--fail-under", "0"])
    assert result.exit_code == 0
    assert result.output.startswith("girdle scan")
    assert '"repo_root"' not in result.output


def test_index_check_stale_and_fresh(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "AGENTS.md"
    target.write_text("# Agent instructions\n", encoding="utf-8")

    stale = runner.invoke(main, ["index", str(tmp_path), "--check", str(target)])
    assert stale.exit_code == 1
    assert stale.output.strip() == "stale"

    injected = runner.invoke(main, ["index", str(tmp_path), "--inject", str(target)])
    assert injected.exit_code == 0

    fresh = runner.invoke(main, ["index", str(tmp_path), "--check", str(target)])
    assert fresh.exit_code == 0
    assert fresh.output.strip() == "fresh"


def test_index_json_and_output_file(tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "index.json"
    result = runner.invoke(main, ["index", str(tmp_path), "--json", "--output", str(out)])
    assert result.exit_code == 0
    assert f"wrote {out}" in result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "entries" in data


def test_align_dry_run_vs_write(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 100\n", encoding="utf-8")
    runner = CliRunner()

    dry_run = runner.invoke(main, ["align", str(tmp_path)])
    assert dry_run.exit_code == 0
    assert "(dry run - pass --write to apply)" in dry_run.output
    assert not (tmp_path / ".editorconfig").exists()

    apply = runner.invoke(main, ["align", str(tmp_path), "--write"])
    assert apply.exit_code == 0
    assert "wrote changes" in apply.output
    assert (tmp_path / ".editorconfig").exists()


def test_align_reports_no_formatter_config(tmp_path: Path):
    result = CliRunner().invoke(main, ["align", str(tmp_path)])
    assert result.exit_code == 0
    assert "no formatter config detected to align from" in result.output


def test_dashboard_writes_html_report(tmp_path: Path):
    _minimal_repo(tmp_path)
    out = tmp_path / "report.html"
    result = CliRunner().invoke(main, ["dashboard", str(tmp_path), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert f"wrote {out}" in result.output


def test_notes_check_reports_dangling_watch_cleanly(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "example.py").write_text(
        'def greet(name):\n    return "hi"\n', encoding="utf-8"
    )
    (tmp_path / ".agent-vault" / "context").mkdir(parents=True, exist_ok=True)
    note_path = tmp_path / ".agent-vault" / "context" / "greet-note.md"
    note_path.write_text(
        "---\ntype: context\nwatches:\n  - path: src/example.py\n"
        "    symbol: greet\n    hash: null\nstale: false\n---\n\n# note\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    CliRunner().invoke(main, ["notes", "ack", str(note_path), "--path", str(tmp_path)])
    (tmp_path / "src" / "example.py").unlink()

    result = CliRunner().invoke(main, ["notes", "check", str(tmp_path)])
    assert result.exit_code == 1
    assert "stale:" in result.output
    assert "dangling watch" in result.output


def test_notes_check_handles_dangling_watch_error(tmp_path: Path, monkeypatch):
    def _raise(_: Path):
        raise DanglingWatchError(
            ".agent-vault/context/greet-note.md",
            [WatchEntry(path="src/example.py", symbol="greet")],
        )

    monkeypatch.setattr(cli, "vault_check", _raise)
    result = CliRunner().invoke(main, ["notes", "check", str(tmp_path)])
    assert result.exit_code == 1
    assert "error:" in result.output
    assert "dangling watch" in result.output
