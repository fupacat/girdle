from pathlib import Path

import pytest

from girdle.detectors import js_common
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


# --- Build detection across JS toolchains ---

def test_yarn_build_script_detected(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"jest","build":"tsc"}}')
    (tmp_path / "yarn.lock").write_text("")
    det = JsYarnDetector()
    fp = det.detect(tmp_path)
    assert "build" in det.applicable_categories(fp)
    result = det.scan(fp, mode="static")
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["yarn", "run", "build"]


def test_yarn_without_build_script_omits_build_category(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"jest"}}')
    (tmp_path / "yarn.lock").write_text("")
    det = JsYarnDetector()
    fp = det.detect(tmp_path)
    assert "build" not in det.applicable_categories(fp)
    assert "build" not in det.scan(fp, mode="static")


def test_pnpm_build_script_detected(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest","build":"vite build"}}')
    (tmp_path / "pnpm-lock.yaml").write_text("")
    det = JsPnpmDetector()
    fp = det.detect(tmp_path)
    assert "build" in det.applicable_categories(fp)
    result = det.scan(fp, mode="static")
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["pnpm", "run", "build"]


def test_pnpm_without_build_script_omits_build_category(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}')
    (tmp_path / "pnpm-lock.yaml").write_text("")
    det = JsPnpmDetector()
    fp = det.detect(tmp_path)
    assert "build" not in det.applicable_categories(fp)
    assert "build" not in det.scan(fp, mode="static")


def test_bun_build_script_detected(tmp_path: Path):
    pkg = '{"scripts":{"test":"bun test","build":"bun run build.ts"}}'
    (tmp_path / "package.json").write_text(pkg)
    (tmp_path / "bun.lock").write_text("")
    det = JsBunDetector()
    fp = det.detect(tmp_path)
    assert "build" in det.applicable_categories(fp)
    result = det.scan(fp, mode="static")
    assert result["build"].tier == Tier.CONFIGURED
    assert det.run_commands(fp)["build"] == ["bun", "run", "build"]


def test_bun_without_build_script_omits_build_category(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"bun test"}}')
    (tmp_path / "bun.lock").write_text("")
    det = JsBunDetector()
    fp = det.detect(tmp_path)
    assert "build" not in det.applicable_categories(fp)
    assert "build" not in det.scan(fp, mode="static")


# --- has_build_script robustness ---

@pytest.mark.parametrize("scripts_value", [None, "not-a-dict", ["array"], 42])
def test_has_build_script_tolerates_non_dict_scripts(scripts_value):
    pkg_data = {"scripts": scripts_value}
    assert js_common.has_build_script(pkg_data) is False


def test_has_build_script_empty_string_is_false():
    assert js_common.has_build_script({"scripts": {"build": ""}}) is False
    assert js_common.has_build_script({"scripts": {"build": "   "}}) is False


def test_js_build_scan_entry_absent_when_no_build_script(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    assert js_common.js_build_scan_entry({}) == {}


def test_js_applicable_categories_includes_build_when_script_present(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"build":"tsc"}}')
    cats = js_common.js_applicable_categories(tmp_path)
    assert "build" in cats
    # build is inserted at index 3 (after tests, lint, coverage)
    assert cats.index("build") == 3


def test_js_applicable_categories_excludes_build_when_no_script(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    cats = js_common.js_applicable_categories(tmp_path)
    assert "build" not in cats
