# Repairing this repo's mechanical CI checks

When a CI failure is one of the repo-specific mechanical checks below,
fix it directly on the PR branch instead of only reporting it. These are
the failures that have stalled PRs most often; none of them need a design
decision.

- **`girdle index . --check AGENTS.md` fails ("stale")**: run
  `girdle index . --inject AGENTS.md` and commit the regenerated block.
  Never edit the block by hand.
- **`girdle notes check .` fails ("watches changed")**: read the named
  note and the watched file's diff. If the note is still accurate, run
  `girdle notes ack <note path>`. If the change made it inaccurate, update
  the note's prose in the same commit (its hash refreshes automatically),
  then ack. Do not ack a note you have not compared against the change.
- **`mdformat` fails**: run `pre-commit run mdformat --all-files` and
  commit the result.
- **`ruff` fails**: run `ruff check --fix .`, fix any remaining
  findings by hand, and commit.
- **`yamllint` fails**: it never rewrites files; edit the YAML to fix
  each rule `yamllint .` reports, then commit.
- **`mergify config validate` fails**: fix the schema error it names; do
  not change queue behavior beyond what is needed to make it valid.
- Before pushing any of these, run `pre-commit run --all-files` and confirm
  it passes.

Do not merge or rebase `master` into a PR branch unless there is a real
conflict: a proactive sync changes the head SHA and dismisses existing
approvals. Do not mark a PR ready for review or convert it to draft
yourself; the workflows own that. If a fix would need a design change
(rather than a mechanical repair), leave a comment describing it instead of
pushing.
