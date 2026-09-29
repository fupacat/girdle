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
