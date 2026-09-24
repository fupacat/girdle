"""Plain pip/requirements.txt and Poetry, since both key off pyproject.toml
presence/absence and share test/lint/CI logic via python_common. uv, Conda,
and Pipenv are separate detectors that must run first and claim their own
markers (see registry.py ordering).
"""

from __future__ import annotations

from pathlib import Path

from girdle.detectors import python_common
from girdle.detectors._util import read_text, read_toml
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class PythonPipDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pyproject = root / "pyproject.toml"
        requirements = root / "requirements.txt"
        setup_py = root / "setup.py"
        data = read_toml(pyproject) if pyproject.exists() else None

        if data is not None and "poetry" in data.get("tool", {}):
            return Fingerprint(
                id="python-poetry", language="python", toolchain="poetry", root=root, variants=[]
            )
        # Yield to more specific toolchain detectors that share these markers.
        other_markers = ("uv.lock", "Pipfile", "environment.yml", "conda-lock.yml")
        if any((root / m).exists() for m in other_markers):
            return None
        if not requirements.exists() and not setup_py.exists() and data is None:
            return None
        return Fingerprint(
            id="python-pip", language="python", toolchain="pip", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": python_common.scan_tests(root),
            "lint": python_common.scan_lint(root),
            "coverage": python_common.scan_coverage(root),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": python_common.scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        prefix = ["poetry", "run"] if fp.toolchain == "poetry" else []
        commands = {"tests": [*prefix, *python_common.test_command()]}
        lint_cmd = python_common.lint_command(fp.root)
        if lint_cmd:
            commands["lint"] = [*prefix, *lint_cmd]
        commands["coverage"] = [*prefix, *python_common.coverage_command()]
        return commands

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        if fp.toolchain == "poetry":
            lock = root / "poetry.lock"
            if not lock.exists():
                return CategoryResult(
                    Tier.ABSENT, reason="no poetry.lock found",
                    recommendation="Run `poetry lock` and commit the generated poetry.lock.",
                )
            if python_common.is_lockfile_gitignored(root, "poetry.lock"):
                return CategoryResult(
                    Tier.ABSENT, reason="poetry.lock exists but is gitignored",
                    recommendation="Remove poetry.lock from .gitignore and commit it.",
                )
            return CategoryResult(Tier.CONFIGURED, evidence=["poetry.lock"])

        req = root / "requirements.txt"
        if not req.exists():
            pyproject = read_toml(root / "pyproject.toml")
            if pyproject and "dependencies" in pyproject.get("project", {}):
                return CategoryResult(
                    Tier.ABSENT,
                    evidence=["pyproject.toml#project.dependencies"],
                    reason=(
                        "PEP 621 dependencies are unpinned in pyproject.toml and no "
                        "lock mechanism (requirements.txt, uv.lock, pip-compile output) "
                        "was found"
                    ),
                    recommendation=(
                        "Pin dependencies: `pip install pip-tools && "
                        "pip-compile pyproject.toml -o requirements.txt`."
                    ),
                )
            return CategoryResult(
                Tier.ABSENT, reason="no requirements.txt found",
                recommendation=(
                    "Add a pinned requirements.txt: `pip install pip-tools && "
                    "pip-compile -o requirements.txt` (or `pip freeze > requirements.txt`)."
                ),
            )
        text = read_text(req) or ""
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        pinned = [ln for ln in lines if "==" in ln]
        if lines and len(pinned) == len(lines):
            return CategoryResult(
                Tier.CONFIGURED, evidence=["requirements.txt (all deps pinned with ==)"]
            )
        if lines:
            return CategoryResult(
                Tier.ABSENT,
                evidence=["requirements.txt"],
                reason=f"{len(lines) - len(pinned)}/{len(lines)} dependencies unpinned",
                recommendation=(
                    "Pin all versions with `==`, ideally regenerated via "
                    "`pip-compile -o requirements.txt`."
                ),
            )
        return CategoryResult(
            Tier.ABSENT, reason="requirements.txt is empty",
            recommendation="Populate requirements.txt with pinned dependencies.",
        )
