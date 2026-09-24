from pathlib import Path

from girdle.align import (
    apply_plan,
    build_align_plans,
    plan_editorconfig,
    plan_gitattributes,
    plan_gitignore,
)

# --- .editorconfig ---

def test_editorconfig_derives_from_black(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.black]\nline-length = 100\n"
    )
    plan = plan_editorconfig(tmp_path, {"python"})
    assert plan.new_content is not None
    assert "[*.py]" in plan.new_content
    assert "max_line_length = 100" in plan.new_content
    assert "indent_size = 4" in plan.new_content
    assert "root = true" in plan.new_content


def test_editorconfig_derives_from_ruff_format(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 120\n[tool.ruff.format]\nindent-style = 'space'\n"
    )
    plan = plan_editorconfig(tmp_path, {"python"})
    assert "max_line_length = 120" in plan.new_content


def test_editorconfig_no_formatter_no_plan(tmp_path: Path):
    plan = plan_editorconfig(tmp_path, {"python"})
    assert plan.new_content is None
    assert plan.additions == []


def test_editorconfig_appends_without_touching_existing_content(tmp_path: Path):
    (tmp_path / ".editorconfig").write_text(
        "root = true\n\n[*.md]\ntrim_trailing_whitespace = false\n"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    plan = plan_editorconfig(tmp_path, {"python"})
    assert "[*.md]" in plan.new_content
    assert "trim_trailing_whitespace = false" in plan.new_content
    assert "[*.py]" in plan.new_content


def test_editorconfig_skips_glob_already_present(tmp_path: Path):
    (tmp_path / ".editorconfig").write_text("root = true\n\n[*.py]\nindent_size = 2\n")
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    plan = plan_editorconfig(tmp_path, {"python"})
    # existing custom indent_size = 2 must survive untouched
    assert plan.new_content is None
    assert any("already present" in a for a in plan.additions)


def test_editorconfig_js_prettier_json(tmp_path: Path):
    (tmp_path / ".prettierrc.json").write_text(
        '{"tabWidth": 2, "useTabs": false, "printWidth": 80}'
    )
    plan = plan_editorconfig(tmp_path, {"javascript"})
    assert "[*.{js,jsx,mjs,cjs}]" in plan.new_content
    assert "indent_size = 2" in plan.new_content


def test_editorconfig_js_unparseable_config_is_skipped(tmp_path: Path):
    (tmp_path / "prettier.config.js").write_text("module.exports = {}")
    plan = plan_editorconfig(tmp_path, {"javascript"})
    assert plan.new_content is None
    assert any("not machine-parseable" in a for a in plan.additions)


def test_editorconfig_rust_from_rustfmt_toml(tmp_path: Path):
    (tmp_path / "rustfmt.toml").write_text("hard_tabs = true\ntab_spaces = 8\nmax_width = 120\n")
    plan = plan_editorconfig(tmp_path, {"rust"})
    assert "[*.rs]" in plan.new_content
    assert "indent_style = tab" in plan.new_content
    assert "indent_size = 8" in plan.new_content


# --- .gitattributes ---

def test_gitattributes_no_eol_signal_no_plan(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    plan = plan_gitattributes(tmp_path, {"python"})
    assert plan.new_content is None


def test_gitattributes_propagates_prettier_eol(tmp_path: Path):
    (tmp_path / ".prettierrc.json").write_text('{"endOfLine": "crlf"}')
    plan = plan_gitattributes(tmp_path, {"javascript"})
    assert plan.new_content == "* text=auto eol=crlf\n"


def test_gitattributes_conflict_when_formatters_disagree(tmp_path: Path):
    (tmp_path / ".prettierrc.json").write_text('{"endOfLine": "crlf"}')
    (tmp_path / "rustfmt.toml").write_text("newline_style = 'Unix'\n")
    plan = plan_gitattributes(tmp_path, {"javascript", "rust"})
    assert plan.new_content is None
    assert any("conflict" in a for a in plan.additions)


def test_gitattributes_existing_text_auto_left_alone(tmp_path: Path):
    (tmp_path / ".gitattributes").write_text("* text=auto\n")
    (tmp_path / ".prettierrc.json").write_text('{"endOfLine": "lf"}')
    plan = plan_gitattributes(tmp_path, {"javascript"})
    assert plan.new_content is None
    assert any("already present" in a for a in plan.additions)


def test_gitattributes_appends_to_existing_file(tmp_path: Path):
    (tmp_path / ".gitattributes").write_text("*.png binary\n")
    (tmp_path / ".prettierrc.json").write_text('{"endOfLine": "lf"}')
    plan = plan_gitattributes(tmp_path, {"javascript"})
    assert plan.new_content == "*.png binary\n* text=auto eol=lf\n"


# --- .gitignore ---

def test_gitignore_adds_missing_patterns(tmp_path: Path):
    plan = plan_gitignore(tmp_path, {"python"})
    assert plan.new_content is not None
    assert "__pycache__" in plan.new_content
    assert ".pytest_cache/" in plan.new_content


def test_gitignore_already_covered_no_plan(tmp_path: Path):
    (tmp_path / ".gitignore").write_text(
        "__pycache__\n.venv\n*.pyc\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n*.egg-info/\n"
    )
    plan = plan_gitignore(tmp_path, {"python"})
    assert plan.new_content is None


def test_gitignore_multi_language_union(tmp_path: Path):
    plan = plan_gitignore(tmp_path, {"python", "javascript"})
    assert "node_modules" in plan.new_content
    assert "__pycache__" in plan.new_content


# --- apply_plan / build_align_plans ---

def test_apply_plan_writes_file(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    plan = plan_editorconfig(tmp_path, {"python"})
    applied = apply_plan(tmp_path, plan)
    assert applied is True
    assert (tmp_path / ".editorconfig").exists()
    assert "[*.py]" in (tmp_path / ".editorconfig").read_text()


def test_apply_plan_noop_when_no_content(tmp_path: Path):
    plan = plan_editorconfig(tmp_path, {"python"})
    applied = apply_plan(tmp_path, plan)
    assert applied is False
    assert not (tmp_path / ".editorconfig").exists()


def test_build_align_plans_returns_three_plans(tmp_path: Path):
    plans = build_align_plans(tmp_path, {"python"})
    assert {p.file for p in plans} == {".editorconfig", ".gitattributes", ".gitignore"}
