Apply this section only to a PR that adds or changes a spec note, a file
matching `.agent-vault/context/spec-*.md`. Ignore it for every other PR.

A spec note is approved only if each requirement survives the checks below.
Report one finding per failing requirement, quoting its REQ id. A spec with
no per-requirement result at all is itself a blocking finding: do not
approve on overall impression.

- **Vacuous pass.** For each REQ, ask whether a trivial or wrong
  implementation could satisfy its acceptance test (always return the
  expected value, catch and ignore the error, test only the happy path).
  If one plausibly could, the requirement fails.
- **Testability.** Each REQ states one observable outcome, uses SHALL, and
  names a concrete test node id. Reject "handle gracefully", "efficient",
  "robust", or an acceptance line that restates the requirement without an
  input and an expected output.
- **Decision conflicts.** Compare the spec with the notes in
  `.agent-vault/decisions/` and `.agent-vault/context/`. Cite the note that
  applies, or state that none do. A spec that contradicts a decision note
  without superseding it fails.
- **Scope.** The `governs:` paths must match the paths the PR adds or
  changes, and a spec PR must not contain implementation code. Listing
  `src/girdle/schema.py`, `detectors/base.py` or any workflow file under
  `governs:` means a human decides: do not approve.
- **Single source of truth.** A requirement that adds a second
  representation of scan output, instead of extending `ScanResult`, fails.
