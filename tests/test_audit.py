import json
from pathlib import Path
from unittest.mock import patch

from girdle.audit import (
    AGENT_INSTRUCTIONS_LOCATIONS,
    AuditFinding,
    audit_file,
    discover_instruction_files,
    parse_agent_output,
    run_audit,
)
from girdle.runner import RunOutcome


def test_audit_binary_not_found(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Do the thing.\n")
    with patch("girdle.audit.shutil.which", return_value=None):
        result = audit_file(tmp_path / "AGENTS.md", tmp_path, ["nonexistent-cli"], 300)
    assert result.available is False
    assert "not found" in result.reason


def test_audit_timeout(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Do the thing.\n")
    outcome = RunOutcome(ran=True, passed=False, reason="timed out after 300s")
    with patch("girdle.audit._invoke_agent", return_value=outcome):
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
    with patch("girdle.audit._invoke_agent", return_value=outcome) as mock_invoke:
        results = run_audit(tmp_path, files=[tmp_path / "README.md"])
    assert len(results) == 1
    assert results[0].target == "README.md"
    mock_invoke.assert_called_once()


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
