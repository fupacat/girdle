"""Tests for the shared scan_ci helper in detectors._util."""

from pathlib import Path

from girdle.detectors._util import scan_ci
from girdle.schema import Tier


def test_github_actions_match(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("- run: go test ./...\n")
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
    (wf_dir / "ci.yml").write_text("- run: echo hello\n")
    result = scan_ci(tmp_path, r"\bgo test\b", "go test ./...")
    assert result.tier == Tier.ABSENT


def test_gradle_pattern_matches_gradlew_and_gradle(tmp_path: Path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("- run: gradle test\n")
    result = scan_ci(tmp_path, r"gradlew?\b.*\btest\b", "./gradlew test")
    assert result.tier == Tier.CONFIGURED
