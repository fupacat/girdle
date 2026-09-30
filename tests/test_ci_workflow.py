from pathlib import Path

import yaml


def _workflow() -> dict:
    return yaml.safe_load(Path(".github/workflows/ci.yml").read_text())


def test_ci_concurrency_cancels_superseded_runs_on_pr_head_ref() -> None:
    workflow = _workflow()
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] is True
    assert concurrency["group"] == "ci-${{ github.event.pull_request.head.ref || github.ref_name }}"


def test_ci_runs_cheap_checks_before_expensive_and_skips_draft_prs() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert "cheap-checks" in jobs
    assert "pytest" in jobs
    assert "sonar" in jobs
    assert "test" in jobs

    assert jobs["pytest"]["needs"] == "cheap-checks"
    assert "github.event.pull_request.draft == false" in jobs["pytest"]["if"]
    assert jobs["sonar"]["needs"] == "cheap-checks"
    assert "github.event.pull_request.draft == false" in jobs["sonar"]["if"]

    assert jobs["test"]["if"] == "always()"
    assert jobs["test"]["needs"] == ["cheap-checks", "pytest"]
