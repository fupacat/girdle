"""Cases that specifically exercise real AST parsing vs. the old regex
approach: multi-line signatures, decorators, TS-only constructs, and C#
namespace-wrapped top-level types.
"""

from pathlib import Path

from girdle.indexer import build_index


def _symbols_for(tmp_path: Path, filename: str, content: str) -> list[str]:
    (tmp_path / filename).write_text(content)
    index = build_index(tmp_path)
    entry = next(e for e in index.entries if e.path == filename)
    return entry.symbols


def test_python_decorated_and_multiline_signature(tmp_path: Path):
    content = (
        "@decorator\n"
        "def multi_line(\n"
        "    a: int,\n"
        "    b: str,\n"
        ") -> None:\n"
        "    pass\n"
    )
    symbols = _symbols_for(tmp_path, "mod.py", content)
    assert "multi_line" in symbols


def test_python_async_def(tmp_path: Path):
    symbols = _symbols_for(tmp_path, "mod.py", "async def fetch():\n    pass\n")
    assert "fetch" in symbols


def test_js_export_const_arrow(tmp_path: Path):
    symbols = _symbols_for(tmp_path, "mod.js", "export const handler = () => {};\n")
    assert "handler" in symbols


def test_js_non_function_const_not_captured(tmp_path: Path):
    symbols = _symbols_for(tmp_path, "mod.js", "export const CONFIG = { a: 1 };\n")
    assert "CONFIG" not in symbols


def test_ts_interface_and_type_alias(tmp_path: Path):
    content = "export interface User {\n  id: string;\n}\nexport type Id = string;\n"
    symbols = _symbols_for(tmp_path, "mod.ts", content)
    assert "User" in symbols
    assert "Id" in symbols


def test_tsx_extension_parses(tmp_path: Path):
    content = "export function Component() {\n  return <div />;\n}\n"
    symbols = _symbols_for(tmp_path, "mod.tsx", content)
    assert "Component" in symbols


def test_java_multiple_top_level_types(tmp_path: Path):
    content = "public class Foo {\n    void method() {}\n}\ninterface Bar {}\n"
    symbols = _symbols_for(tmp_path, "Foo.java", content)
    assert "Foo" in symbols
    assert "Bar" in symbols
    assert "method" not in symbols  # nested method excluded, flat index only


def test_csharp_namespace_unwrapped(tmp_path: Path):
    content = "namespace MyApp {\n    public class Foo {}\n    public interface IBar {}\n}\n"
    symbols = _symbols_for(tmp_path, "Foo.cs", content)
    assert "Foo" in symbols
    assert "IBar" in symbols


def test_rust_impl_for_trait(tmp_path: Path):
    content = "pub struct Config {}\npub trait Doer {}\nimpl Doer for Config {}\n"
    symbols = _symbols_for(tmp_path, "lib.rs", content)
    assert "Config" in symbols
    assert "Doer" in symbols


def test_go_multiple_types_in_one_type_declaration_group(tmp_path: Path):
    content = "package main\n\ntype (\n\tServer struct{}\n\tClient struct{}\n)\n"
    symbols = _symbols_for(tmp_path, "main.go", content)
    assert "Server" in symbols
    assert "Client" in symbols
