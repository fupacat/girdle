from pathlib import Path

from girdle.detectors.python_conda import PythonCondaDetector
from girdle.detectors.python_pip import PythonPipDetector
from girdle.detectors.python_pipenv import PythonPipenvDetector
from girdle.detectors.python_uv import PythonUvDetector
from girdle.schema import Tier


def test_pip_yields_to_uv(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "uv.lock").write_text("")
    assert PythonPipDetector().detect(tmp_path) is None
    assert PythonUvDetector().detect(tmp_path) is not None


def test_pip_yields_to_pipenv(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    assert PythonPipDetector().detect(tmp_path) is None
    assert PythonPipenvDetector().detect(tmp_path) is not None


def test_pip_yields_to_conda(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: x\n")
    assert PythonPipDetector().detect(tmp_path) is None
    assert PythonCondaDetector().detect(tmp_path) is not None


def test_uv_lock_configured(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "uv.lock").write_text("")
    det = PythonUvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_conda_env_without_lock_is_absent(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: x\ndependencies: [python=3.12]\n")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_conda_with_lock_is_configured(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: x\n")
    (tmp_path / "conda-lock.yml").write_text("")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_pipenv_without_lock_is_absent(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_pipenv_with_lock_is_configured(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    (tmp_path / "Pipfile.lock").write_text("{}")
    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED
