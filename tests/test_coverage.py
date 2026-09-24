"""Coverage category: spot-checks across a representative sample of
detectors, not exhaustive of all 14 - mirrors the sampling approach in
test_recommendations.py.
"""

from pathlib import Path

from girdle.detectors.dotnet import DotNetDetector
from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.java_gradle import JavaGradleDetector
from girdle.detectors.java_maven import JavaMavenDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.python_pip import PythonPipDetector
from girdle.detectors.rust import RustDetector
from girdle.schema import Tier


def test_python_coverage_absent_by_default(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("click==8.1.7\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert "coverage" in det.applicable_categories(fp)
    assert result["coverage"].tier == Tier.ABSENT
    assert "pytest-cov" in result["coverage"].recommendation


def test_python_coverage_configured_via_coveragerc(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("click==8.1.7\n")
    (tmp_path / ".coveragerc").write_text("[run]\nsource = .\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED


def test_python_coverage_configured_via_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.run]\nsource = ['.']\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED
    assert "pyproject.toml#tool.coverage" in result["coverage"].evidence


def test_python_coverage_run_command_declared(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.coverage.run]\n")
    det = PythonPipDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert commands["coverage"] == ["pytest", "--cov"]


def test_js_npm_coverage_via_dependency(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "devDependencies": {"jest": "1.0.0", "nyc": "1.0.0"}}'
    )
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED
    assert any("nyc" in e for e in result["coverage"].evidence)


def test_js_npm_coverage_absent(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.ABSENT
    assert "npm install" in result["coverage"].recommendation


def test_js_npm_coverage_run_command_only_if_script_declared(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "jest", "coverage": "jest --coverage"}}'
    )
    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert commands["coverage"] == ["npm", "run", "coverage"]


def test_go_coverage_absent_without_ci_evidence(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.ABSENT


def test_go_coverage_configured_via_ci(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("run: go test -coverprofile=coverage.out ./...\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED


def test_go_coverage_run_command_always_declared(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    commands = det.run_commands(fp)
    assert commands["coverage"] == ["go", "test", "-cover", "./..."]


def test_rust_coverage_absent(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.ABSENT


def test_rust_coverage_configured_via_tarpaulin_toml(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    (tmp_path / "tarpaulin.toml").write_text("")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED
    commands = det.run_commands(fp)
    assert commands["coverage"] == ["cargo", "tarpaulin"]


def test_java_maven_coverage_via_jacoco(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(
        "<project><plugins><jacoco-maven-plugin/></plugins></project>"
    )
    det = JavaMavenDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED


def test_java_gradle_coverage_via_jacoco(tmp_path: Path):
    (tmp_path / "build.gradle").write_text("plugins { id 'jacoco' }\n")
    det = JavaGradleDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED
    commands = det.run_commands(fp)
    assert "jacocoTestReport" in commands["coverage"]


def test_dotnet_coverage_via_coverlet(tmp_path: Path):
    csproj = (
        '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
        '<PackageReference Include="coverlet.collector" Version="6.0.0" /></ItemGroup></Project>'
    )
    (tmp_path / "App.csproj").write_text(csproj)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.CONFIGURED
    commands = det.run_commands(fp)
    assert "coverage" in commands


def test_dotnet_coverage_absent(tmp_path: Path):
    csproj = '<Project Sdk="Microsoft.NET.Sdk"></Project>'
    (tmp_path / "App.csproj").write_text(csproj)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["coverage"].tier == Tier.ABSENT
