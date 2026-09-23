import sys
from pathlib import Path

from girdle.runner import run_check


def test_missing_binary_is_not_ran(tmp_path: Path):
    outcome = run_check(["definitely-not-a-real-binary-xyz"], tmp_path)
    assert outcome.ran is False
    assert outcome.passed is False
    assert "not found" in outcome.reason


def test_successful_command(tmp_path: Path):
    outcome = run_check([sys.executable, "-c", "exit(0)"], tmp_path)
    assert outcome.ran is True
    assert outcome.passed is True
    assert outcome.reason is None


def test_failing_command(tmp_path: Path):
    outcome = run_check([sys.executable, "-c", "exit(1)"], tmp_path)
    assert outcome.ran is True
    assert outcome.passed is False
    assert "exited 1" in outcome.reason


def test_timeout(tmp_path: Path):
    outcome = run_check([sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, timeout=1)
    assert outcome.ran is True
    assert outcome.passed is False
    assert "timed out" in outcome.reason
