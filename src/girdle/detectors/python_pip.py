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

POETRY_LOCK = "poetry.lock"
REQUIREMENTS_TXT = "requirements.txt"


class PythonPipDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pyproject = root / "pyproject.toml"
        requirements = root / REQUIREMENTS_TXT
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
            lock = root / POETRY_LOCK
            if not lock.exists():
                return CategoryResult(
                    Tier.ABSENT, reason=f"no {POETRY_LOCK} found",
                    recommendation=f"Run `poetry lock` and commit the generated {POETRY_LOCK}.",
                )
            if python_common.is_lockfile_gitignored(root, POETRY_LOCK):
                return CategoryResult(
                    Tier.ABSENT, reason=f"{POETRY_LOCK} exists but is gitignored",
                    recommendation=f"Remove {POETRY_LOCK} from .gitignore and commit it.",
                )
            drift = _check_poetry_drift(root)
            if drift:
                missing = ", ".join(sorted(drift)[:5])
                return CategoryResult(
                    Tier.ABSENT,
                    evidence=[POETRY_LOCK],
                    reason=(
                        f"manifest/lockfile drift: {len(drift)} package(s) missing"
                        f" from lockfile: {missing}"
                    ),
                    recommendation=(
                        "Run `poetry lock` to regenerate the lockfile"
                        " from the current pyproject.toml."
                    ),
                )
            return CategoryResult(Tier.CONFIGURED, evidence=[POETRY_LOCK])

        req = root / REQUIREMENTS_TXT
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
                        f"pip-compile pyproject.toml -o {REQUIREMENTS_TXT}`."
                    ),
                )
            return CategoryResult(
                Tier.ABSENT, reason=f"no {REQUIREMENTS_TXT} found",
                recommendation=(
                    "Add a pinned requirements.txt: `pip install pip-tools && "
                    f"pip-compile -o {REQUIREMENTS_TXT}` (or `pip freeze > {REQUIREMENTS_TXT}`)."
                ),
            )
        text = read_text(req) or ""
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        pinned = [ln for ln in lines if "==" in ln]
        if lines and len(pinned) == len(lines):
            drift = _check_pip_drift(root, lines)
            if drift:
                missing = ", ".join(sorted(drift)[:5])
                return CategoryResult(
                    Tier.ABSENT,
                    evidence=[REQUIREMENTS_TXT],
                    reason=(
                        f"manifest/lockfile drift: {len(drift)} package(s) missing"
                        f" from requirements.txt: {missing}"
                    ),
                    recommendation=(
                        f"Run `pip-compile pyproject.toml -o {REQUIREMENTS_TXT}`"
                        " to regenerate the lockfile."
                    ),
                )
            return CategoryResult(
                Tier.CONFIGURED, evidence=[f"{REQUIREMENTS_TXT} (all deps pinned with ==)"]
            )
        if lines:
            return CategoryResult(
                Tier.ABSENT,
                evidence=[REQUIREMENTS_TXT],
                reason=f"{len(lines) - len(pinned)}/{len(lines)} dependencies unpinned",
                recommendation=(
                    "Pin all versions with `==`, ideally regenerated via "
                    f"`pip-compile -o {REQUIREMENTS_TXT}`."
                ),
            )
        return CategoryResult(
            Tier.ABSENT, reason=f"{REQUIREMENTS_TXT} is empty",
            recommendation=f"Populate {REQUIREMENTS_TXT} with pinned dependencies.",
        )


def _check_poetry_drift(root: Path) -> list[str]:
    """Return packages in [tool.poetry.dependencies] absent from poetry.lock."""
    import re

    pyproject = read_toml(root / "pyproject.toml")
    if not pyproject:
        return []
    declared = set((pyproject.get("tool", {}).get("poetry", {}).get("dependencies") or {}).keys())
    # "python" is a special constraint, not a real package
    declared.discard("python")
    if not declared:
        return []

    lock_text = read_text(root / POETRY_LOCK) or ""
    locked = set(re.findall(r'^name\s*=\s*"([^"]+)"', lock_text, re.MULTILINE))
    locked_normalized = {re.sub(r"[-_.]+", "-", n).lower() for n in locked}

    return [
        pkg for pkg in declared
        if re.sub(r"[-_.]+", "-", pkg).lower() not in locked_normalized
    ]


def _check_pip_drift(root: Path, req_lines: list[str]) -> list[str]:
    """Return packages in pyproject.toml [project.dependencies] absent from requirements.txt."""
    import re

    pyproject = read_toml(root / "pyproject.toml")
    if not pyproject:
        return []
    raw_deps = pyproject.get("project", {}).get("dependencies") or []
    if not raw_deps:
        return []

    # Extract bare package name from PEP 508 specifier (e.g. "requests>=2.0" -> "requests")
    def _name(spec: str) -> str:
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
        return re.sub(r"[-_.]+", "-", m.group(1)).lower() if m else ""

    declared = {_name(d) for d in raw_deps if d.strip()}
    if not declared:
        return []

    # Normalize names from requirements.txt lines (e.g. "requests==2.31.0" -> "requests")
    locked_normalized = {_name(ln) for ln in req_lines}

    return [pkg for pkg in declared if pkg not in locked_normalized]
