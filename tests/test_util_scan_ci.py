"""Tests for the shared scan_ci helper in detectors._util."""

from pathlib import Path

from girdle.detectors._util import scan_ci
from girdle.schema import Tier


def _gha_workflow(on_block: str, run_command: str, comments: str = "") -> str:
    return (
        "name: ci\n"
        f"on:\n{on_block}\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"{comments}"
        f"      - run: {run_command}\n"
    )


def test_github_actions_match(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        _gha_workflow("  pull_request: {}\n", "go test ./...\n"),
    )
    result = scan_ci(tmp_path, r"\bgo test\b", "go test ./...")
    assert result.tier == Tier.CONFIGURED
    assert any("ci.yml" in e for e in result.evidence)


def test_gitlab_fallback(tmp_path: Path):
    (tmp_path / ".gitlab-ci.yml").write_text("script:\n  - cargo test\n")
    result = scan_ci(tmp_path, r"\bcargo test\b", "cargo test")
    assert result.tier == Tier.CONFIGURED
    assert any(".gitlab-ci.yml" in e for e in result.evidence)


def test_azure_fallback(tmp_path: Path):
    (tmp_path / "azure-pipelines.yml").write_text("- script: dotnet test\n")
    result = scan_ci(tmp_path, r"\bdotnet test\b", "dotnet test")
    assert result.tier == Tier.CONFIGURED
    assert any("azure-pipelines.yml" in e for e in result.evidence)


def test_absent_when_no_ci(tmp_path: Path):
    result = scan_ci(tmp_path, r"\bmvn\b.*\btest\b", "mvn test")
    assert result.tier == Tier.ABSENT
    assert result.recommendation is not None
    assert "mvn test" in result.recommendation


def test_no_match_in_workflow(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(_gha_workflow("  pull_request: {}\n", "echo hello\n"))
    result = scan_ci(tmp_path, r"\bgo test\b", "go test ./...")
    assert result.tier == Tier.ABSENT


def test_gradle_pattern_matches_gradlew_and_gradle(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(_gha_workflow("  pull_request: {}\n", "gradle test\n"))
    result = scan_ci(tmp_path, r"gradlew?\b.*\btest\b", "./gradlew test")
    assert result.tier == Tier.CONFIGURED


def test_comment_only_match_is_ignored(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        _gha_workflow(
            "  pull_request: {}\n",
            "echo done\n",
            comments="      # pytest\n",
        )
    )
    result = scan_ci(tmp_path, r"\bpytest\b", "pytest")
    assert result.tier == Tier.ABSENT


def test_comment_only_match_inside_run_block_is_ignored(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        "name: ci\n"
        "on:\n"
        "  pull_request: {}\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: |\n"
        "          # pytest\n"
        "          echo done\n"
    )
    result = scan_ci(tmp_path, r"\bpytest\b", "pytest")
    assert result.tier == Tier.ABSENT


def test_schedule_only_workflow_does_not_count_as_pr_gate(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        _gha_workflow("  schedule:\n    - cron: '0 0 * * *'\n", "pytest -q\n")
    )
    result = scan_ci(tmp_path, r"\bpytest\b", "pytest")
    assert result.tier == Tier.ABSENT


def test_reports_valid_workflow_even_if_not_first_file(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "a-schedule.yml").write_text(
        _gha_workflow("  schedule:\n    - cron: '0 0 * * *'\n", "pytest -q\n")
    )
    (wf_dir / "z-ci.yml").write_text(_gha_workflow("  pull_request: {}\n", "pytest -q\n"))
    result = scan_ci(tmp_path, r"\bpytest\b", "pytest")
    assert result.tier == Tier.CONFIGURED
    assert result.evidence == [".github/workflows/z-ci.yml: runs pytest"]
