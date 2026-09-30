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
    lib = Path(".github/scripts/agent-failure-lib.sh").read_text(encoding="utf-8")

    assert "insufficient credits" in lib and "402" in lib  # spend limit
    assert "429" in lib  # rate limit
    assert '"labels[]=agent:failed"' in script
    assert '-X DELETE "$api/labels/$TRIGGER_LABEL"' in script  # no re-trigger loop on spend
    # The error line comes from text that can echo model output or issue text.
    assert "sed 's/@/(at)/g'" in lib and "cut -c1-300" in lib


def test_failure_is_classified_in_the_agent_job_not_from_the_api_log() -> None:
    # A run's job logs cannot be read through the API until the whole run has
    # completed, and the reporter runs inside the run (the first real reports had
    # no error line). The agent job has the model's output on disk: it tees it,
    # classifies it there, and hands the result on as job outputs.
    for path, job in (
        (".github/workflows/gemini-agent.yml", "gemini-agent"),
        (".github/workflows/gemini-agent-pr.yml", "agent"),
    ):
        workflow = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        steps = workflow["jobs"][job]["steps"]
        aider = next(s for s in steps if s.get("id") == "aider")
        classify = next(s for s in steps if s.get("id") == "classify")
        report = workflow["jobs"]["report-failure"]["steps"][-1]

        assert "set -o pipefail" in aider["run"]  # tee must not mask aider's exit code
        assert 'tee "$RUNNER_TEMP/aider.log"' in aider["run"]
        assert "steps.aider.outcome == 'failure'" in classify["if"]
        assert "classify-agent-failure.sh" in classify["run"]
        outputs = workflow["jobs"][job]["outputs"]
        assert outputs["failure_kind"] == "${{ steps.classify.outputs.kind }}"
        assert outputs["failure_error"] == "${{ steps.classify.outputs.error }}"
        assert report["env"]["FAILURE_KIND"] == "${{ needs." + job + ".outputs.failure_kind }}"
        assert report["env"]["FAILURE_ERROR"] == "${{ needs." + job + ".outputs.failure_error }}"


def test_dispatch_can_override_the_model() -> None:
    workflow = _workflow()
    inputs = workflow["on" if "on" in workflow else True]["workflow_dispatch"]["inputs"]

    assert inputs["model"]["required"] is False
    aider = next(
        s for s in workflow["jobs"]["gemini-agent"]["steps"] if s.get("id") == "aider"
    )
    assert "github.event.inputs.model" in aider["env"]["MODEL_NAME"]


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
