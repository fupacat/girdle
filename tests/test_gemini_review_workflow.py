import re
from pathlib import Path

import yaml

WORKFLOW = ".github/workflows/gemini-review-pr.yml"


def _load() -> dict:
    return yaml.safe_load(Path(WORKFLOW).read_text(encoding="utf-8"))


def _job_text(workflow: dict, job: str) -> str:
    return yaml.safe_dump(workflow["jobs"][job])


def test_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = _load()
    for name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses:
                assert re.search(r"@[0-9a-f]{40}$", uses), f"{name}: {uses}"


def test_model_key_and_write_permissions_are_split_between_jobs() -> None:
    workflow = _load()
    review = _job_text(workflow, "review")
    publish = _job_text(workflow, "publish")
    resolve = _job_text(workflow, "resolve")

    assert "OPENROUTER_API_KEY" in review
    assert "OPENROUTER_API_KEY" not in publish
    assert "OPENROUTER_API_KEY" not in resolve
    assert workflow["jobs"]["publish"]["permissions"]["pull-requests"] == "write"
    assert "permissions" not in workflow["jobs"]["review"]  # inherited contents: read


def test_only_ready_trusted_non_fork_prs_are_considered() -> None:
    workflow = _load()
    resolve = _job_text(workflow, "resolve")

    assert "draft" in resolve and "pr-is-draft" in resolve
    assert "fork" in resolve and "does not review fork PRs" in resolve
    assert "OWNER|MEMBER|COLLABORATOR" in resolve
    assert "github-actions[bot]" in resolve


def test_same_head_is_not_reviewed_twice() -> None:
    workflow = _load()
    resolve = _job_text(workflow, "resolve")
    concurrency = workflow["concurrency"]["group"]

    assert "already-reviewed-this-head" in resolve
    assert ".commit_id == $sha" in resolve
    assert "${{ github.event.pull_request.head.sha }}" in concurrency


def test_high_risk_changes_are_never_auto_approved() -> None:
    workflow = _load()
    resolve = _job_text(workflow, "resolve")
    publish = _job_text(workflow, "publish")
    publish_if = workflow["jobs"]["publish"]["if"]

    assert ".mergify.yml" in resolve
    assert '.github/workflows/' in resolve
    assert "src/girdle/schema.py" in resolve
    assert "src/girdle/detectors/base.py" in resolve
    assert "mode=high-risk" in resolve
    assert "REQUEST_CHANGES" in publish
    assert "needs.review.result == 'skipped'" in publish_if


def test_prompt_uses_trusted_rubric_and_caps_diff_size() -> None:
    workflow = _load()
    review = _job_text(workflow, "review")
    checkout = workflow["jobs"]["review"]["steps"][0]

    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["path"] == "trusted"
    assert checkout["with"]["persist-credentials"] is False
    assert "trusted/.github/review/conventions.md" in review
    assert "trusted/.github/review/risk.md" in review
    assert "trusted/.github/review/spec-review.md" in review
    assert "MAX_DIFF_CHARS=120000" in review
    assert "json_object" in review
    assert "has_spec=true" in review


def test_model_or_api_error_posts_neutral_comment_not_approval() -> None:
    workflow = _load()
    publish = _job_text(workflow, "publish")

    assert "No approval" in publish and "was posted" in publish
    assert "STATUS" in publish and "DECISION" in publish
    assert "model/API error" in publish
    assert "pulls/$PR_NUM/reviews" in publish
