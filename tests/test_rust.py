from pathlib import Path

from girdle.detectors.rust import RustDetector
from girdle.schema import Tier


def test_detect_none_without_cargo_toml(tmp_path: Path):
    assert RustDetector().detect(tmp_path) is None


def test_bin_crate_missing_lock_is_absent_and_applicable(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    assert "lib" not in fp.variants
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
    assert "reproducibility" in det.applicable_categories(fp)


def test_lib_crate_missing_lock_is_excluded_from_applicable(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[lib]\nname = 'x'\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    assert "lib" in fp.variants
    assert "reproducibility" not in det.applicable_categories(fp)


def test_lib_crate_with_committed_lock_is_applicable_and_configured(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[lib]\nname = 'x'\n")
    (tmp_path / "Cargo.lock").write_text("")
    det = RustDetector()
    fp = det.detect(tmp_path)
    assert "reproducibility" in det.applicable_categories(fp)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_inline_test_detected(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n[[bin]]\nname = 'x'\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() {}\n#[cfg(test)]\nmod tests {}\n")
    det = RustDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["tests"].tier == Tier.CONFIGURED
