from pathlib import Path

from girdle.detectors._util import scan_static_analysis
from girdle.scan import run_scan
from girdle.tiers import Tier


def _wf(root: Path, text: str, name: str = "ci.yml"):
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / name).write_text(text)


def test_static_analysis_absent_by_default(tmp_path: Path):
    cat = scan_static_analysis(tmp_path)
    assert cat.tier == Tier.ABSENT
    assert "CodeQL" in cat.recommendation


def test_codeql_workflow_detected(tmp_path: Path):
    _wf(tmp_path, "jobs:\n  analyze:\n    steps:\n      - uses: github/codeql-action/init@v4\n")

    cat = scan_static_analysis(tmp_path)

    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence == [".github/workflows/ci.yml: uses github/codeql-action"]


def test_semgrep_config_detected(tmp_path: Path):
    (tmp_path / ".semgrep.yml").write_text("rules: []\n")

    cat = scan_static_analysis(tmp_path)

    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence == [".semgrep.yml"]


def test_sonar_scan_with_config_detected(tmp_path: Path):
    (tmp_path / "sonar-project.properties").write_text("sonar.projectKey=demo\n")
    _wf(tmp_path, "steps:\n  - uses: SonarSource/sonarqube-scan-action@v4\n")

    cat = scan_static_analysis(tmp_path)

    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence == [
        "sonar-project.properties + .github/workflows/ci.yml: runs SonarQube/SonarCloud"
    ]


def test_run_scan_surfaces_static_analysis_category(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("pytest==8.0.0\n")
    _wf(tmp_path, "jobs:\n  analyze:\n    steps:\n      - uses: github/codeql-action/analyze@v4\n")

    result = run_scan(tmp_path)

    eco = result.ecosystems[0]
    assert "static_analysis" in eco.applicable_categories
    assert eco.categories["static_analysis"].tier == Tier.CONFIGURED
