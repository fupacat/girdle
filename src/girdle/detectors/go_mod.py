from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text, scan_ci
from girdle.detectors.base import Fingerprint
from girdle.fsutil import rglob_excluding
from girdle.schema import CategoryResult, Tier


class GoModDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "go.mod").exists():
            return None
        variants = ["workspace"] if (root / "go.work").exists() else []
        return Fingerprint(
            id="go", language="go", toolchain="go-modules", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "build", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": self._scan_tests(root),
            "lint": self._scan_lint(root),
            "coverage": self._scan_coverage(root),
            "build": self._scan_build(root),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        commands = {
            "tests": ["go", "test", "./..."],
            "coverage": ["go", "test", "-cover", "./..."],
            "build": ["go", "build", "./..."],
        }
        if (fp.root / ".golangci.yml").exists() or (fp.root / ".golangci.yaml").exists():
            commands["lint"] = ["golangci-lint", "run"]
        return commands

    def _scan_tests(self, root: Path) -> CategoryResult:
        test_files = list(rglob_excluding(root, "*_test.go"))
        if not test_files:
            return CategoryResult(
                Tier.ABSENT, reason="no *_test.go files found",
                recommendation="Add *_test.go files using the standard `testing` package.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=[f"{len(test_files)} *_test.go file(s)"])

    def _scan_lint(self, root: Path) -> CategoryResult:
        evidence = []
        for marker in (".golangci.yml", ".golangci.yaml", "staticcheck.conf"):
            if (root / marker).exists():
                evidence.append(marker)
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no golangci-lint/staticcheck config found",
                recommendation="Add a .golangci.yml and run `golangci-lint run`.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_coverage(self, root: Path) -> CategoryResult:
        evidence = []
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                if re.search(r"-cover(profile)?\b", read_text(wf) or ""):
                    evidence.append(f".github/workflows/{wf.name}: runs with -cover")
                    break
        makefile = root / "Makefile"
        if not evidence and makefile.exists():
            if re.search(r"-cover(profile)?\b", read_text(makefile) or ""):
                evidence.append("Makefile: runs with -cover")
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no evidence of `go test -cover` in CI or Makefile",
                recommendation=(
                    "Add `go test -cover ./...` to CI (or a Makefile target) to track "
                    "coverage."
                ),
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_build(self, root: Path) -> CategoryResult:
        return CategoryResult(Tier.CONFIGURED, evidence=["go.mod (build via `go build ./...`)"])

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        sum_files = [root / "go.sum"]
        if "workspace" in fp.variants:
            sum_files.append(root / "go.work.sum")
        present = [str(f.name) for f in sum_files if f.exists()]
        if not present:
            return CategoryResult(
                Tier.ABSENT, reason="no go.sum found (unusual for a healthy Go repo)",
                recommendation="Run `go mod tidy` to generate go.sum and commit it.",
            )
        return CategoryResult(Tier.CONFIGURED, evidence=present)

    def _scan_ci(self, root: Path) -> CategoryResult:
        return scan_ci(root, r"\bgo test\b", "go test ./...")
