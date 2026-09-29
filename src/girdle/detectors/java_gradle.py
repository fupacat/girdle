from __future__ import annotations

import os
from pathlib import Path

from girdle.detectors._util import read_text, scan_ci
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

BUILD_GRADLE_KTS = "build.gradle.kts"
BUILD_GRADLE = "build.gradle"


class JavaGradleDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        kotlin = root / BUILD_GRADLE_KTS
        groovy = root / BUILD_GRADLE
        if not kotlin.exists() and not groovy.exists():
            return None
        variants = ["kotlin-dsl"] if kotlin.exists() else []
        return Fingerprint(
            id="java-gradle", language="java", toolchain="gradle", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "build", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        build_file = BUILD_GRADLE_KTS if "kotlin-dsl" in fp.variants else BUILD_GRADLE
        build_text = read_text(root / build_file) or ""
        return {
            "tests": self._scan_tests(root, build_text),
            "lint": self._scan_lint(build_text),
            "coverage": self._scan_coverage(build_text),
            "build": self._scan_build(fp),
            "reproducibility": self._scan_reproducibility(root, build_text),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"
        wrapper_path = fp.root / wrapper_name
        exe = str(wrapper_path) if wrapper_path.exists() else "gradle"
        commands = {"tests": [exe, "test"], "build": [exe, "assemble"]}
        build_file = BUILD_GRADLE_KTS if "kotlin-dsl" in fp.variants else BUILD_GRADLE
        build_text = read_text(fp.root / build_file) or ""
        if "jacoco" in build_text.lower():
            commands["coverage"] = [exe, "test", "jacocoTestReport"]
        return commands

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

    def _scan_lint(self, build_text: str) -> CategoryResult:
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

    def _scan_coverage(self, build_text: str) -> CategoryResult:
        if "jacoco" not in build_text.lower():
            return CategoryResult(
                Tier.ABSENT, reason="no jacoco plugin found in build script",
                recommendation=(
                    "Apply the jacoco plugin (`id 'jacoco'`) and add a jacocoTestReport "
                    "task."
                ),
            )
        return CategoryResult(Tier.CONFIGURED, evidence=["build script: jacoco plugin"])

    def _scan_build(self, fp: Fingerprint) -> CategoryResult:
        build_file = BUILD_GRADLE_KTS if "kotlin-dsl" in fp.variants else BUILD_GRADLE
        return CategoryResult(Tier.CONFIGURED, evidence=[build_file])

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
        return scan_ci(root, r"gradlew?\b.*\btest\b", "./gradlew test")
