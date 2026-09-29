from pathlib import Path


def test_assign_job_skips_mergify_merge_queue_pull_requests():
    workflow = Path(".github/workflows/auto-assign-copilot.yml").read_text()
    assert "github.event_name != 'pull_request'" in workflow
    assert "startsWith(github.head_ref, 'mergify/merge-queue/')" in workflow
