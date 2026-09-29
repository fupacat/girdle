from pathlib import Path


def test_assign_job_skips_mergify_merge_queue_pull_requests():
    workflow_path = (
        Path(__file__).resolve().parent.parent
        / ".github/workflows/auto-assign-copilot.yml"
    )
    workflow = workflow_path.read_text()
    assert (
        "${{\n"
        "        github.event_name != 'pull_request' ||\n"
        "        !startsWith(github.head_ref, 'mergify/merge-queue/')\n"
        "      }}"
    ) in workflow
