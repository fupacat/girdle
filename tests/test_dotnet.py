from pathlib import Path

from girdle.detectors.dotnet import DotNetDetector
from girdle.schema import Tier

CSPROJ_PINNED = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
</Project>
"""

CSPROJ_RANGE = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.*" />
  </ItemGroup>
</Project>
"""


def test_detect_none_without_project_files(tmp_path: Path):
    assert DotNetDetector().detect(tmp_path) is None


def test_pinned_packagereference_configured(tmp_path: Path):
    (tmp_path / "App.csproj").write_text(CSPROJ_PINNED)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_floating_version_without_lockfile_is_absent(tmp_path: Path):
    (tmp_path / "App.csproj").write_text(CSPROJ_RANGE)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_packages_lock_json_configured_even_with_ranges(tmp_path: Path):
    (tmp_path / "App.csproj").write_text(CSPROJ_RANGE)
    (tmp_path / "packages.lock.json").write_text("{}")
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_test_sdk_reference_detected(tmp_path: Path):
    proj = """<Project Sdk="Microsoft.NET.Sdk">
      <ItemGroup>
        <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
      </ItemGroup>
    </Project>
    """
    (tmp_path / "App.Tests.csproj").write_text(proj)
    det = DotNetDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["tests"].tier == Tier.CONFIGURED
