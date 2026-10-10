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

| MCSWE idea                      | Here                                                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| SRS with `REQ-NNN` lines        | A spec note: `.agent-vault/context/spec-<topic>.md`, template below                                                                |
| Acceptance record per REQ       | One line per REQ naming a test node id and its expected observable result                                                          |
| Traceability                    | Tests carry `@pytest.mark.req("<spec-slug>", "REQ-NNN")` (marker and trace check are future tooling, see below)                    |
| Revision-bound approval         | The merged spec PR *is* the approval of that text. Later edits are new PRs that go through the same review                         |
| Approver gates                  | The reviewing agent, using `.github/review/spec-review.md`; humans decide anything touching core contracts                         |
| Amend on change                 | Edit the spec in its own PR. Once the code exists, the spec `watches` it, so drift in the code marks the spec stale until re-acked |
| ICD and per-function trace tags | Dropped. They are the retrofit cost and add little over tests plus the structural index                                            |

## Flow

1. **Spec PR.** The spec note only, no implementation. The reviewing agent reviews it against
   the rubric; a human approves anything it refuses to.
1. **Implementation PR.** Code and tests governed by the spec's `governs:`
   paths. Each REQ has at least one passing test. This PR also adds the
   governed code paths to the spec's frontmatter `watches` (they cannot exist
   earlier: a watch on a missing path is a dangling watch and blocks the
   commit), so later drift in that code marks the spec stale.
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

What the vault hashes do and do not give you: `girdle notes check` marks a note
stale when a *watched target* changes, and skips notes with no `watches`.
Editing a spec's own prose does not mark it stale. So the approval of a spec's
text is the merged spec PR, and `watches` (added with the implementation) covers
the other direction: code that drifts from an approved spec.

Approval is an agent's, not a rubber stamp: the rubric in
`.github/review/spec-review.md` asks the reviewing agent to try to defeat each
requirement (a trivial implementation that would still pass) and to report per
REQ. The rubric is scoped by its own wording to PRs that touch spec files, so
it can sit alongside the general review conventions without changing how other
PRs are reviewed. Which agent reviews is a separate decision (Gitar's trial
ended; see the tool-roles decision notes).

## Open items

- **Marker and trace check.** A pytest marker plus a check that every REQ has a
  passing test and every marker points at a real REQ. Not built yet; until it
  is, the review rubric and human review carry this.
- **Native note type.** `girdle notes` recognises fixed folders, so specs live in
  `context/` with a `spec-` prefix for now. A `specs/` type would let the
  hook treat them as approvals proper.
- **Unverified.** Whether the reviewing agent reliably reports per-REQ findings
  from this rubric. The first pilot spec is the test of that.
