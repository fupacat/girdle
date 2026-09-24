"""Maven has no native lockfile concept, so reproducibility is scored on
version-pinning (exact versions) vs. ranges ([1.0,2.0), LATEST, +), not on
lockfile presence the way npm/Poetry/etc. are.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text
from girdle.detectors.base import Fingerprint
from girdle.schema import CategoryResult, Tier

LINT_PLUGINS = ("maven-checkstyle-plugin", "spotbugs-maven-plugin", "maven-pmd-plugin")
RANGE_PATTERN = re.compile(
    r"<version>\s*[\[(][^<]*[\])]\s*</version>|<version>\s*LATEST\s*</version>"
)


class JavaMavenDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "pom.xml").exists():
            return None
        return Fingerprint(
            id="java-maven", language="java", toolchain="maven", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        pom_text = read_text(root / "pom.xml") or ""
        return {
            "tests": self._scan_tests(root, pom_text),
            "lint": self._scan_lint(pom_text),
            "reproducibility": self._scan_reproducibility(pom_text),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        # Lint execution skipped: checkstyle/spotbugs/pmd goal names vary by
        # plugin config and aren't safe to guess.
        return {"tests": ["mvn", "test"]}

    def _scan_tests(self, root: Path, pom_text: str) -> CategoryResult:
        has_test_dir = (root / "src" / "test" / "java").is_dir()
        has_junit = "junit" in pom_text.lower() or "testng" in pom_text.lower()
        if not has_test_dir and not has_junit:
            return CategoryResult(
                Tier.ABSENT, reason="no src/test/java or junit/testng dependency found",
                recommendation=(
                    "Add the junit dependency to pom.xml and create tests under "
                    "src/test/java."
                ),
            )
        evidence = []
        if has_test_dir:
            evidence.append("src/test/java")
        if has_junit:
            evidence.append("junit/testng dependency in pom.xml")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, pom_text: str) -> CategoryResult:
        found = [p for p in LINT_PLUGINS if p in pom_text]
        if not found:
            return CategoryResult(
                Tier.ABSENT, reason="no checkstyle/spotbugs/pmd plugin found in pom.xml",
                recommendation="Add the maven-checkstyle-plugin (or spotbugs/pmd) to pom.xml.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=[f"pom.xml plugin: {p}" for p in found])

    def _scan_reproducibility(self, pom_text: str) -> CategoryResult:
        ranges = RANGE_PATTERN.findall(pom_text)
        if ranges:
            return CategoryResult(
                Tier.ABSENT,
                reason=(
                    f"{len(ranges)} dependency version range(s) found "
                    "(Maven has no native lockfile)"
                ),
                recommendation=(
                    "Replace version ranges with exact pinned <version> elements in "
                    "pom.xml."
                ),
            )
        if "<version>" not in pom_text:
            return CategoryResult(
                Tier.ABSENT, reason="no dependency versions found to evaluate",
                recommendation="Add explicit <version> elements to your <dependency> entries.",
            )
        return CategoryResult(
            Tier.CONFIGURED, evidence=["all dependency versions appear exact-pinned (no ranges)"]
        )

    def _scan_ci(self, root: Path) -> CategoryResult:
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                if re.search(r"\bmvn\b.*\btest\b", read_text(wf) or ""):
                    return CategoryResult(
                        Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs mvn test"]
                    )
        for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
            p = root / f
            if p.exists() and re.search(r"\bmvn\b.*\btest\b", read_text(p) or ""):
                return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs mvn test"])
        return CategoryResult(
            Tier.ABSENT, reason="no CI config found running mvn test",
            recommendation=(
                "Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs "
                "`mvn test`."
            ),
        )
