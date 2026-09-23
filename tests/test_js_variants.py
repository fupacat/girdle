from pathlib import Path

from girdle.detectors.js_bun import JsBunDetector
from girdle.detectors.js_npm import JsNpmDetector
from girdle.detectors.js_pnpm import JsPnpmDetector
from girdle.detectors.js_yarn import JsYarnDetector
from girdle.schema import Tier


def test_npm_yields_to_yarn(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "yarn.lock").write_text("")
    assert JsNpmDetector().detect(tmp_path) is None
    assert JsYarnDetector().detect(tmp_path) is not None


def test_npm_yields_to_pnpm(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    assert JsNpmDetector().detect(tmp_path) is None
    assert JsPnpmDetector().detect(tmp_path) is not None


def test_npm_yields_to_bun(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "bun.lockb").write_bytes(b"\x00")
    assert JsNpmDetector().detect(tmp_path) is None
    assert JsBunDetector().detect(tmp_path) is not None


def test_yarn_gitignored_lockfile_is_absent(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (tmp_path / "yarn.lock").write_text("")
    (tmp_path / ".gitignore").write_text("yarn.lock\n")
    det = JsYarnDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT


def test_bun_binary_lockfile_presence_only(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "bun.lockb").write_bytes(b"\x00\x01")
    det = JsBunDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.CONFIGURED


def test_pnpm_workspace_variant_detected(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    det = JsPnpmDetector()
    fp = det.detect(tmp_path)
    assert "workspace" in fp.variants
