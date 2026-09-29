from pathlib import Path

import yaml


def test_fallback_sweep_checks_out_repository():
    workflow_path = Path(".github/workflows/auto-merge-copilot.yml")
    workflow = yaml.safe_load(workflow_path.read_text())
    steps = workflow["jobs"]["fallback-sweep"]["steps"]

    assert any(step.get("uses") == "actions/checkout@v7" for step in steps)
