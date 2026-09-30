import re
from pathlib import Path

import yaml

PR_WORKFLOW = ".github/workflows/gemini-agent-pr.yml"
ISSUE_WORKFLOW = ".github/workflows/gemini-agent.yml"


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _job_text(workflow: dict, job: str) -> str:
    return yaml.safe_dump(workflow["jobs"][job])


def test_actions_are_pinned_to_full_commit_shas() -> None:
    for path in (PR_WORKFLOW, ISSUE_WORKFLOW):
        workflow = _load(path)
        for name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses:
                    assert re.search(r"@[0-9a-f]{40}$", uses), f"{path} {name}: {uses}"


def test_model_key_and_push_token_never_share_a_job() -> None:
    workflow = _load(PR_WORKFLOW)
    agent = _job_text(workflow, "agent")
    publish = _job_text(workflow, "publish")
    resolve = _job_text(workflow, "resolve")

    assert "OPENROUTER_API_KEY" in agent and "AGENT_PR_TOKEN" not in agent
    assert "AGENT_PR_TOKEN" in publish and "OPENROUTER_API_KEY" not in publish
    assert "OPENROUTER_API_KEY" not in resolve and "AGENT_PR_TOKEN" not in resolve


def test_agent_job_is_read_only_and_does_not_persist_credentials() -> None:
    workflow = _load(PR_WORKFLOW)

    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["agent"]  # inherits contents: read
    checkout = workflow["jobs"]["agent"]["steps"][0]
    assert checkout["with"]["persist-credentials"] is False


def test_only_trusted_commenters_on_prs_reach_the_workflow() -> None:
    condition = _load(PR_WORKFLOW)["jobs"]["resolve"]["if"]

    assert "github.event.issue.pull_request" in condition
    assert "@gemini" in condition
    assert '["OWNER","MEMBER","COLLABORATOR"]' in condition
    assert "github.event.comment.author_association" in condition


def test_resolve_enforces_branch_label_fork_and_repair_cap() -> None:
    workflow = _load(PR_WORKFLOW)
    step = next(s for s in workflow["jobs"]["resolve"]["steps"] if s.get("id") == "resolve")
    script = step["run"]

    assert "isCrossRepository" in script
    assert "gemini/*" in script
    assert "agent-pr" in script
    assert "repair:[0-9]+" in script
    assert '-ge 2' in script and "--add-label manual" in script


def test_master_is_merged_only_for_a_real_conflict_and_at_a_pinned_sha() -> None:
    workflow = _load(PR_WORKFLOW)
    agent = workflow["jobs"]["agent"]["steps"]
    sync = next(s for s in agent if s.get("id") == "sync")["run"]
    publish = next(
        s for s in workflow["jobs"]["publish"]["steps"] if "BASE_SHA" in s.get("env", {})
    )["run"]

    assert "git merge --no-commit --no-ff" in sync
    assert "git merge --abort" in sync  # clean merge: never sync proactively
    assert 'git merge --no-commit --no-ff "$BASE_SHA"' in publish  # replay at the agent's SHA


def test_aider_runs_without_auto_commits_or_shell_suggestions() -> None:
    workflow = _load(PR_WORKFLOW)
    aider = next(
        s for s in workflow["jobs"]["agent"]["steps"] if "aider \\" in s.get("run", "")
    )["run"]

    for flag in ("--no-auto-commits", "--no-suggest-shell-commands", "--yes-always"):
        assert flag in aider


def test_publisher_refuses_workflow_changes_and_labels_the_cycle() -> None:
    workflow = _load(PR_WORKFLOW)
    publish = next(
        s for s in workflow["jobs"]["publish"]["steps"] if "BASE_SHA" in s.get("env", {})
    )["run"]

    assert ".github/workflows/" in publish
    assert '"repair:$((REPAIR_N + 1))"' in publish
    assert "HEAD:refs/heads/${HEAD_REF}" in publish
    assert "--force" not in publish
