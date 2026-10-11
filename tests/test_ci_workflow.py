from pathlib import Path

import yaml


def _workflow() -> dict:
    return yaml.safe_load(Path(".github/workflows/ci.yml").read_text())


def test_ci_concurrency_is_scoped_to_pr_and_does_not_cancel_pushes() -> None:
    workflow = _workflow()
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"
    assert concurrency["group"] == "ci-${{ github.event.pull_request.number || github.ref }}"


def test_ci_runs_cheap_checks_before_expensive_and_skips_draft_prs() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert "cheap-checks" in jobs
    assert "pytest" in jobs
    assert "sonar" in jobs
    assert "test" in jobs

    assert jobs["pytest"]["needs"] == ["changes", "cheap-checks"]
    assert "github.event.pull_request.draft == false" in jobs["pytest"]["if"]
    assert jobs["sonar"]["needs"] == ["changes", "cheap-checks", "pytest"]
    assert "needs.pytest.result == 'success'" in jobs["sonar"]["if"]

    assert jobs["test"]["if"] == "always()"
    assert jobs["test"]["needs"] == ["changes", "cheap-checks", "pytest"]


def test_precommit_enforces_reqtrace_for_all_specs() -> None:
    workflow = _workflow()
    cheap_steps = workflow["jobs"]["cheap-checks"]["steps"]
    reqs_step = next(
        step
        for step in cheap_steps
        if step.get("name") == "requirements traceability (spec-*.md)"
    )
    assert reqs_step["run"] == "./scripts/check-spec-reqs.sh"

    precommit = yaml.safe_load(Path(".pre-commit-config.yaml").read_text(encoding="utf-8"))
    local_repo = next(repo for repo in precommit["repos"] if repo["repo"] == "local")
    reqs_hook = next(hook for hook in local_repo["hooks"] if hook["id"] == "girdle-reqs-check")
    assert reqs_hook["pass_filenames"] is False
    assert reqs_hook["always_run"] is True
    assert reqs_hook["entry"] == "./scripts/check-spec-reqs.sh"


def test_reqtrace_wrapper_checks_each_spec_file() -> None:
    script = Path("scripts/check-spec-reqs.sh").read_text(encoding="utf-8")
    assert ".agent-vault/context/spec-*.md" in script
    assert "failed=0" in script
    assert 'if ! girdle reqs check "$spec"' in script
    assert 'exit "$failed"' in script
