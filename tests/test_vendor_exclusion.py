"""Regression tests for a real bug found scanning a genuine repo: detectors
using unfiltered rglob() picked up dependency test files inside .venv/
site-packages, node_modules, and vendor/ as if they were the scanned
project's own tests.
"""

from pathlib import Path

from girdle.detectors.go_mod import GoModDetector
from girdle.detectors.python_common import scan_tests
from girdle.detectors.rust import RustDetector
from girdle.schema import Tier


def test_python_ignores_test_files_inside_venv(tmp_path: Path):
    vendored = tmp_path / ".venv" / "Lib" / "site-packages" / "somepkg"
    vendored.mkdir(parents=True)
    (vendored / "test_something.py").write_text("def test_x(): pass\n")
    result = scan_tests(tmp_path)
    assert result.tier == Tier.ABSENT


def test_python_still_finds_real_top_level_tests(tmp_path: Path):
    (tmp_path / "test_real.py").write_text("def test_x(): pass\n")
    result = scan_tests(tmp_path)
    assert result.tier == Tier.CONFIGURED


def test_go_ignores_test_files_inside_vendor(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "go.sum").write_text("")
    vendored = tmp_path / "vendor" / "example.com" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "pkg_test.go").write_text("package pkg\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["tests"].tier == Tier.ABSENT


def test_rust_ignores_rs_files_inside_target(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    build_dir = tmp_path / "target" / "debug" / "build" / "somecrate"
    build_dir.mkdir(parents=True)
    (build_dir / "generated.rs").write_text("#[cfg(test)]\nmod tests {}\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["tests"].tier == Tier.ABSENT
