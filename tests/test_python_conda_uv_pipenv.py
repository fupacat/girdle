from pathlib import Path

from girdle.detectors.python_conda import PythonCondaDetector
from girdle.detectors.python_pipenv import PythonPipenvDetector
from girdle.detectors.python_uv import PythonUvDetector
from girdle.schema import Tier


def _write_common_present_markers(root: Path) -> None:
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "ruff.toml").write_text("line-length = 88\n", encoding="utf-8")
    (root / ".coveragerc").write_text("[run]\nbranch = true\n", encoding="utf-8")
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - run: pytest -q\n", encoding="utf-8"
    )


def _assert_common_category_tiers(result: dict, tier: Tier) -> None:
    for category in ("tests", "lint", "coverage", "ci_gating"):
        assert result[category].tier == tier


def test_conda_detect_none_without_environment_files(tmp_path: Path):
    assert PythonCondaDetector().detect(tmp_path) is None


def test_conda_detects_environment_yaml(tmp_path: Path):
    (tmp_path / "environment.yaml").write_text("name: demo\n", encoding="utf-8")
    assert PythonCondaDetector().detect(tmp_path) is not None


def test_conda_scan_categories_present(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "conda-lock.yml").write_text("# lock\n", encoding="utf-8")
    _write_common_present_markers(tmp_path)
    det = PythonCondaDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.CONFIGURED)
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_conda_scan_categories_absent(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("dependencies: [python=3.12]\n", encoding="utf-8")
    det = PythonCondaDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.ABSENT)
    assert result["reproducibility"].tier == Tier.ABSENT


def test_conda_run_commands_empty_without_environment_name(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("dependencies: [python=3.12]\n", encoding="utf-8")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    assert det.run_commands(fp) == {}


def test_conda_run_commands_from_environment_yaml_with_optional_lint(tmp_path: Path):
    (tmp_path / "environment.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "ruff.toml").write_text("line-length = 88\n", encoding="utf-8")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert commands["tests"] == ["conda", "run", "-n", "demo", "pytest", "-q"]
    assert commands["lint"] == ["conda", "run", "-n", "demo", "ruff", "check", "."]
    assert commands["coverage"] == ["conda", "run", "-n", "demo", "pytest", "--cov"]


def test_uv_detect_none_without_lock(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert PythonUvDetector().detect(tmp_path) is None


def test_uv_scan_categories_present(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("# lock\n", encoding="utf-8")
    _write_common_present_markers(tmp_path)
    det = PythonUvDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.CONFIGURED)
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_uv_scan_categories_absent(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("# lock\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("uv.lock\n", encoding="utf-8")
    det = PythonUvDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.ABSENT)
    assert result["reproducibility"].tier == Tier.ABSENT


def test_uv_run_commands_with_and_without_lint(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("# lock\n", encoding="utf-8")
    det = PythonUvDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert "lint" not in commands
    assert commands["tests"] == ["uv", "run", "pytest", "-q"]
    assert commands["coverage"] == ["uv", "run", "pytest", "--cov"]

    (tmp_path / "ruff.toml").write_text("line-length = 88\n", encoding="utf-8")
    commands_with_lint = det.run_commands(det.detect(tmp_path))
    assert commands_with_lint["lint"] == ["uv", "run", "ruff", "check", "."]


def test_pipenv_detect_none_without_pipfile(tmp_path: Path):
    assert PythonPipenvDetector().detect(tmp_path) is None


def test_pipenv_scan_categories_present(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("[packages]\n", encoding="utf-8")
    (tmp_path / "Pipfile.lock").write_text("{}", encoding="utf-8")
    _write_common_present_markers(tmp_path)
    det = PythonPipenvDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.CONFIGURED)
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_pipenv_scan_categories_absent(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("[packages]\n", encoding="utf-8")
    det = PythonPipenvDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    _assert_common_category_tiers(result, Tier.ABSENT)
    assert result["reproducibility"].tier == Tier.ABSENT


def test_pipenv_reproducibility_absent_when_lock_gitignored(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("[packages]\n", encoding="utf-8")
    (tmp_path / "Pipfile.lock").write_text("{}", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("Pipfile.lock\n", encoding="utf-8")
    det = PythonPipenvDetector()
    result = det.scan(det.detect(tmp_path), mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_pipenv_run_commands_with_and_without_lint(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("[packages]\n", encoding="utf-8")
    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert "lint" not in commands
    assert commands["tests"] == ["pipenv", "run", "pytest", "-q"]
    assert commands["coverage"] == ["pipenv", "run", "pytest", "--cov"]

    (tmp_path / "ruff.toml").write_text("line-length = 88\n", encoding="utf-8")
    commands_with_lint = det.run_commands(det.detect(tmp_path))
    assert commands_with_lint["lint"] == ["pipenv", "run", "ruff", "check", "."]
