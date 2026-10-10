from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from girdle.cli import main
from girdle.reqtrace import check_traceability


@pytest.mark.req("req-trace", "REQ-001")
def test_reports_untraced_req(tmp_path: Path):
    """Given a spec with two REQs and a test for one, the other is untraced."""
    spec = tmp_path / "spec-req-trace.md"
    spec.write_text(
        dedent("""
        - **REQ-001** foo
        - **REQ-002** bar
    """
        )
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_one.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("req-trace", "REQ-001")
        def test_one(): pass
    """
        )
    )

    result = check_traceability(spec, tests_dir)

    assert result.untraced == ["REQ-002"]
    assert not result.orphaned
    assert not result.problems


@pytest.mark.req("req-trace", "REQ-001")
def test_marker_for_another_spec_does_not_trace(tmp_path: Path):
    """A marker for another spec's slug does not trace this spec's REQs."""
    spec = tmp_path / "spec-req-trace.md"
    spec.write_text(
        dedent("""
        - **REQ-001** foo
        - **REQ-002** bar
    """
        )
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_one.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("other-spec", "REQ-001")
        def test_one(): pass
    """
        )
    )

    result = check_traceability(spec, tests_dir)

    assert result.untraced == ["REQ-001", "REQ-002"]
    assert not result.orphaned
    assert not result.problems


@pytest.mark.req("req-trace", "REQ-002")
def test_reports_orphan_marker(tmp_path: Path):
    """A marker for a REQ not in the spec is orphaned."""
    spec = tmp_path / "spec-req-trace.md"
    spec.write_text("- **REQ-001** foo")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_one.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("req-trace", "REQ-009")
        def test_nine(): pass
        @pytest.mark.req("other-spec", "REQ-009")
        def test_other_nine(): pass
    """
        )
    )

    result = check_traceability(spec, tests_dir)

    assert result.untraced == ["REQ-001"]
    assert result.orphaned == ["REQ-009"]
    assert not result.problems


@pytest.mark.req("req-trace", "REQ-003")
def test_ignores_req_mentions_in_prose_and_code_fences(tmp_path: Path):
    """REQ-NNN is only defined when it's bold at the start of a list item."""
    spec = tmp_path / "spec-req-trace.md"
    spec.write_text(
        dedent("""
        This is about REQ-007.
        ```
        REQ-007
        ```
    """
        )
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    result = check_traceability(spec, tests_dir)

    assert not result.untraced
    assert not result.orphaned
    assert not result.problems


@pytest.mark.req("req-trace", "REQ-004")
def test_nonliteral_marker_is_reported(tmp_path: Path):
    """A marker with non-literal or missing args is a problem."""
    spec = tmp_path / "spec-req-trace.md"
    spec.write_text("- **REQ-001** foo")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_one.py").write_text(
        dedent("""
        import pytest
        SOME_VAR = "req-trace"
        @pytest.mark.req(SOME_VAR, "REQ-001")
        def test_one(): pass
        @pytest.mark.req("req-trace")
        def test_two(): pass
    """
        )
    )

    result = check_traceability(spec, tests_dir)

    assert result.untraced == ["REQ-001"]
    assert not result.orphaned
    assert len(result.problems) == 2
    problem_text = "\n".join(result.problems)
    assert "slug argument of @pytest.mark.req must be a string literal" in problem_text
    assert "@pytest.mark.req must have 2 arguments" in problem_text


@pytest.mark.req("req-trace", "REQ-005")
def test_cli_exit_codes(tmp_path: Path):
    """The CLI exits 0 on success and 1 on any failure."""
    runner = CliRunner()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    spec = tmp_path / "spec-req-trace.md"

    # Success
    spec.write_text("- **REQ-001** foo")
    (tests_dir / "test_ok.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("req-trace", "REQ-001")
        def test_ok(): pass
    """
        )
    )
    result = runner.invoke(main, ["reqs", "check", str(spec), "--tests", str(tests_dir)])
    assert result.exit_code == 0, result.output
    assert "All requirements traced." in result.output

    # Untraced
    spec.write_text("- **REQ-001** foo\n- **REQ-002** bar")
    result = runner.invoke(main, ["reqs", "check", str(spec), "--tests", str(tests_dir)])
    assert result.exit_code == 1
    assert "Untraced requirements" in result.output

    # Orphaned
    spec.write_text("- **REQ-001** foo")
    (tests_dir / "test_orphan.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("req-trace", "REQ-009")
        def test_orphan(): pass
    """
        )
    )
    result = runner.invoke(main, ["reqs", "check", str(spec), "--tests", str(tests_dir)])
    assert result.exit_code == 1
    assert "Orphaned test markers" in result.output
    (tests_dir / "test_orphan.py").unlink()

    # Problem
    (tests_dir / "test_problem.py").write_text(
        dedent("""
        import pytest
        @pytest.mark.req("req-trace")
        def test_problem(): pass
    """
        )
    )
    result = runner.invoke(main, ["reqs", "check", str(spec), "--tests", str(tests_dir)])
    assert result.exit_code == 1
    assert "Problems found" in result.output
