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


def test_poetry_lock_gitignored(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    (tmp_path / "poetry.lock").write_text("")
    (tmp_path / ".gitignore").write_text("poetry.lock\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
