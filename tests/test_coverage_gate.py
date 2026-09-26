from pathlib import Path

from girdle.coverage_gate import detect_gate
from girdle.detectors.base import Fingerprint
from girdle.scan import _check_coverage_gate
from girdle.schema import CategoryResult, Tier


def _wf(root: Path, content: str) -> None:
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "ci.yml").write_text(content)


def test_no_ci_no_gate(tmp_path: Path):
    assert detect_gate(tmp_path) is None


def test_codecov_upload_without_config_file_not_confirmed(tmp_path: Path):
    _wf(tmp_path, "uses: codecov/codecov-action@v4\n")
    assert detect_gate(tmp_path) is None  # no codecov.yml present at all


def test_codecov_patch_gate_detected(tmp_path: Path):
    (tmp_path / "codecov.yml").write_text(
        "coverage:\n  status:\n    patch:\n      default:\n        target: 80%\n"
    )
    _wf(tmp_path, "uses: codecov/codecov-action@v4\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "patch" in gate.lower()


def test_codecov_config_without_patch_section(tmp_path: Path):
    (tmp_path / "codecov.yml").write_text("coverage:\n  precision: 2\n")
    _wf(tmp_path, "uses: codecov/codecov-action@v4\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "not confirmed" in gate


def test_coveralls_detected(tmp_path: Path):
    _wf(tmp_path, "uses: coverallsapp/github-action@v2\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "Coveralls" in gate


def test_diff_cover_with_fail_under(tmp_path: Path):
    _wf(tmp_path, "run: diff-cover coverage.xml --fail-under=90\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "90" in gate


def test_diff_cover_without_fail_under_flagged_as_not_enforcing(tmp_path: Path):
    _wf(tmp_path, "run: diff-cover coverage.xml\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "not actually enforcing" in gate


def test_sonar_without_config_file_not_detected(tmp_path: Path):
    _wf(tmp_path, "uses: SonarSource/sonarcloud-github-action@master\n")
    assert detect_gate(tmp_path) is None


def test_sonar_with_report_path_configured(tmp_path: Path):
    (tmp_path / "sonar-project.properties").write_text(
        "sonar.organization=x\nsonar.python.coverage.reportPaths=coverage.xml\n"
    )
    _wf(tmp_path, "uses: SonarSource/sonarcloud-github-action@master\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "coverage report configured" in gate


def test_sonar_without_report_path_flags_coverage_not_analyzed(tmp_path: Path):
    (tmp_path / "sonar-project.properties").write_text("sonar.organization=x\n")
    _wf(tmp_path, "uses: SonarSource/sonarcloud-github-action@master\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "no coverage report path configured" in gate


def test_sonarqube_scan_action_also_detected(tmp_path: Path):
    (tmp_path / ".sonarcloud.properties").write_text("sonar.coverageReportPaths=coverage.xml\n")
    _wf(tmp_path, "uses: SonarSource/sonarqube-scan-action@v4\n")
    gate = detect_gate(tmp_path)
    assert gate is not None
    assert "coverage report configured" in gate


# --- integration with scan._check_coverage_gate ---

def _fp(tmp_path: Path) -> Fingerprint:
    return Fingerprint(id="x", language="python", toolchain="pip", root=tmp_path, variants=[])


def test_gate_check_skipped_when_coverage_absent(tmp_path: Path):
    _wf(tmp_path, "uses: codecov/codecov-action@v4\n")
    (tmp_path / "codecov.yml").write_text("coverage:\n  status:\n    patch: {}\n")
    categories = {
        "coverage": CategoryResult(Tier.ABSENT),
        "ci_gating": CategoryResult(Tier.CONFIGURED),
    }
    _check_coverage_gate(_fp(tmp_path), categories)
    assert categories["coverage"].evidence == []
    assert categories["coverage"].recommendation is None


def test_gate_check_skipped_when_ci_absent(tmp_path: Path):
    categories = {
        "coverage": CategoryResult(Tier.CONFIGURED),
        "ci_gating": CategoryResult(Tier.ABSENT),
    }
    _check_coverage_gate(_fp(tmp_path), categories)
    assert categories["coverage"].evidence == []
    assert categories["coverage"].recommendation is None


def test_gate_check_adds_evidence_when_both_present_and_gate_found(tmp_path: Path):
    _wf(tmp_path, "uses: codecov/codecov-action@v4\n")
    (tmp_path / "codecov.yml").write_text("coverage:\n  status:\n    patch: {}\n")
    categories = {
        "coverage": CategoryResult(Tier.VERIFIED),
        "ci_gating": CategoryResult(Tier.CONFIGURED),
    }
    _check_coverage_gate(_fp(tmp_path), categories)
    assert any("PR-scoped gate" in e for e in categories["coverage"].evidence)


def test_gate_check_recommends_when_both_present_but_no_gate(tmp_path: Path):
    _wf(tmp_path, "run: pytest --cov\n")
    categories = {
        "coverage": CategoryResult(Tier.VERIFIED),
        "ci_gating": CategoryResult(Tier.CONFIGURED),
    }
    _check_coverage_gate(_fp(tmp_path), categories)
    assert categories["coverage"].recommendation is not None
    assert "PR-scoped gate" in categories["coverage"].recommendation


def test_gate_check_does_not_override_existing_recommendation(tmp_path: Path):
    categories = {
        "coverage": CategoryResult(Tier.CONFIGURED, recommendation="run --run to verify"),
        "ci_gating": CategoryResult(Tier.CONFIGURED),
    }
    _check_coverage_gate(_fp(tmp_path), categories)
    assert categories["coverage"].recommendation == "run --run to verify"
