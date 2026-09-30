import re
from pathlib import Path

import yaml


def _workflow_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".github/workflows/auto-assign-copilot.yml"


def _workflow_text() -> str:
    return _workflow_path().read_text(encoding="utf-8")


def _normalized_workflow_text() -> str:
    return re.sub(r"\s+", " ", _workflow_text())


def _workflow_yaml() -> dict:
    return yaml.safe_load(_workflow_text())


def test_assign_job_skips_mergify_merge_queue_pull_requests() -> None:
    workflow = _workflow_yaml()
    condition = " ".join(workflow["jobs"]["assign"]["if"].split())
    assert (
        condition
        == "github.event_name != 'pull_request' || "
        "!startsWith(github.head_ref, 'mergify/merge-queue/')"
    )


def test_assign_job_uses_concurrency_group() -> None:
    workflow = _workflow_yaml()
    concurrency = workflow["jobs"]["assign"]["concurrency"]
    assert concurrency["cancel-in-progress"] is False
    assert (
        concurrency["group"]
        == "auto-assign-copilot-${{ github.event.pull_request.number || "
        "github.event.issue.number || 'sweep' }}"
    )


def test_adds_issue_to_project_before_status_sync() -> None:
    text = _normalized_workflow_text()
    assert "addProjectV2ItemById" in text
    assert "contentId: issue.id" in text
    assert "Added #${issue.number} to project #${projectNumber}" in text


def test_uses_pr_check_rollup_for_project_status() -> None:
    text = _normalized_workflow_text()
    assert text.count("statusCheckRollup") >= 2
    assert "statusCheckRollup { state }" in text


def test_status_logic_covers_ready_in_progress_in_review_done() -> None:
    text = _normalized_workflow_text()
    assert 'if (issue.state !== "OPEN") return "Done";' in text
    assert '"Done"' in text
    assert "issue.assignees.totalCount > 0" in text
    assert 'return "In Progress";' in text
    assert '"Ready"' in text
    assert "activePullRequests.some(pr => !pr.isDraft)" in text
    assert 'return "In Review";' in text


def test_ci_workflow_uses_pr_scoped_concurrency_and_fast_checks() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"
    assert concurrency["group"] == "ci-${{ github.event.pull_request.number || github.sha }}"

    jobs = workflow["jobs"]
    cheap = jobs["cheap-checks"]
    cheap_run_steps = [step["run"] for step in cheap["steps"] if "run" in step]
    assert any("ruff check ." in step for step in cheap_run_steps)
    assert any("mdformat --check --wrap keep" in step for step in cheap_run_steps)
    assert any("yamllint ." in step for step in cheap_run_steps)
    assert any("mergify config validate" in step for step in cheap_run_steps)
    assert any("girdle index . --check AGENTS.md" in step for step in cheap_run_steps)
    assert any("girdle notes check ." in step for step in cheap_run_steps)

    pytest_if = " ".join(jobs["pytest"]["if"].split())
    assert "needs.cheap-checks.result == 'success'" in pytest_if
    assert "needs.changes.outputs.light_diff != 'true'" in pytest_if
    assert "github.event.pull_request.draft" not in pytest_if

    sonar_if = " ".join(jobs["sonar"]["if"].split())
    assert "needs.cheap-checks.result == 'success'" in sonar_if
    assert "github.event.pull_request.draft" not in sonar_if

    assert jobs["test"]["needs"] == ["changes", "cheap-checks", "pytest", "sonar"]
    assert jobs["test"]["if"] == "always()"
    pytest_gate = next(
        step
        for step in jobs["test"]["steps"]
        if step["name"] == "pytest must pass or be skipped for light diffs"
    )
    pytest_gate_if = " ".join(pytest_gate["if"].split())
    assert "needs.pytest.result != 'success'" in pytest_gate_if
    assert (
        "needs.pytest.result != 'skipped' || "
        "needs.changes.outputs.light_diff != 'true'"
    ) in pytest_gate_if
