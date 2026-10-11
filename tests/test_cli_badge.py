"""CLI-level coverage for user-facing CLI commands.

`girdle badge`:
badge.py's own unit tests exercise
the URL/markdown/endpoint-schema functions directly, but the Click command
wiring (default vs --markdown vs --json, and -o file output) is only
exercised here.
"""

import json
import sys
from pathlib import Path

from click.testing import CliRunner

import girdle.cli as cli
from girdle.cli import main


def _minimal_repo(root: Path) -> None:
    (root / "requirements.txt").write_text("click==8.1.7\n", encoding="utf-8")


def test_badge_default_prints_bare_url(tmp_path: Path):
    _minimal_repo(tmp_path)
    result = CliRunner().invoke(main, ["badge", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output.strip().startswith("https://img.shields.io/badge/girdle-")


def test_badge_markdown_flag(tmp_path: Path):
    _minimal_repo(tmp_path)
    result = CliRunner().invoke(main, ["badge", str(tmp_path), "--markdown"])
    assert result.exit_code == 0
    assert result.output.strip().startswith("[![girdle](")


def test_badge_json_flag(tmp_path: Path):
    _minimal_repo(tmp_path)
    result = CliRunner().invoke(main, ["badge", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"schemaVersion": 1' in result.output


def test_badge_output_writes_file(tmp_path: Path):
    _minimal_repo(tmp_path)
    out = tmp_path / "girdle.json"
    result = CliRunner().invoke(main, ["badge", str(tmp_path), "--json", "-o", str(out)])
    assert result.exit_code == 0
    assert f"wrote {out}" in result.output
    assert '"schemaVersion": 1' in out.read_text(encoding="utf-8")


def test_scan_json_and_fail_under(tmp_path: Path):
    _minimal_repo(tmp_path)
    runner = CliRunner()

    ok = runner.invoke(main, ["scan", str(tmp_path), "--json", "--fail-under", "0"])
    assert ok.exit_code == 0
    data = json.loads(ok.output)
    assert data["repo_root"] == str(tmp_path)

    fail = runner.invoke(main, ["scan", str(tmp_path), "--json", "--fail-under", "2"])
    assert fail.exit_code == 1


def test_scan_human_tty(tmp_path: Path, monkeypatch):
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


def test_index_check_stale_fresh(tmp_path: Path):
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


def test_index_json_output_file(tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "index.json"
    result = runner.invoke(main, ["index", str(tmp_path), "--json", "--output", str(out)])
    assert result.exit_code == 0
    assert f"wrote {out}" in result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "entries" in data


def test_align_dry_run_and_write(tmp_path: Path):
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


def test_align_no_formatter_notice(tmp_path: Path):
    result = CliRunner().invoke(main, ["align", str(tmp_path)])
    assert result.exit_code == 0
    assert "no formatter config detected to align from" in result.output


def test_dashboard_writes_report(tmp_path: Path):
    _minimal_repo(tmp_path)
    out = tmp_path / "report.html"
    result = CliRunner().invoke(main, ["dashboard", str(tmp_path), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert f"wrote {out}" in result.output
