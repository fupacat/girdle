---
type: context
watches:
  - path: src/girdle/reqtrace.py
  - path: src/girdle/cli.py
    symbol: reqs
  - path: src/girdle/cli.py
    symbol: reqs_check
  - path: tests/test_reqtrace.py
---

# Spec: requirement-to-test traceability check

Pilot spec for the [[process-spec-first]] flow. Adds the `req` marker check the
process note lists as unbuilt tooling: a static check that every `REQ-NNN` in a
spec note is claimed by at least one test, and that no test claims a REQ the
spec does not define.

governs:

- src/girdle/reqtrace.py
- src/girdle/cli.py
- tests/test_reqtrace.py

## Requirements

- **REQ-001** A marker SHALL name its spec as well as the requirement,
  `@pytest.mark.req("<slug>", "REQ-NNN")`, where `<slug>` is the spec file name
  without the `spec-` prefix and `.md` suffix. `check_traceability(spec, tests_dir)` SHALL report every `REQ-NNN` defined in the spec that no test
  marks with that spec's slug as `untraced`. Ids are only unique within a spec
  (every spec has a REQ-001), so a marker for another spec SHALL NOT trace it.
  - acceptance: `tests/test_reqtrace.py::test_reports_untraced_req` - given
    `spec-req-trace.md` defining REQ-001 and REQ-002 and a tests directory where
    only a test marked `req("req-trace", "REQ-001")` exists,
    `untraced == ["REQ-002"]`.
  - acceptance: `tests/test_reqtrace.py::test_marker_for_another_spec_does_not_trace`
    - the same spec and a test marked only `req("other-spec", "REQ-001")` gives
      `untraced == ["REQ-001", "REQ-002"]`.
- **REQ-002** `check_traceability` SHALL report every REQ id used in a marker for
  this spec's slug that the spec does not define as `orphaned`; markers naming a
  different slug SHALL be ignored.
  - acceptance: `tests/test_reqtrace.py::test_reports_orphan_marker` - given a
    spec defining REQ-001 and a test marked `req("req-trace", "REQ-009")`,
    `orphaned == ["REQ-009"]` and `untraced == ["REQ-001"]`; a second test
    marked `req("other-spec", "REQ-009")` is not reported.
- **REQ-003** The spec parser SHALL treat a `REQ-NNN` as defined only when it
  appears as bold text at the start of a list item (`- **REQ-NNN**`); mentions
  in prose or inside fenced code blocks SHALL NOT define a requirement.
  - acceptance: `tests/test_reqtrace.py::test_ignores_req_mentions_in_prose_and_code_fences`
    - a spec whose only `REQ-007` occurrences are in a sentence and in a code
      fence yields no defined requirements.
- **REQ-004** Markers SHALL be read statically from the test sources (AST), not by
  importing or running them; a marker with a missing slug or id, or whose
  arguments are not string literals, SHALL be reported as a problem rather than
  ignored.
  - acceptance: `tests/test_reqtrace.py::test_nonliteral_marker_is_reported` -
    a test marked `req(SOME_VAR)` and another marked `req("req-trace")` each
    produce one `problems` entry naming the file and line (two in total), and
    the test modules are never imported.
- **REQ-005** `girdle reqs check <spec> [--tests DIR]` SHALL exit 1 when there is
  any untraced requirement, orphaned marker or problem, and exit 0 otherwise.
  - acceptance: `tests/test_reqtrace.py::test_cli_exit_codes` - exit code 0 for
    a fully traced spec, 1 for each of the three failure kinds.

## Out of scope

- Whether the marked tests pass. CI already enforces that; this check is about
  whether a test exists for each requirement, nothing more.
- Non-pytest runners and non-Python tests.
- Any change to `ScanResult` or scan output.

## Decisions consulted

- `src/girdle/schema.py` is the single source of truth for scan output. This
  check is a repo-process tool, not scan output, so it returns its own small
  result type in `reqtrace.py` and does not touch `ScanResult`.
- [[process-spec-first]] defines the spec shape this check parses.
