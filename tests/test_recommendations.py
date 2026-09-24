"""Spot-checks that ABSENT categories carry a concrete, stack-specific
recommendation across a representative sample of detectors/toolchains -
not exhaustive of all ~56 ABSENT branches, but enough to catch a systemic
regression (e.g. the field silently not being wired up somewhere).
"""

from pathlib import Path

from girdle.detectors.dotnet import DotNetDetector
from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.js_yarn import JsYarnDetector
from girdle.detectors.python_pip import PythonPipDetector
from girdle.detectors.rust import RustDetector
from girdle.schema import Tier


def test_python_pip_recommendation_names_pip_compile(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests\nclick\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "pip-compile" in result["reproducibility"].recommendation


def test_js_npm_recommendation_is_toolchain_specific(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "npm install" in result["reproducibility"].recommendation


def test_js_yarn_recommendation_names_yarn_not_npm(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".gitignore").write_text("yarn.lock\n")
    det = JsYarnDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "yarn.lock" in result["reproducibility"].recommendation
    assert "npm" not in result["reproducibility"].recommendation


def test_go_recommendation_names_go_mod_tidy(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "go mod tidy" in result["reproducibility"].recommendation


def test_rust_bin_recommendation_names_cargo_build(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "cargo build" in result["reproducibility"].recommendation


def test_dotnet_recommendation_mentions_lockfile_or_pinning(tmp_path: Path):
    csproj = (
        '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
        '<PackageReference Include="X" Version="1.*" /></ItemGroup></Project>'
    )
    (tmp_path / "App.csproj").write_text(csproj)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "RestorePackagesWithLockFile" in result["reproducibility"].recommendation


def test_verified_category_has_no_recommendation(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "go.sum").write_text("")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["reproducibility"].recommendation is None
