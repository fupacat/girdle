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
    # A requested-changes review blocks the merge until dismissed; withholding the
    # approval is enough, so high-risk PRs get a plain comment review.
    assert "event='COMMENT'" in publish
    assert "event='REQUEST_CHANGES'" not in publish
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
    assert "TRUNCATED_FOR_BUDGET" not in review  # never review a partial diff
    assert "json_object" in review
    assert "has_spec=true" in review


def test_model_or_api_error_posts_neutral_comment_not_approval() -> None:
    workflow = _load()
    publish = _job_text(workflow, "publish")

    assert "No approval" in publish and "was posted" in publish
    assert "STATUS" in publish and "DECISION" in publish
    assert "model/API error" in publish
    assert "pulls/$PR_NUM/reviews" in publish


def test_partial_diffs_fail_closed_and_are_never_approved() -> None:
    workflow = _load()
    review = _job_text(workflow, "review")
    publish = _job_text(workflow, "publish")

    # Large or binary files have no .patch in the API, and an over-budget diff is
    # not truncated: both end the job before the model is called, with no decision.
    assert "(.patch == null)" in review
    assert review.count("status=incomplete") == 3  # no patch, over budget, unreadable spec
    assert review.index("status=incomplete") < review.index("openrouter.ai")
    assert "incomplete" in publish
    assert "no approval." in publish


def test_model_id_is_sent_in_openrouter_form_not_aider_form() -> None:
    # The repo's variables use aider's "openrouter/<vendor>/<model>"; OpenRouter's
    # own API rejects that prefix with HTTP 400.
    review = _job_text(_load(), "review")

    assert "${MODEL_NAME#openrouter/}" in review


def test_unparseable_replies_are_diagnosed_and_given_room_to_finish() -> None:
    # The first real run ended "not valid review JSON" with no way to see why; a
    # reasoning model can spend a small max_tokens before it writes the answer.
    review = _job_text(_load(), "review")

    assert "max_tokens: 16000" in review
    assert "finish_reason" in review
    assert "content head" in review


def test_spec_reviews_see_the_whole_spec_not_just_the_diff() -> None:
    # #503 changed only a spec's frontmatter; a reviewer shown the patch alone
    # concluded the spec "defines no requirements" and requested changes.
    review = _job_text(_load(), "review")

    assert "spec-.*[.]md" in review  # the rubric's own scope, not any "spec" filename
    assert "application/vnd.github.raw" in review
    assert "SPEC_FILES" in review
    assert "SPEC_FILE:" in review
    assert "Could not read the full spec" in review  # fails closed, no approval
