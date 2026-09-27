import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from girdle.audit import (
    AGENT_INSTRUCTIONS_LOCATIONS,
    AuditFinding,
    audit_file,
    discover_instruction_files,
    parse_agent_output,
    run_audit,
)
from girdle.cli import main
from girdle.runner import RunOutcome


def test_audit_binary_not_found(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Do the thing.\n")
    with patch("girdle.audit.shutil.which", return_value=None):
        result = audit_file(tmp_path / "AGENTS.md", tmp_path, ["nonexistent-cli"], 300)
    assert result.available is False
    assert "not found" in result.reason


def test_audit_missing_file_is_unavailable_not_a_crash(tmp_path: Path):
    # --file allows a not-yet-existing path through click validation
    # (exists=False) - audit_file must degrade gracefully, not raise
    # FileNotFoundError. Force past the "which" gate so this exercises the
    # is_file() check specifically, regardless of whether `claude` happens
    # to be on PATH in this environment.
    with patch("girdle.audit.shutil.which", return_value="/usr/bin/claude"):
        result = audit_file(tmp_path / "does-not-exist.md", tmp_path, ["claude", "-p"], 300)
    assert result.available is False
    assert "not found" in result.reason


def test_audit_directory_target_is_unavailable_not_a_crash(tmp_path: Path):
    subdir = tmp_path / "a-directory"
    subdir.mkdir()
    with patch("girdle.audit.shutil.which", return_value="/usr/bin/claude"):
        result = audit_file(subdir, tmp_path, ["claude", "-p"], 300)
    assert result.available is False


def test_audit_timeout(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Do the thing.\n")
    outcome = RunOutcome(ran=True, passed=False, reason="timed out after 300s")
    with (
        patch("girdle.audit.shutil.which", return_value="/usr/bin/claude"),
        patch("girdle.audit._invoke_agent", return_value=outcome),
    ):
        result = audit_file(tmp_path / "AGENTS.md", tmp_path, ["claude", "-p"], 300)
    assert result.available is False
    assert result.reason == "timed out after 300s"


def test_audit_outer_json_unparseable():
    findings, error = parse_agent_output("not json")
    assert findings is None
    assert "not valid JSON" in error


def test_audit_inner_result_not_json():
    stdout = json.dumps({"result": "plain text"})
    findings, error = parse_agent_output(stdout)
    assert findings is None
    assert "ignored format instruction" in error


def test_audit_result_field_not_a_string():
    # A non-conforming agent CLI (or --agent-cmd override) could return a
    # "result" that's an object/list/number instead of a string - must
    # degrade gracefully, not raise TypeError out of json.loads.
    stdout = json.dumps({"result": {"not": "a string"}})
    findings, error = parse_agent_output(stdout)
    assert findings is None
    assert "missing string result field" in error


def test_audit_fully_valid():
    inner = [
        {"excerpt": "Always run pytest.", "bucket": "1", "rationale": "already a pre-commit hook",
         "citation": "pre-commit pytest hook"},
    ]
    stdout = json.dumps({"result": json.dumps(inner)})
    findings, error = parse_agent_output(stdout)
    assert error is None
    assert findings == [
        AuditFinding(
            excerpt="Always run pytest.", bucket=1,
            rationale="already a pre-commit hook", citation="pre-commit pytest hook",
        )
    ]


def test_discover_instruction_files_partial(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("x\n")
    found = discover_instruction_files(tmp_path)
    assert found == [tmp_path / "AGENTS.md"]
    assert len(AGENT_INSTRUCTIONS_LOCATIONS) == 3


def test_run_audit_explicit_files_override_discovery(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("x\n")
    (tmp_path / "README.md").write_text("y\n")
    outcome = RunOutcome(ran=True, passed=True, reason=None, stdout=json.dumps({"result": "[]"}))
    with (
        patch("girdle.audit.shutil.which", return_value="/usr/bin/claude"),
        patch("girdle.audit._invoke_agent", return_value=outcome) as mock_invoke,
    ):
        results = run_audit(tmp_path, files=[tmp_path / "README.md"])
    assert len(results) == 1
    assert results[0].target == "README.md"
    mock_invoke.assert_called_once()


def test_audit_cmd_bad_agent_cmd_quoting_is_usage_error(tmp_path: Path):
    # shlex.split raises ValueError on unbalanced quotes - must surface as a
    # normal Click usage error, not an unhandled traceback.
    (tmp_path / "AGENTS.md").write_text("x\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["audit", str(tmp_path), "--agent-cmd", "claude -p 'unterminated"]
    )
    assert result.exit_code == 2
    assert "--agent-cmd" in result.output


def test_parse_agent_output_malformed_entry_skipped():
    inner = [
        {"excerpt": "good", "bucket": "2", "rationale": "r", "citation": "PostToolUse hook"},
        {"excerpt": "missing bucket field"},
    ]
    stdout = json.dumps({"result": json.dumps(inner)})
    findings, error = parse_agent_output(stdout)
    assert error is None
    assert len(findings) == 1
    assert findings[0].excerpt == "good"
