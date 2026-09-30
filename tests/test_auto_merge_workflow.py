from pathlib import Path

import yaml


def _workflow() -> dict:
    workflow_path = Path(".github/workflows/auto-merge-copilot.yml")
    return yaml.safe_load(workflow_path.read_text())


def test_fallback_sweep_checks_out_repository() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["fallback-sweep"]["steps"]

    assert any(step.get("uses") == "actions/checkout@v7" for step in steps)


def test_workflow_run_and_schedule_drive_check_based_promotion() -> None:
    workflow = _workflow()
    triggers = workflow.get("on", workflow.get(True))

    assert triggers["push"]["branches"] == ["master"]
    assert triggers["workflow_run"]["workflows"] == ["CI"]
    assert triggers["workflow_run"]["types"] == ["completed"]
    assert triggers["schedule"][0]["cron"] == "*/15 * * * *"


def test_reactive_mark_ready_skips_empty_or_plan_only_prs() -> None:
    workflow = _workflow()
    run_script = workflow["jobs"]["auto-merge"]["steps"][0]["run"]

    assert "--json state,changedFiles,commits" in run_script
    assert 'if [ "$changed_files" -eq 0 ]; then' in run_script
    assert "^initial[[:space:]]+plan" in run_script
    assert "only initial-plan commit and 0 changed files" in run_script
    assert "Skipping PR #$pr_number: 0 changed files." in run_script


def test_fallback_sweep_skips_empty_conflicting_or_blocklisted_prs() -> None:
    workflow = _workflow()
    run_script = workflow["jobs"]["fallback-sweep"]["steps"][1]["run"]

    assert "--json" in run_script
    assert "mergeable" in run_script
    assert "labels" in run_script
    assert "statusCheckRollup" in run_script
    assert 'if [ "$changed_files" -eq 0 ]; then' in run_script
    assert "^initial[[:space:]]+plan" in run_script
    assert "0 changed files" in run_script
    assert "merge conflict or mergeability not yet resolved" in run_script
    assert "label blocklist applied" in run_script


def test_conflict_nudge_sweep_uses_master_sha_marker_and_clears_label() -> None:
    workflow = _workflow()
    run_script = workflow["jobs"]["conflict-nudge-sweep"]["steps"][0]["run"]

    assert "COPILOT_ASSIGN_TOKEN is not configured" in run_script
    assert 'master_sha=$(gh api "repos/$GH_REPO/git/ref/heads/master"' in run_script
    assert 'marker="<!-- conflict-nudge:${master_sha} -->"' in run_script
    assert 'if [ "$mergeable" = "null" ] || [ "$mergeable_state" = "unknown" ]; then' in run_script
    assert "manual label applied" in run_script
    assert "repos/$GH_REPO/issues/$pr/comments?per_page=100" in run_script
    assert "@copilot This PR has a merge conflict with `master`." in run_script
    assert "labels[]=conflict-nudged" in run_script
    assert "labels/conflict-nudged\" -X DELETE" in run_script
