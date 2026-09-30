from pathlib import Path

import yaml


def _workflow() -> dict:
    return yaml.safe_load(Path(".github/workflows/gemini-agent.yml").read_text(encoding="utf-8"))


def _publish_steps() -> list[dict]:
    return _workflow()["jobs"]["publish"]["steps"]


def test_publisher_labels_prs_so_the_promote_sweep_picks_them_up() -> None:
    step = next(s for s in _publish_steps() if s.get("name") == "Create Pull Request")

    assert step["with"]["labels"] == "agent-pr"
    assert step["with"]["branch"].startswith("gemini/issue-")
    assert step["with"]["draft"] is True


def test_publisher_uses_the_dedicated_pr_token() -> None:
    step = next(s for s in _publish_steps() if s.get("name") == "Create Pull Request")

    assert step["with"]["token"] == "${{ secrets.AGENT_PR_TOKEN }}"


def test_failed_runs_are_reported_on_the_issue() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["report-failure"]

    assert job["needs"] == ["gemini-agent", "publish"]
    assert "always()" in job["if"]
    assert "needs.gemini-agent.result == 'failure'" in job["if"]
    assert "needs.publish.result == 'failure'" in job["if"]
    # No model key and no push token in the reporting job; it only comments.
    text = yaml.safe_dump(job)
    assert "OPENROUTER_API_KEY" not in text and "AGENT_PR_TOKEN" not in text
    assert job["permissions"] == {"contents": "read", "issues": "write", "actions": "read"}
    run = next(s for s in job["steps"] if "run" in s)
    assert run["run"] == "bash .github/scripts/report-agent-failure.sh"
    assert run["env"]["TRIGGER_LABEL"].startswith("${{ github.event_name == 'issues'")


def test_report_script_handles_spend_limits_and_defuses_untrusted_text() -> None:
    script = Path(".github/scripts/report-agent-failure.sh").read_text(encoding="utf-8")

    assert "insufficient credits" in script and "402" in script  # spend limit
    assert "429" in script  # rate limit
    assert '--add-label "agent:failed"' in script
    assert '--remove-label "$TRIGGER_LABEL"' in script  # no re-trigger loop on spend
    # The error line comes from a log that can echo model output or issue text.
    assert "sed 's/@/(at)/g'" in script and "cut -c1-300" in script


# Flags confirmed against aider's own usage text in a real Actions run (the first
# acceptance run died with "unrecognized arguments: --no-dirty-check"). --config
# is used by the PR-mode workflow and is confirmed there by the PR-mode run.
AIDER_FLAGS = {
    "--model", "--read", "--file", "--message", "--yes-always", "--env-file", "--config",
    "--auto-commits", "--no-auto-commits", "--no-dirty-commits",
    "--no-auto-lint", "--no-auto-test", "--no-suggest-shell-commands",
    "--no-check-update", "--no-analytics",
}  # fmt: skip


def test_aider_is_only_given_flags_it_accepts() -> None:
    import re

    for path in (".github/workflows/gemini-agent.yml", ".github/workflows/gemini-agent-pr.yml"):
        workflow = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                run = step.get("run", "")
                if "aider \\" not in run:
                    continue
                invocation = run[run.index("aider \\"):]
                used = set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", invocation))
                assert used <= AIDER_FLAGS, f"{path}: {sorted(used - AIDER_FLAGS)}"
