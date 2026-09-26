from pathlib import Path

from girdle.indexer import (
    build_index,
    find_symbol_source,
    inject_into,
    is_stale,
    render_block,
    render_manifest,
)


def test_python_symbols_extracted(tmp_path: Path):
    (tmp_path / "mod.py").write_text(
        "def top_level():\n    pass\n\nclass Foo:\n    def method(self):\n        pass\n"
    )
    index = build_index(tmp_path)
    entry = next(e for e in index.entries if e.path == "mod.py")
    assert entry.language == "python"
    assert "top_level" in entry.symbols
    assert "Foo" in entry.symbols
    assert "method" not in entry.symbols  # nested methods excluded, flat index only


def test_excluded_dirs_are_skipped(tmp_path: Path):
    vendor = tmp_path / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "index.js").write_text("function hidden() {}\n")
    (tmp_path / "app.js").write_text("function visible() {}\n")
    index = build_index(tmp_path)
    paths = [e.path for e in index.entries]
    assert "app.js" in paths
    assert not any("node_modules" in p for p in paths)


def test_go_and_rust_symbols(tmp_path: Path):
    (tmp_path / "main.go").write_text("package main\n\nfunc Run() {}\n\ntype Server struct{}\n")
    (tmp_path / "lib.rs").write_text("pub fn run() {}\n\npub struct Config {}\n")
    index = build_index(tmp_path)
    go_entry = next(e for e in index.entries if e.path == "main.go")
    rs_entry = next(e for e in index.entries if e.path == "lib.rs")
    assert "Run" in go_entry.symbols
    assert "Server" in go_entry.symbols
    assert "run" in rs_entry.symbols
    assert "Config" in rs_entry.symbols


def test_budget_truncates_and_flags(tmp_path: Path):
    for i in range(20):
        (tmp_path / f"mod_{i}.py").write_text(f"def func_{i}():\n    pass\n" * 5)
    index = build_index(tmp_path, budget_tokens=50)
    assert index.truncated is True
    assert len(index.entries) < index.total_files_scanned


def test_manifest_render_is_deterministic(tmp_path: Path):
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    index1 = build_index(tmp_path)
    index2 = build_index(tmp_path)
    assert render_manifest(index1) == render_manifest(index2)
    # alphabetical display order regardless of symbol-count ranking
    manifest = render_manifest(index1)
    assert manifest.index("a.py") < manifest.index("b.py")


def test_inject_creates_markers_in_empty_file(tmp_path: Path):
    target = tmp_path / "AGENTS.md"
    result = inject_into(target, "a.py | python | 1L | foo")
    assert "girdle:index:start" in result
    assert "a.py | python | 1L | foo" in result


def test_inject_replaces_existing_block(tmp_path: Path):
    target = tmp_path / "AGENTS.md"
    target.write_text("# Notes\n\n" + render_block("old-manifest") + "\n\nmore notes\n")
    result = inject_into(target, "new-manifest")
    assert "old-manifest" not in result
    assert "new-manifest" in result
    assert "# Notes" in result
    assert "more notes" in result


def test_is_stale_true_when_missing(tmp_path: Path):
    assert is_stale(tmp_path / "nope.md", "anything") is True


def test_is_stale_false_when_matching(tmp_path: Path):
    target = tmp_path / "AGENTS.md"
    target.write_text(render_block("current-manifest"))
    assert is_stale(target, "current-manifest") is False


def test_is_stale_true_when_drifted(tmp_path: Path):
    target = tmp_path / "AGENTS.md"
    target.write_text(render_block("old-manifest"))
    assert is_stale(target, "new-manifest") is True


def test_find_symbol_source_python_includes_decorator():
    # A decorator change is a real code change and must show up in the
    # hashed span, not just the unwrapped function body.
    source = b"@decorator\ndef greet():\n    pass\n"
    text = find_symbol_source(source, "python", "python", "greet")
    assert text.startswith("@decorator")


def test_find_symbol_source_js_includes_export():
    source = b"export function greet() {}\n"
    text = find_symbol_source(source, "javascript", "javascript", "greet")
    assert text.startswith("export")


def test_find_symbol_source_js_const_arrow_includes_export():
    source = b"export const greet = () => {}\n"
    text = find_symbol_source(source, "javascript", "javascript", "greet")
    assert text.startswith("export")
