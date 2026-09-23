import sys
from pathlib import Path

from girdle.detectors.base import Fingerprint
from girdle.scan import _verify
from girdle.schema import CategoryResult, Tier


class _FakeDetector:
    def __init__(self, command):
        self._command = command

    def run_commands(self, fp):
        return {"tests": self._command}


def _fp(tmp_path: Path) -> Fingerprint:
    return Fingerprint(id="fake", language="fake", toolchain="fake", root=tmp_path, variants=[])


def test_verify_upgrades_to_verified_on_success(tmp_path: Path):
    categories = {"tests": CategoryResult(Tier.CONFIGURED, evidence=["some config"])}
    detector = _FakeDetector([sys.executable, "-c", "exit(0)"])
    _verify(detector, _fp(tmp_path), categories)
    assert categories["tests"].tier == Tier.VERIFIED
    assert any("verified" in e for e in categories["tests"].evidence)


def test_verify_keeps_configured_on_failure(tmp_path: Path):
    categories = {"tests": CategoryResult(Tier.CONFIGURED, evidence=["some config"])}
    detector = _FakeDetector([sys.executable, "-c", "exit(1)"])
    _verify(detector, _fp(tmp_path), categories)
    assert categories["tests"].tier == Tier.CONFIGURED
    assert "exited 1" in categories["tests"].reason


def test_verify_skips_absent_categories(tmp_path: Path):
    categories = {"tests": CategoryResult(Tier.ABSENT, reason="no config")}
    detector = _FakeDetector([sys.executable, "-c", "exit(0)"])
    _verify(detector, _fp(tmp_path), categories)
    assert categories["tests"].tier == Tier.ABSENT


def test_verify_noop_without_run_commands(tmp_path: Path):
    categories = {"tests": CategoryResult(Tier.CONFIGURED)}

    class NoRunCommands:
        pass

    _verify(NoRunCommands(), _fp(tmp_path), categories)
    assert categories["tests"].tier == Tier.CONFIGURED
