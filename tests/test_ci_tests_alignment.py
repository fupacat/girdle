"""Tests for the ci_gating vs. tests alignment check in scan.py."""

from __future__ import annotations

from pathlib import Path

from girdle.detectors.base import Fingerprint
from girdle.scan import _check_ci_tests_alignment
from girdle.schema import CategoryResult, Tier


def _fp(tmp_path: Path) -> Fingerprint:
    return Fingerprint(id="fake", language="fake", toolchain="fake", root=tmp_path, variants=[])


class _FakeDetector:
    def __init__(self, test_cmd: list[str] | None = None):
        self._test_cmd = test_cmd

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        if self._test_cmd is None:
            return {}
        return {"tests": self._test_cmd}


def _write_gha_workflow(tmp_path: Path, content: str) -> None:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "ci.yml").write_text(content)


# ── both categories must be CONFIGURED for the check to fire ─────────────────


def test_noop_when_tests_absent(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: pytest")
    categories = {
        "tests": CategoryResult(Tier.ABSENT, reason="no tests"),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml: runs pytest"]),
    }
    detector = _FakeDetector(["pytest", "-q"])
    _check_ci_tests_alignment(detector, _fp(tmp_path), categories)
    # No alignment evidence appended when tests is absent.
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


def test_noop_when_ci_gating_absent(tmp_path: Path):
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.ABSENT, reason="no CI"),
    }
    detector = _FakeDetector(["pytest", "-q"])
    _check_ci_tests_alignment(detector, _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


def test_noop_when_no_run_commands(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: something-else")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml"]),
    }

    class NoRunCommands:
        pass

    _check_ci_tests_alignment(NoRunCommands(), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


def test_noop_when_no_tests_entry_in_run_commands(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: something-else")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml"]),
    }
    _check_ci_tests_alignment(_FakeDetector(None), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


# ── aligned: CI contains the expected command ─────────────────────────────────


def test_aligned_pytest_in_gha(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: pytest -q --cov\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml: runs pytest"]),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)
    assert categories["ci_gating"].recommendation is None


def test_aligned_npm_test_in_gha(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: npm test\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["package.json#scripts.test"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml: runs npm test"]),
    }
    _check_ci_tests_alignment(_FakeDetector(["npm", "test"]), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


def test_aligned_via_gitlab_ci(tmp_path: Path):
    (tmp_path / ".gitlab-ci.yml").write_text("script:\n  - pytest\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=[".gitlab-ci.yml: runs pytest"]),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


def test_aligned_via_azure_pipelines(tmp_path: Path):
    (tmp_path / "azure-pipelines.yml").write_text("script: pytest\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["azure-pipelines.yml: runs pytest"]),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)


# ── misaligned: CI is configured but doesn't run the test command ─────────────


def test_headline_drift_does_not_mask_alignment_gap(tmp_path: Path):
    _write_gha_workflow(
        tmp_path,
        "name: Run pytest suite (headline)\n"
        "# pytest is configured\n"
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      - run: python -m unittest\n",
    )
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(
            Tier.CONFIGURED, evidence=["ci.yml: runs python -m unittest"]
        ),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    alignment_evidence = [e for e in categories["ci_gating"].evidence if "alignment" in e]
    assert alignment_evidence, "Expected headline drift not to mask alignment gap"


def test_mismatch_flags_alignment_gap(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: python -m unittest\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(
            Tier.CONFIGURED, evidence=["ci.yml: runs python -m unittest"]
        ),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    alignment_evidence = [e for e in categories["ci_gating"].evidence if "alignment" in e]
    assert alignment_evidence, "Expected an alignment finding"
    assert "pytest" in alignment_evidence[0]


def test_mismatch_sets_recommendation(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: python -m unittest\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(
            Tier.CONFIGURED, evidence=["ci.yml: runs python -m unittest"]
        ),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    assert categories["ci_gating"].recommendation is not None
    assert "pytest" in categories["ci_gating"].recommendation


def test_mismatch_does_not_override_existing_recommendation(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: python -m unittest\n")
    existing_rec = "Custom existing recommendation."
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(
            Tier.CONFIGURED,
            evidence=["ci.yml"],
            recommendation=existing_rec,
        ),
    }
    _check_ci_tests_alignment(_FakeDetector(["pytest", "-q"]), _fp(tmp_path), categories)
    assert categories["ci_gating"].recommendation == existing_rec


def test_mismatch_js_npm(tmp_path: Path):
    _write_gha_workflow(tmp_path, "run: yarn test\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["package.json"]),
        "ci_gating": CategoryResult(Tier.CONFIGURED, evidence=["ci.yml: runs yarn test"]),
    }
    _check_ci_tests_alignment(_FakeDetector(["npm", "test"]), _fp(tmp_path), categories)
    alignment_evidence = [e for e in categories["ci_gating"].evidence if "alignment" in e]
    assert alignment_evidence, "Expected alignment finding when CI runs yarn but command is npm"


def test_poetry_prefix_stripped_for_search(tmp_path: Path):
    """'poetry run pytest' in CI should match ['poetry', 'run', 'pytest'] test cmd."""
    _write_gha_workflow(tmp_path, "run: poetry run pytest\n")
    categories = {
        "tests": CategoryResult(Tier.CONFIGURED, evidence=["pytest.ini"]),
        "ci_gating": CategoryResult(
            Tier.CONFIGURED, evidence=["ci.yml: runs poetry run pytest"]
        ),
    }
    _check_ci_tests_alignment(
        _FakeDetector(["poetry", "run", "pytest", "-q"]), _fp(tmp_path), categories
    )
    # 'pytest' is in the workflow, so should be aligned.
    assert not any("alignment" in e for e in categories["ci_gating"].evidence)
