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
    assert checkout["with"]["path"] == "trusted"


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

    # git merge-tree never touches the working tree, so a clean merge changes
    # nothing (no proactive sync); only exit code 1 (conflicts) sets merged=true.
    assert "git merge-tree --write-tree" in sync
    assert '"$rc" -eq 0' in sync and "merged=false" in sync
    # The agent and the publisher must name the commits identically (marker
    # labels derive from the arguments), both by SHA, so the trees match.
    assert '"$head_sha" "$base_sha"' in sync
    assert '"$HEAD_SHA" "$BASE_SHA"' in publish


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
    assert "${commit}:refs/heads/${HEAD_REF}" in publish
    assert "--force" not in publish


def test_privileged_jobs_never_check_out_the_pr_branch() -> None:
    # issue_comment workflows can read secrets; the PR branch holds model-written
    # code. No checkout step may take a ref. The agent job reads the PR head as
    # files in a separate worktree; the publisher has no working tree from the
    # branch at all (git plumbing on a temporary index).
    workflow = _load(PR_WORKFLOW)
    for job in ("agent", "publish"):
        steps = workflow["jobs"][job]["steps"]
        for step in steps:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert "ref" not in step["with"]
                assert step["with"]["path"] == "trusted"
    agent_steps = workflow["jobs"]["agent"]["steps"]
    worktrees = [s for s in agent_steps if "git worktree add --detach ../pr" in s.get("run", "")]
    assert len(worktrees) == 1
    publish_steps = workflow["jobs"]["publish"]["steps"]
    publish_runs = chr(10).join(s.get("run", "") for s in publish_steps)
    assert "worktree" not in publish_runs
    assert "git checkout" not in publish_runs
    assert "GIT_INDEX_FILE" in publish_runs and "git commit-tree" in publish_runs
    assert "git apply --cached" in publish_runs


def test_tooling_and_config_come_from_the_trusted_checkout() -> None:
    workflow = _load(PR_WORKFLOW)
    steps = workflow["jobs"]["agent"]["steps"]
    install = next(s for s in steps if s.get("name", "").startswith("Install tooling"))
    aider = next(s for s in steps if "aider \\" in s.get("run", ""))
    hygiene = next(s for s in steps if s.get("id") == "hygiene")

    assert './trusted[dev]' in install["run"]
    # Repo-level aider config or .env could run commands with the model key.
    for flag in ("--config", "--env-file", "--no-auto-test", "--no-auto-lint"):
        assert flag in aider["run"]
    assert "$GITHUB_WORKSPACE/trusted/AGENTS.md" in aider["run"]
    # pre-commit runs hooks (pytest among them) that would execute the PR
    # branch's code in the privileged job; only direct, trusted fixers are used.
    commands = [
        line for line in hygiene["run"].splitlines() if not line.strip().startswith("#")
    ]
    code = chr(10).join(commands)
    assert "pre-commit" not in code
    assert "pytest" not in code
    assert "girdle index . --inject AGENTS.md" in code
    assert hygiene["working-directory"] == "pr"


def test_publisher_rejects_unresolved_conflict_markers() -> None:
    workflow = _load(PR_WORKFLOW)
    publish = next(
        s for s in workflow["jobs"]["publish"]["steps"] if "BASE_SHA" in s.get("env", {})
    )["run"]

    assert "<<<<<<<" in publish and "conflict markers" in publish
