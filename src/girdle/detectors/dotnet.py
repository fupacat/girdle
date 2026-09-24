"""packages.lock.json is opt-in (RestorePackagesWithLockFile) and absent by
default even in healthy .NET repos, so its absence must not be penalized as
hard as a missing npm/Poetry lockfile - it's scored CONFIGURED-adjacent via
exact-version PackageReferences instead, with the lockfile as a bonus signal
folded into the same evidence rather than a separate required check.
"""

from __future__ import annotations

import re
from pathlib import Path

from girdle.detectors._util import read_text
from girdle.detectors.base import Fingerprint
from girdle.fsutil import rglob_excluding
from girdle.schema import CategoryResult, Tier

VERSION_RANGE_PATTERN = re.compile(r'Version="[^"]*[\*\[\(].*?"|Version="\d+\.\*"')
PACKAGE_REF_PATTERN = re.compile(r'<PackageReference\b')
PINNED_VERSION_PATTERN = re.compile(r'Version="\d+(\.\d+){1,3}"')


class DotNetDetector:
    def detect(self, root: Path) -> Fingerprint | None:
        project_files = list(root.glob("*.csproj")) + list(root.glob("*.fsproj"))
        sln_files = list(root.glob("*.sln"))
        if not project_files and not sln_files:
            return None
        return Fingerprint(
            id="dotnet", language="dotnet", toolchain="nuget", root=root, variants=[]
        )

    def applicable_categories(self, fp: Fingerprint) -> list[str]:
        return ["tests", "lint", "coverage", "reproducibility", "ci_gating"]

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]:
        root = fp.root
        project_texts = [read_text(p) or "" for p in rglob_excluding(root, "*.csproj", "*.fsproj")]
        combined = "\n".join(project_texts)
        return {
            "tests": self._scan_tests(root, combined),
            "lint": self._scan_lint(root),
            "coverage": self._scan_coverage(root, combined),
            "reproducibility": self._scan_reproducibility(root, combined),
            "ci_gating": self._scan_ci(root),
        }

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        # Analyzers run as part of the build, not a separate lint invocation;
        # no standalone lint command to declare here.
        commands = {"tests": ["dotnet", "test"]}
        project_texts = [
            read_text(p) or "" for p in rglob_excluding(fp.root, "*.csproj", "*.fsproj")
        ]
        if "coverlet" in "\n".join(project_texts).lower():
            commands["coverage"] = ["dotnet", "test", "--collect:XPlat Code Coverage"]
        return commands

    def _scan_tests(self, root: Path, combined: str) -> CategoryResult:
        has_test_sdk = "Microsoft.NET.Test.Sdk" in combined
        has_test_proj = any(rglob_excluding(root, "*.Tests.csproj", "*Tests.csproj"))
        if not has_test_sdk and not has_test_proj:
            return CategoryResult(
                Tier.ABSENT, reason="no Microsoft.NET.Test.Sdk reference or *.Tests.csproj found",
                recommendation=(
                    "Add a *.Tests.csproj project referencing Microsoft.NET.Test.Sdk."
                ),
            )
        evidence = []
        if has_test_sdk:
            evidence.append("Microsoft.NET.Test.Sdk reference")
        if has_test_proj:
            evidence.append("*.Tests.csproj naming convention")
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_lint(self, root: Path) -> CategoryResult:
        evidence = []
        if (root / ".editorconfig").exists():
            evidence.append(".editorconfig")
        props = root / "Directory.Build.props"
        if props.exists() and "EnableNETAnalyzers" in (read_text(props) or ""):
            evidence.append("Directory.Build.props: EnableNETAnalyzers")
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no .editorconfig or EnableNETAnalyzers found",
                recommendation=(
                    "Add a .editorconfig, or set <EnableNETAnalyzers>true</EnableNETAnalyzers> "
                    "in Directory.Build.props."
                ),
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_coverage(self, root: Path, combined: str) -> CategoryResult:
        evidence = []
        if "coverlet" in combined.lower():
            evidence.append("PackageReference: coverlet")
        wf_dir = root / ".github" / "workflows"
        if not evidence and wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                text = read_text(wf) or ""
                if "XPlat Code Coverage" in text or "--collect" in text:
                    evidence.append(f".github/workflows/{wf.name}: collects coverage")
                    break
        if not evidence:
            return CategoryResult(
                Tier.ABSENT, reason="no coverlet package or coverage collection in CI found",
                recommendation=(
                    "Add the coverlet.collector package and run `dotnet test "
                    '--collect:"XPlat Code Coverage"`.'
                ),
            )
        return CategoryResult(Tier.CONFIGURED, evidence=evidence)

    def _scan_reproducibility(self, root: Path, combined: str) -> CategoryResult:
        has_lockfile = (root / "packages.lock.json").exists() or any(
            rglob_excluding(root, "packages.lock.json")
        )
        ranges = VERSION_RANGE_PATTERN.findall(combined)
        pinned = PINNED_VERSION_PATTERN.findall(combined)
        refs = len(PACKAGE_REF_PATTERN.findall(combined))

        if has_lockfile:
            return CategoryResult(Tier.CONFIGURED, evidence=["packages.lock.json"])
        if refs == 0:
            return CategoryResult(
                Tier.ABSENT, reason="no PackageReference entries found to evaluate",
                recommendation=(
                    "Add explicit-version PackageReference entries as dependencies "
                    "are added."
                ),
            )
        if ranges:
            return CategoryResult(
                Tier.ABSENT,
                reason=(
                    f"{len(ranges)} floating/range PackageReference version(s) found and no "
                    "packages.lock.json (RestorePackagesWithLockFile is opt-in in .NET)"
                ),
                recommendation=(
                    "Pin exact PackageReference versions, or enable "
                    "<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile> and run "
                    "`dotnet restore`."
                ),
            )
        return CategoryResult(
            Tier.CONFIGURED,
            evidence=[f"{len(pinned)} PackageReference(s) exact-pinned, no packages.lock.json"],
        )

    def _scan_ci(self, root: Path) -> CategoryResult:
        wf_dir = root / ".github" / "workflows"
        if wf_dir.exists():
            for wf in wf_dir.glob("*.y*ml"):
                if re.search(r"\bdotnet test\b", read_text(wf) or ""):
                    return CategoryResult(
                        Tier.CONFIGURED, evidence=[f".github/workflows/{wf.name}: runs dotnet test"]
                    )
        for f in (".gitlab-ci.yml", "azure-pipelines.yml"):
            p = root / f
            if p.exists() and re.search(r"\bdotnet test\b", read_text(p) or ""):
                return CategoryResult(Tier.CONFIGURED, evidence=[f"{f}: runs dotnet test"])
        return CategoryResult(
            Tier.ABSENT, reason="no CI config found running dotnet test",
            recommendation=(
                "Add a GitHub Actions workflow (.github/workflows/ci.yml) that runs "
                "`dotnet test`."
            ),
        )
