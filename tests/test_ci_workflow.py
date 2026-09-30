from pathlib import Path

import yaml


def _workflow() -> dict:
    return yaml.safe_load(Path(".github/workflows/ci.yml").read_text())


def test_ci_concurrency_is_scoped_to_pr_and_does_not_cancel_pushes() -> None:
    workflow = _workflow()
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"
    assert concurrency["group"] == "ci-${{ github.event.pull_request.number || github.ref }}"


def test_ci_runs_cheap_checks_before_expensive_and_skips_draft_prs() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert "cheap-checks" in jobs
    assert "pytest" in jobs
    assert "sonar" in jobs
    assert "test" in jobs

    assert jobs["pytest"]["needs"] == ["changes", "cheap-checks"]
    assert "github.event.pull_request.draft == false" in jobs["pytest"]["if"]
    assert jobs["sonar"]["needs"] == ["changes", "cheap-checks", "pytest"]
    assert "github.event.pull_request.draft == false" in jobs["sonar"]["if"]

    assert jobs["test"]["if"] == "always()"
    assert jobs["test"]["needs"] == ["cheap-checks", "pytest"]
