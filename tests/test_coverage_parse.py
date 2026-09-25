from girdle.coverage_parse import parse_percentage

PYTEST_COV_OUTPUT = """\
Name                     Stmts   Miss  Cover
--------------------------------------------
src/foo.py                  10      2    80%
--------------------------------------------
TOTAL                        10      2    80%
"""

GO_OUTPUT = "ok      example.com/mod 0.003s  coverage: 87.5% of statements\n"

TARPAULIN_OUTPUT = "91.30% coverage, 21/23 lines covered\n"

JEST_TABLE = """\
File      | % Stmts | % Branch | % Funcs | % Lines |
----------|---------|----------|---------|---------|
All files |   79.16 |    65.00 |   80.00 |   79.16 |
"""


def test_parses_python_total_line():
    assert parse_percentage("python", PYTEST_COV_OUTPUT) == "80%"


def test_parses_go_coverage_line():
    assert parse_percentage("go", GO_OUTPUT) == "87.5%"


def test_parses_rust_tarpaulin_line():
    assert parse_percentage("rust", TARPAULIN_OUTPUT) == "91.30%"


def test_parses_js_all_files_row():
    assert parse_percentage("javascript", JEST_TABLE) == "79.16%"


def test_unknown_language_returns_none():
    assert parse_percentage("java", "anything") is None


def test_unparseable_output_returns_none():
    assert parse_percentage("python", "no coverage info here\n") is None


def test_empty_output_returns_none():
    assert parse_percentage("go", "") is None
