"""CLI-level coverage for `girdle badge` - badge.py's own unit tests exercise
the URL/markdown/endpoint-schema functions directly, but the Click command
wiring (default vs --markdown vs --json, and -o file output) is only
exercised here.
"""

from pathlib import Path

from click.testing import CliRunner

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
