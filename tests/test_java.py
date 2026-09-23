from pathlib import Path

from girdle.detectors.java_gradle import JavaGradleDetector
from girdle.detectors.java_maven import JavaMavenDetector
from girdle.schema import Tier

POM_PINNED = """<project>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
    </dependency>
  </dependencies>
</project>
"""

POM_RANGE = """<project>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>[4.0,5.0)</version>
    </dependency>
  </dependencies>
</project>
"""


def test_maven_detect_none_without_pom(tmp_path: Path):
    assert JavaMavenDetector().detect(tmp_path) is None


def test_maven_pinned_versions_configured(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(POM_PINNED)
    det = JavaMavenDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["tests"].tier == Tier.CONFIGURED


def test_maven_version_range_is_absent(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(POM_RANGE)
    det = JavaMavenDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_gradle_detect_none_without_build_file(tmp_path: Path):
    assert JavaGradleDetector().detect(tmp_path) is None


def test_gradle_lockfile_configured(tmp_path: Path):
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    (tmp_path / "gradle.lockfile").write_text("")
    det = JavaGradleDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_gradle_no_lock_mechanism_is_absent(tmp_path: Path):
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    det = JavaGradleDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_gradle_kotlin_dsl_variant(tmp_path: Path):
    (tmp_path / "build.gradle.kts").write_text("plugins { java }\n")
    det = JavaGradleDetector()
    fp = det.detect(tmp_path)
    assert "kotlin-dsl" in fp.variants
