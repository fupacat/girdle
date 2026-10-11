import json
import types
from pathlib import Path

from click.testing import CliRunner

from girdle.cli import main


def _minimal_python_repo(root: Path) -> None:
    (root / "requirements.txt").write_text("click==8.1.7\n", encoding="utf-8")


def _python_repo_with_formatter(root: Path) -> None:
    _minimal_python_repo(root)
    (root / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 99\n[tool.ruff.format]\nindent-style = 'space'\n",
        encoding="utf-8",
    )


def test_scan_defaults_to_json_output(tmp_path: Path):
    _minimal_python_repo(tmp_path)
    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--fail-under", "0"])
    assert result.exit_code == 0
    assert json.loads(result.output)["repo_root"].endswith(str(tmp_path))


def test_scan_human_output_when_tty(monkeypatch, tmp_path: Path):
    _minimal_python_repo(tmp_path)
    fake_sys = types.SimpleNamespace(
        stdout=types.SimpleNamespace(isatty=lambda: True),
        exit=lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )
    monkeypatch.setattr("girdle.cli.sys", fake_sys)
    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--fail-under", "0"])
    assert result.exit_code == 0
    assert f"girdle scan  {tmp_path}" in result.output
    assert "summary:" in result.output


def test_scan_fail_under_nonzero_exit(tmp_path: Path):
    _minimal_python_repo(tmp_path)
    result = CliRunner().invoke(main, ["scan", str(tmp_path), "--fail-under", "2"])
    assert result.exit_code == 1


def test_dashboard_writes_output_file(tmp_path: Path):
    _minimal_python_repo(tmp_path)
    out = tmp_path / "report.html"
    result = CliRunner().invoke(main, ["dashboard", str(tmp_path), "-o", str(out)])
    assert result.exit_code == 0
    assert f"wrote {out}" in result.output
    assert "<!doctype html>" in out.read_text(encoding="utf-8").lower()


def test_index_check_stale_then_fresh(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# AGENTS\n", encoding="utf-8")
    runner = CliRunner()

    stale = runner.invoke(main, ["index", str(tmp_path), "--check", str(agents)])
    assert stale.exit_code == 1
    assert stale.output.strip() == "stale"

    injected = runner.invoke(main, ["index", str(tmp_path), "--inject", str(agents)])
    assert injected.exit_code == 0

    fresh = runner.invoke(main, ["index", str(tmp_path), "--check", str(agents)])
    assert fresh.exit_code == 0
    assert fresh.output.strip() == "fresh"

    (tmp_path / "src" / "b.py").write_text("def g():\n    return 2\n", encoding="utf-8")
    stale_again = runner.invoke(main, ["index", str(tmp_path), "--check", str(agents)])
    assert stale_again.exit_code == 1
    assert stale_again.output.strip() == "stale"


def test_index_json_output_writes_file(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "index.json"
    result = CliRunner().invoke(main, ["index", str(tmp_path), "--json", "-o", str(out)])
    assert result.exit_code == 0
    assert f"wrote {out}" in result.output
    assert '"entries"' in out.read_text(encoding="utf-8")


def test_align_dry_run_then_write(tmp_path: Path):
    _python_repo_with_formatter(tmp_path)
    runner = CliRunner()

    dry_run = runner.invoke(main, ["align", str(tmp_path)])
    assert dry_run.exit_code == 0
    assert "(dry run - pass --write to apply)" in dry_run.output
    assert not (tmp_path / ".editorconfig").exists()

    apply = runner.invoke(main, ["align", str(tmp_path), "--write"])
    assert apply.exit_code == 0
    assert "wrote changes" in apply.output
    assert (tmp_path / ".editorconfig").exists()
    assert (tmp_path / ".gitignore").exists()
