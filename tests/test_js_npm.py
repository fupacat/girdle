from pathlib import Path

from girdle.detectors.js_npm import JsNpmDetector
from girdle.schema import Tier


def test_detect_none_without_package_json(tmp_path: Path):
    assert JsNpmDetector().detect(tmp_path) is None


def test_detect_yields_to_yarn(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "yarn.lock").write_text("")
    assert JsNpmDetector().detect(tmp_path) is None


def test_full_configured_repo(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}'
    )
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / ".eslintrc.json").write_text("{}")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("run: npm test\n")

    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    assert fp is not None
    result = det.scan(fp, mode="static")

    assert result["tests"].tier == Tier.CONFIGURED
    assert result["lint"].tier == Tier.CONFIGURED
    assert result["reproducibility"].tier == Tier.CONFIGURED
    assert result["ci_gating"].tier == Tier.CONFIGURED


def test_gitignored_lockfile_scores_absent(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / ".gitignore").write_text("package-lock.json\n")

    det = JsNpmDetector()
    fp = det.detect(tmp_path)
    result = det.scan(fp, mode="static")
    assert result["reproducibility"].tier == Tier.ABSENT
