from __future__ import annotations

import os
import re
from pathlib import Path

from girdle.detectors._util import read_text
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier


class JavaGradleDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        kotlin = root / "build.gradle.kts"
        groovy = root / "build.gradle"
        if not kotlin.exists() and not groovy.exists():
            return None
        variants = ["kotlin-dsl"] if kotlin.exists() else []
        return Fingerprint(
            id="java-gradle", language="java", toolchain="gradle", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        build_file = "build.gradle.kts" if "kotlin-dsl" in fp.variants else "build.gradle"
        build_text = read_text(root / build_file) or ""
        return {
            "tests": self._scan_tests(root, build_text),
            "lint": self._scan_lint(root, build_text),
            "reproducibility": self._scan_reproducibility(root, build_text),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"
        wrapper_path = fp.root / wrapper_name
        exe = str(wrapper_path) if wrapper_path.exists() else "gradle"
        return {"tests": [exe, "test"]}

    def _scan_tests(self, root: Path, build_text: str) -> CategoryResult:
        has_test_dir = (root / "src" / "test").is_dir()
        has_junit = "junit" in build_text.lower() or "testng" in build_text.lower()
        if not has_test_dir and not has_junit:
            return CategoryResult(
                Tier.ABSENT, reason="no src/test or junit/testng dependency found",
                recommendation="Add the junit dependency and create tests under src/test.",
            )
        evidence = []
        if has_test_dir:
            evidence.append("src/test")
        if has_junit:
            evidence.append("junit/testng dependency in build script")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, root: Path, build_text: str) -> CategoryResult:
        evidence = []
        if "checkstyle" in build_text.lower():
            evidence.append("checkstyle plugin")
        if "spotless" in build_text.lower():
            evidence.append("spotless plugin")
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no checkstyle/spotless plugin found",
                recommendation="Add the checkstyle or spotless Gradle plugin to your build script.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_reproducibility(self, root: Path, build_text: str) -> CategoryResult:
        lockfile = root / "gradle.lockfile"
        catalog = root / "gradle" / "libs.versions.toml"
        if lockfile.exists():
            return CategoryResult(Tier.CONFIGURED, evidence=["gradle.lockfile"])
        if catalog.exists():
            return CategoryResult(
                Tier.CONFIGURED, evidence=["gradle/libs.versions.toml (version catalog)"]
            )
        if "dependencyLocking" in build_text:
            return CategoryResult(
                Tier.CONFIGURED, evidence=["build script: dependencyLocking enabled"]
            )
        return CategoryResult(
            Tier.ABSENT,
            reason="no gradle.lockfile, version catalog, or dependencyLocking found",
            recommendation=(
                "Enable dependency locking (`dependencyLocking { lockAllConfigurations() }` "
                "then `./gradlew dependencies --write-locks`), or adopt a version catalog "
                "(gradle/libs.versions.toml)."
            ),
        )

    def _scan_ci(self, root: Path) -> CategoryResult:
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                text = read_text(wf) or ""
                if re.search(r"gradlew?\s+.*test\b", text) or re.search(r"\bgradle test\b", text):
                    return CategoryResult(
                        Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs gradle test"]
                    )
        for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
            p = root / f
            text = read_text(p) or ""
            if p.exists() and re.search(r"gradlew?\s+.*test\b", text):
                return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs gradle test"])
        return CategoryResult(
            Tier.ABSENT, reason="no CI config found running gradle test",
            recommendation=(
                "Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs "
                "`./gradlew test`."
            ),
        )
