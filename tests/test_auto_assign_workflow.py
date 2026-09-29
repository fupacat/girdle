import re
from pathlib import Path


def _workflow_text() -> str:
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/auto-assign-copilot.yml"
    return workflow.read_text(
        encoding="utf-8",
    )


def _normalized_workflow_text() -> str:
    return re.sub(r"\s+", " ", _workflow_text())


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
