from __future__ import annotations

from pathlib import Path

from girdle.detectors import js_common
from girdle.detectors._util import read_json
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

PACKAGE_LOCK_JSON = "package-lock.json"


class JsNpmDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        pkg = root / "package.json"
        if not pkg.exists():
            return None
        # Only claim npm if no other lockfile signals a different toolchain.
        other_lockfiles = ("yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")
        if any((root / lf).exists() for lf in other_lockfiles):
            return None
        return Fingerprint(
            id="js-npm",
            language="javascript",
            toolchain="npm",
            root=root,
            variants=js_common.detect_variants(root),
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        categories = ["tests", "lint", "coverage", "reproducibility", "ci_gating"]
        pkg_data = read_json(fp.root / "package.json") or {}
        if js_common.has_build_script(pkg_data):
            categories.insert(3, "build")
        return categories

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pkg_data = read_json(root / "package.json") or {}
        return {
            "tests": js_common.scan_tests(pkg_data, "npm"),
            "lint": js_common.scan_lint(root, fp, "npm"),
            "coverage": js_common.scan_coverage(pkg_data, "npm"),
            **(
                {"build": js_common.scan_build(pkg_data)}
                if js_common.has_build_script(pkg_data) else {}
            ),
            "reproducibility": self._scan_reproducibility(root),
            "ci_gating": js_common.scan_ci(root, r"\bnpm (run )?(test|ci)\b", "npm test"),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return js_common.run_commands(fp.root, "npm")

    def _scan_reproducibility(self, root: Path) -> CategoryResult:
        lockfile = root / PACKAGE_LOCK_JSON
        if not lockfile.exists():
            return CategoryResult(
                Tier.ABSENT, reason=f"no {PACKAGE_LOCK_JSON} found",
                recommendation=f"Run `npm install` and commit the generated {PACKAGE_LOCK_JSON}.",
            )
        if js_common.is_lockfile_gitignored(root, PACKAGE_LOCK_JSON):
            return CategoryResult(
                Tier.ABSENT,
                reason=f"{PACKAGE_LOCK_JSON} exists but is gitignored (not committed)",
                recommendation=f"Remove {PACKAGE_LOCK_JSON} from .gitignore and commit it.",
            )
        drift = _check_lockfile_drift(root)
        if drift:
            missing = ", ".join(sorted(drift)[:5])
            return CategoryResult(
                Tier.ABSENT,
                evidence=[PACKAGE_LOCK_JSON],
                reason=(
                    f"manifest/lockfile drift: {len(drift)} package(s) missing"
                    f" from lockfile: {missing}"
                ),
                recommendation=(
                    "Run `npm install` to regenerate the lockfile"
                    " from the current package.json."
                ),
            )
        return CategoryResult(Tier.CONFIGURED, evidence=[PACKAGE_LOCK_JSON])


def _check_lockfile_drift(root: Path) -> list[str]:
    """Return package names declared in package.json but absent from package-lock.json."""
    pkg_data = read_json(root / "package.json") or {}
    lock_data = read_json(root / PACKAGE_LOCK_JSON)
    if lock_data is None:
        return []

    # Collect declared dependency names from the manifest.
    declared: set[str] = set()
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        declared.update((pkg_data.get(section) or {}).keys())

    if not declared:
        return []

    # Build the set of package names in the lockfile.
    # v2/v3 lockfiles use a "packages" section with keys like "node_modules/pkg"
    # or "node_modules/@scope/pkg" (and "" for the root entry).
    # v1 lockfiles use a "dependencies" section with bare package names.
    locked: set[str] = set()
    packages = lock_data.get("packages")
    if isinstance(packages, dict):
        for key in packages:
            if key == "":
                continue
            # Strip "node_modules/" prefix (handles nested: "node_modules/a/node_modules/b" -> "b")
            name = key.split("node_modules/")[-1]
            locked.add(name)
    dependencies = lock_data.get("dependencies")
    if isinstance(dependencies, dict):
        locked.update(dependencies.keys())

    return [pkg for pkg in declared if pkg not in locked]
