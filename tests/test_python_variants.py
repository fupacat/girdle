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


def test_conda_categories_present(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: env\n")
    (tmp_path / "conda-lock.yml").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    (tmp_path / ".coveragerc").write_text("[run]\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("run: pytest -q\n")

    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.CONFIGURED
    assert result["lint"].tier == Tier.CONFIGURED
    assert result["coverage"].tier == Tier.CONFIGURED
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["ci_gating"].tier == Tier.CONFIGURED


def test_conda_categories_absent(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("name: env\n")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.ABSENT
    assert result["lint"].tier == Tier.ABSENT
    assert result["coverage"].tier == Tier.ABSENT
    assert result["reproducibility"].tier == Tier.ABSENT
    assert result["ci_gating"].tier == Tier.ABSENT


def test_conda_run_commands_uses_environment_yaml_and_lint(tmp_path: Path):
    (tmp_path / "environment.yaml").write_text("name: env2\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)

    assert commands["tests"] == ["conda", "run", "-n", "env2", "pytest", "-q"]
    assert commands["lint"] == ["conda", "run", "-n", "env2", "ruff", "check", "."]
    assert commands["coverage"] == ["conda", "run", "-n", "env2", "pytest", "--cov"]


def test_conda_run_commands_empty_without_env_name(tmp_path: Path):
    (tmp_path / "environment.yml").write_text("channels:\n  - conda-forge\n")
    det = PythonCondaDetector()
    fp = det.detect(tmp_path)
    assert det.run_commands(fp) == {}


def test_uv_categories_present(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / ".coveragerc").write_text("[run]\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("run: python -m pytest -q\n")

    det = PythonUvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.CONFIGURED
    assert result["lint"].tier == Tier.CONFIGURED
    assert result["coverage"].tier == Tier.CONFIGURED
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["ci_gating"].tier == Tier.CONFIGURED


def test_uv_categories_absent_when_lock_gitignored(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / ".gitignore").write_text("uv.lock\n")

    det = PythonUvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.ABSENT
    assert result["lint"].tier == Tier.ABSENT
    assert result["coverage"].tier == Tier.ABSENT
    assert result["reproducibility"].tier == Tier.ABSENT
    assert result["ci_gating"].tier == Tier.ABSENT


def test_uv_run_commands_with_and_without_lint(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "uv.lock").write_text("")
    det = PythonUvDetector()
    fp = det.detect(tmp_path)

    no_lint = det.run_commands(fp)
    assert "lint" not in no_lint
    assert no_lint["tests"] == ["uv", "run", "pytest", "-q"]
    assert no_lint["coverage"] == ["uv", "run", "pytest", "--cov"]

    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    with_lint = det.run_commands(fp)
    assert with_lint["lint"] == ["uv", "run", "ruff", "check", "."]


def test_pipenv_categories_present(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    (tmp_path / "Pipfile.lock").write_text("{}")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    (tmp_path / ".coveragerc").write_text("[run]\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("run: pytest -q\n")

    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.CONFIGURED
    assert result["lint"].tier == Tier.CONFIGURED
    assert result["coverage"].tier == Tier.CONFIGURED
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["ci_gating"].tier == Tier.CONFIGURED


def test_pipenv_categories_absent(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.ABSENT
    assert result["lint"].tier == Tier.ABSENT
    assert result["coverage"].tier == Tier.ABSENT
    assert result["reproducibility"].tier == Tier.ABSENT
    assert result["ci_gating"].tier == Tier.ABSENT


def test_pipenv_run_commands_with_and_without_lint(tmp_path: Path):
    (tmp_path / "Pipfile").write_text("")
    det = PythonPipenvDetector()
    fp = det.detect(tmp_path)

    no_lint = det.run_commands(fp)
    assert "lint" not in no_lint
    assert no_lint["tests"] == ["pipenv", "run", "pytest", "-q"]
    assert no_lint["coverage"] == ["pipenv", "run", "pytest", "--cov"]

    (tmp_path / "ruff.toml").write_text("line-length = 88\n")
    with_lint = det.run_commands(fp)
    assert with_lint["lint"] == ["pipenv", "run", "ruff", "check", "."]
