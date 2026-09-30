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
