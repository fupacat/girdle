from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text, read_toml
from girdle.detectors.base import Fingerprint
from girdle.fsutil import rglob_excluding
from girdle.schema import CategoryResult, Tier


class RustDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        if not (root / "Cargo.toml").exists():
            return None
        data = read_toml(root / "Cargo.toml") or {}
        is_lib = "lib" in data or (root / "src" / "lib.rs").exists()
        variants = ["lib"] if is_lib else ["bin"]
        return Fingerprint(
            id="rust", language="rust", toolchain="cargo", root=root, variants=variants
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        cats = ["tests", "lint", "reproducibility", "ci_gating"]
        # A gitignored/absent Cargo.lock is correct practice for a library crate
        # (consumers resolve their own versions), so it's not a scoreable gap.
        if "lib" in fp.variants and not (fp.root / "Cargo.lock").exists():
            cats.remove("reproducibility")
        return cats

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        return {
            "tests": self._scan_tests(root),
            "lint": self._scan_lint(root),
            "reproducibility": self._scan_reproducibility(root, fp),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        return {
            "tests": ["cargo", "test"],
            "lint": ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
        }

    def _scan_tests(self, root: Path) -> CategoryResult:
        has_tests_dir = (root / "tests").is_dir()
        has_inline = any(
            "#[test]" in (read_text(f) or "") or "#[cfg(test)]" in (read_text(f) or "")
            for f in rglob_excluding(root, "*.rs")
        )
        if not has_tests_dir and not has_inline:
            return CategoryResult(Tier.ABSENT, reason="no tests/ dir or #[test]/#[cfg(test)] found")
        evidence = []
        if has_tests_dir:
            evidence.append("tests/ directory")
        if has_inline:
            evidence.append("#[test]/#[cfg(test)] in source")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, root: Path) -> CategoryResult:
        evidence = []
        if (root / "clippy.toml").exists() or (root / ".clippy.toml").exists():
            evidence.append("clippy.toml")
        if (root / "rustfmt.toml").exists() or (root / ".rustfmt.toml").exists():
            evidence.append("rustfmt.toml")
        cargo_data = read_toml(root / "Cargo.toml") or {}
        if "lints" in cargo_data:
            evidence.append("Cargo.toml#[lints]")
        if not evidence:
            return CategoryResult(Tier.ABSENT, reason="no clippy/rustfmt config or [lints] found")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_reproducibility(self, root: Path, fp: Fingerprint) -> CategoryResult:
        lock = root / "Cargo.lock"
        if not lock.exists():
            if "lib" in fp.variants:
                return CategoryResult(
                    Tier.ABSENT,
                    reason=(
                        "no Cargo.lock (expected/normal for a library crate, "
                        "excluded from scoring)"
                    ),
                )
            return CategoryResult(
                Tier.ABSENT, reason="no Cargo.lock found (required for a binary crate)"
            )
        return CategoryResult(Tier.CONFIGURED, evidence=["Cargo.lock"])

    def _scan_ci(self, root: Path) -> CategoryResult:
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                if re.search(r"\bcargo test\b", read_text(wf) or ""):
                    return CategoryResult(
                        Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs cargo test"]
                    )
        for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
            p = root / f
            if p.exists() and re.search(r"\bcargo test\b", read_text(p) or ""):
                return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs cargo test"])
        return CategoryResult(Tier.ABSENT, reason="no CI config found running cargo test")
