from pathlib import Path

from girdle.detectors.python_conda import PythonCondaDetector
from girdle.detectors.python_pipenv import PythonPipenvDetector
from girdle.detectors.python_uv import PythonUvDetector
from girdle.schema import Tier


def _write_configured_common_categories(root: Path) -> None:
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "ruff.toml").write_text("line-length = 88\n", encoding="utf-8")
    (root / ".coveragerc").write_text("[run]\nbranch = true\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: pytest -q\n",
        encoding="utf-8",
    )


def test_python_conda_categories_present_and_absent(tmp_path: Path):
    det = PythonCondaDetector()

    (tmp_path / "environment.yml").write_text("name: demo\n", encoding="utf-8")
    fp = det.detect(tmp_path)
    assert fp is not None
    absent = det.scan(fp, mode="static")
    assert absent["tests"].tier == Tier.ABSENT
    assert absent["lint"].tier == Tier.ABSENT
    assert absent["coverage"].tier == Tier.ABSENT
    assert absent["ci_gating"].tier == Tier.ABSENT
    assert absent["reproducibility"].tier == Tier.ABSENT
    assert det.run_commands(fp)["tests"] == ["conda", "run", "-n", "demo", "pytest", "-q"]

    _write_configured_common_categories(tmp_path)
    (tmp_path / "conda-lock.yml").write_text("lock\n", encoding="utf-8")
    configured = det.scan(fp, mode="static")
    assert configured["tests"].tier == Tier.CONFIGURED
    assert configured["lint"].tier == Tier.CONFIGURED
    assert configured["coverage"].tier == Tier.CONFIGURED
    assert configured["ci_gating"].tier == Tier.CONFIGURED
    assert configured["reproducibility"].tier == Tier.CONFIGURED


def test_python_conda_detect_none_without_environment_file(tmp_path: Path):
    assert PythonCondaDetector().detect(tmp_path) is None


def test_python_conda_environment_yaml_and_missing_name_branches(tmp_path: Path):
    det = PythonCondaDetector()
    (tmp_path / "environment.yaml").write_text("channels:\n  - conda-forge\n", encoding="utf-8")
    fp = det.detect(tmp_path)
    assert fp is not None
    assert det.run_commands(fp) == {}


def test_python_uv_detect_none_without_required_files(tmp_path: Path):
    det = PythonUvDetector()
    assert det.detect(tmp_path) is None
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert det.detect(tmp_path) is None


def test_python_uv_categories_present_and_absent(tmp_path: Path):
    det = PythonUvDetector()

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    fp = det.detect(tmp_path)
    assert fp is not None
    absent = det.scan(fp, mode="static")
    assert absent["tests"].tier == Tier.ABSENT
    assert absent["lint"].tier == Tier.ABSENT
    assert absent["coverage"].tier == Tier.ABSENT
    assert absent["ci_gating"].tier == Tier.ABSENT
    assert absent["reproducibility"].tier == Tier.CONFIGURED

    (tmp_path / ".gitignore").write_text("uv.lock\n", encoding="utf-8")
    ignored = det.scan(fp, mode="static")
    assert ignored["reproducibility"].tier == Tier.ABSENT

    (tmp_path / ".gitignore").write_text("", encoding="utf-8")
    _write_configured_common_categories(tmp_path)
    configured = det.scan(fp, mode="static")
    assert configured["tests"].tier == Tier.CONFIGURED
    assert configured["lint"].tier == Tier.CONFIGURED
    assert configured["coverage"].tier == Tier.CONFIGURED
    assert configured["ci_gating"].tier == Tier.CONFIGURED
    assert configured["reproducibility"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["tests"] == ["uv", "run", "pytest", "-q"]
    assert det.run_commands(fp)["lint"] == ["uv", "run", "ruff", "check", "."]


def test_python_pipenv_categories_present_and_absent(tmp_path: Path):
    det = PythonPipenvDetector()

    (tmp_path / "Pipfile").write_text("[packages]\n", encoding="utf-8")
    fp = det.detect(tmp_path)
    assert fp is not None
    absent = det.scan(fp, mode="static")
    assert absent["tests"].tier == Tier.ABSENT
    assert absent["lint"].tier == Tier.ABSENT
    assert absent["coverage"].tier == Tier.ABSENT
    assert absent["ci_gating"].tier == Tier.ABSENT
    assert absent["reproducibility"].tier == Tier.ABSENT

    (tmp_path / "Pipfile.lock").write_text("{}", encoding="utf-8")
    _write_configured_common_categories(tmp_path)
    configured = det.scan(fp, mode="static")
    assert configured["tests"].tier == Tier.CONFIGURED
    assert configured["lint"].tier == Tier.CONFIGURED
    assert configured["coverage"].tier == Tier.CONFIGURED
    assert configured["ci_gating"].tier == Tier.CONFIGURED
    assert configured["reproducibility"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["tests"] == ["pipenv", "run", "pytest", "-q"]
    assert det.run_commands(fp)["lint"] == ["pipenv", "run", "ruff", "check", "."]


def test_python_pipenv_detect_none_without_pipfile(tmp_path: Path):
    assert PythonPipenvDetector().detect(tmp_path) is None
