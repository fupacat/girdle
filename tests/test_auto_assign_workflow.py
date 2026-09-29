from pathlib import Path

import yaml


def test_assign_job_skips_mergify_merge_queue_pull_requests():
    workflow_path = (
        Path(__file__).resolve().parent.parent
        / ".github/workflows/auto-assign-copilot.yml"
    )
    workflow = yaml.safe_load(workflow_path.read_text())
    condition = " ".join(workflow["jobs"]["assign"]["if"].split())
    assert (
        condition
        == "github.event_name != 'pull_request' || "
        "!startsWith(github.head_ref, 'mergify/merge-queue/')"
    )
