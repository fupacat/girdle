---
type: context
---

# Spec-first process for new code

How girdle adopts the *process* of [MCSWE v3](https://github.com/fupacat/mcswe)
(spec, then architecture, then implementation, then audit) for new code only,
without the framework itself. The framework is POSIX-only (`fcntl` locks) and
assumes a whole-project retrofit; neither fits this repo. This note keeps the
parts that matter and maps each onto machinery girdle already has.

## What is kept, and where it lives

| MCSWE idea                      | Here                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| SRS with `REQ-NNN` lines        | A spec note: `.agent-vault/context/spec-<topic>.md`, template below                              |
| Acceptance record per REQ       | One line per REQ naming a test node id and its expected observable result                        |
| Traceability                    | Tests carry `@pytest.mark.req("REQ-NNN")` (marker and trace check are future tooling, see below) |
| Revision-bound approval         | The spec note's `watches` hashes and `girdle notes ack`; editing an approved spec marks it stale |
| Approver gates                  | Gitar, using `.gitar/review/spec-review.md`; humans decide anything touching core contracts      |
| Amend on change                 | Edit the spec in its own PR; implementation PRs reference the approved spec                      |
| ICD and per-function trace tags | Dropped. They are the retrofit cost and add little over tests plus the structural index          |

## Flow

1. **Spec PR.** The spec note only, no implementation. Gitar reviews it against
   the rubric; a human approves anything it refuses to.
1. **Implementation PR.** Code and tests governed by the spec's `governs:`
   paths. Each REQ has at least one passing test.
1. **Change.** New behavior means amending the spec first, in its own PR.

This matches the minimal-discrete-PR policy and gives the Gemini and Copilot
agents a precise issue body to implement against.

## Spec template

```markdown
---
type: context
---

# Spec: <topic>

governs:
- src/girdle/<new_module>.py
- tests/test_<new_module>.py

## Requirements

- **REQ-001** The scanner SHALL <one observable outcome>.
  - acceptance: `tests/test_<new_module>.py::test_<name>` - given <input>,
    returns/raises <expected output>.

## Out of scope

## Decisions consulted
```

## Approval

Approval is an agent's, not a rubber stamp: the rubric in
`.gitar/review/spec-review.md` asks Gitar to try to defeat each requirement
(a trivial implementation that would still pass) and to report per REQ. Gitar's
repo-level approval criteria (`.gitar/config/approve.md`) are deliberately not
used: they apply to every PR and have no path scoping, while review guidance
only affects PRs that touch spec files.

## Open items

- **Marker and trace check.** A pytest marker plus a check that every REQ has a
  passing test and every marker points at a real REQ. Not built yet; until it
  is, the Gitar rubric and human review carry this.
- **Native note type.** `girdle notes` recognises fixed folders, so specs live in
  `context/` with a `spec-` prefix for now. A `specs/` type would let the
  hook treat them as approvals proper.
- **Unverified.** Whether Gitar reliably reports per-REQ findings from review
  guidance. The first pilot spec is the test of that.
