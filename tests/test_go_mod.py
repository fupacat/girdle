from pathlib import Path

from girdle.detectors.go_mod import GoModDetector
from girdle.schema import Tier


def test_detect_none_without_go_mod(tmp_path: Path):
    assert GoModDetector().detect(tmp_path) is None


def test_missing_go_sum_is_absent(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_test_files_detected(tmp_path: Path):
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "go.sum").write_text("")
    (tmp_path / "main_test.go").write_text("package main\n")
    det = GoModDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["tests"].tier == Tier.CONFIGURED
    assert result["reproducibility"].tier == Tier.CONFIGURED
