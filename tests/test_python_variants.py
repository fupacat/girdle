from pathlib import Path

import pytest

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


def _write_common_category_markers(root: Path, *, with_lint: bool = True) -> None:
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    if with_lint:
        (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    (root / ".coveragerc").write_text("[run]\n")
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("run: pytest -q\n")


@pytest.mark.parametrize(
    ("detector", "setup_present", "setup_absent"),
    [
        (
            PythonCondaDetector,
            lambda p: (
                (p / "environment.yml").write_text("name: env\n"),
                (p / "conda-lock.yml").write_text(""),
            ),
            lambda p: (p / "environment.yml").write_text("name: env\n"),
        ),
        (
            PythonUvDetector,
            lambda p: (
                (p / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n"),
                (p / "uv.lock").write_text(""),
            ),
            lambda p: (
                (p / "pyproject.toml").write_text("[project]\nname = 'x'\n"),
                (p / "uv.lock").write_text(""),
                (p / ".gitignore").write_text("uv.lock\n"),
            ),
        ),
        (
            PythonPipenvDetector,
            lambda p: ((p / "Pipfile").write_text(""), (p / "Pipfile.lock").write_text("{}")),
            lambda p: (p / "Pipfile").write_text(""),
        ),
    ],
)
def test_python_variant_categories_present_and_absent(
    tmp_path: Path, detector, setup_present, setup_absent
):
    present = tmp_path / "present"
    present.mkdir()
    setup_present(present)
    _write_common_category_markers(present)
    det = detector()
    fp = det.detect(present)
    configured = det.scan(fp, mode="static")
    assert all(configured[key].tier == Tier.CONFIGURED for key in configured)

    absent = tmp_path / "absent"
    absent.mkdir()
    setup_absent(absent)
    det2 = detector()
    fp2 = det2.detect(absent)
    missing = det2.scan(fp2, mode="static")
    assert all(missing[key].tier == Tier.ABSENT for key in missing)


@pytest.mark.parametrize(
    (
        "detector",
        "marker_file",
        "marker_text",
        "expected_tests",
        "expected_lint",
        "expected_coverage",
    ),
    [
        (
            PythonCondaDetector,
            "environment.yaml",
            "name: env2\n",
            ["conda", "run", "-n", "env2", "pytest", "-q"],
            ["conda", "run", "-n", "env2", "ruff", "check", "."],
            ["conda", "run", "-n", "env2", "pytest", "--cov"],
        ),
        (
            PythonUvDetector,
            "pyproject.toml",
            "[tool.ruff]\nline-length = 88\n",
            ["uv", "run", "pytest", "-q"],
            ["uv", "run", "ruff", "check", "."],
            ["uv", "run", "pytest", "--cov"],
        ),
        (
            PythonPipenvDetector,
            "ruff.toml",
            "line-length = 88\n",
            ["pipenv", "run", "pytest", "-q"],
            ["pipenv", "run", "ruff", "check", "."],
            ["pipenv", "run", "pytest", "--cov"],
        ),
    ],
)
def test_python_variant_run_commands_include_expected_lint(
    tmp_path: Path,
    detector,
    marker_file: str,
    marker_text: str,
    expected_tests: list[str],
    expected_lint: list[str],
    expected_coverage: list[str],
):
    det = detector()
    if detector is PythonCondaDetector:
        (tmp_path / "environment.yaml").write_text("name: env2\n")
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    elif detector is PythonUvDetector:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (tmp_path / "uv.lock").write_text("")
        (tmp_path / marker_file).write_text(marker_text)
    else:
        (tmp_path / "Pipfile").write_text("")
        (tmp_path / marker_file).write_text(marker_text)

    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert commands["tests"] == expected_tests
    assert commands["lint"] == expected_lint
    assert commands["coverage"] == expected_coverage


def test_conda_run_commands_empty_without_env_name(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("channels:\n  - conda-forge\n")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    assert det.run_commands(fp) == {}
