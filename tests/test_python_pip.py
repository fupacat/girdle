from pathlib import Path

from girdle.detectors.python_pip import PythonPipDetector
from girdle.schema import Tier


def test_detect_none_without_markers(tmp_path: Path):
    assert PythonPipDetector().detect(tmp_path) is None


def test_detect_poetry(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    fp = PythonPipDetector().detect(tmp_path)
    assert fp is not None
    assert fp.toolchain == "poetry"


def test_pinned_requirements_configured(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\nclick==8.1.7\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_unpinned_requirements_absent(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests\nclick\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_pep621_unpinned_gets_specific_reason(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'x'\ndependencies = ['click>=8.1']\n"
    )
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "PEP 621" in result["reproducibility"].reason


def test_poetry_lock_gitignored(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    (tmp_path / "poetry.lock").write_text("")
    (tmp_path / ".gitignore").write_text("poetry.lock\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_poetry_drift_missing_package(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry]\nname = 'x'\n"
        "[tool.poetry.dependencies]\n"
        "python = '^3.11'\nrequests = '^2.31'\nclick = '^8.0'\n"
    )
    # poetry.lock only contains requests, not click
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
    )
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "click" in result["reproducibility"].reason
    assert "drift" in result["reproducibility"].reason


def test_poetry_no_drift(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry]\nname = 'x'\n"
        "[tool.poetry.dependencies]\n"
        "python = '^3.11'\nrequests = '^2.31'\n"
    )
    (tmp_path / "poetry.lock").write_text(
        '[[package]]\nname = "requests"\nversion = "2.31.0"\n'
    )
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_pip_drift_pyproject_dep_missing_from_requirements(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'x'\ndependencies = ['requests>=2.0', 'click>=8.0']\n"
    )
    # requirements.txt only has requests, not click
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "click" in result["reproducibility"].reason
    assert "drift" in result["reproducibility"].reason


def test_pip_no_drift_all_deps_in_requirements(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'x'\ndependencies = ['requests>=2.0']\n"
    )
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED
