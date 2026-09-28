from pathlib import Path

from girdle.detectors.dotnet import DotNetDetector
from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.java_gradle import JavaGradleDetector
from girdle.detectors.java_maven import JavaMavenDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.rust import RustDetector
from girdle.schema import CATEGORY_NAMES, Tier


def test_schema_category_names_include_build():
    assert "build" in CATEGORY_NAMES


def test_go_build_configured_and_verifiable(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["go", "build", "./..."]


def test_rust_build_configured_and_verifiable(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\nversion = '0.1.0'\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["cargo", "build"]


def test_maven_build_configured_and_verifiable(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project />")
    det = JavaMavenDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["mvn", "-DskipTests", "package"]


def test_gradle_build_configured_and_verifiable(tmp_path: Path):
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    det = JavaGradleDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"][-1] == "assemble"


def test_dotnet_build_configured_and_verifiable(tmp_path: Path):
    (tmp_path / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk" />\n')
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["dotnet", "build"]


def test_js_build_requires_explicit_build_script(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build","test":"vitest"}}')
    (tmp_path / "package-lock.json").write_text("{}")
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" in det.applicable_categories(fp)
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["npm", "run", "build"]


def test_js_without_build_script_omits_build_category(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}')
    (tmp_path / "package-lock.json").write_text("{}")
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "build" not in det.applicable_categories(fp)
    assert "build" not in result
    assert "build" not in det.run_commands(fp)
