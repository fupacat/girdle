---
type: decision
---

# PRs are scoped to one discrete change

## Context

An investigation into why merge velocity dropped and the queue started
seeing frequent friction found several shared-artifact/hot-file collision
sources, including generated-index churn, vault-freshness changes, and
`schema.py`'s hot-file cluster. Independent of those specific fixes, a
wide-scoped PR is simply more likely to overlap with whatever else is in
flight - a small PR narrows *how much* it touches even within a hot file,
and lands faster through the queue, reducing the window in which it can
collide with something else. This matches established
trunk-based-development practice (short-lived branches, small diffs), not
a scheme specific to this repo.

## Decision

Each PR is scoped to one discrete, reviewable change. Concretely:

- Break a larger feature into the smallest mergeable steps rather than
  landing it as one PR. Plumbing/refactoring that enables a behavior
  change lands separately from the behavior change itself.
- If a step needs to merge before the feature it's part of is complete
  or user-visible, land it inert (unreferenced/dead code, or gated behind
  a flag) rather than holding the PR until the whole feature is ready.
  girdle has no feature-flag mechanism yet - use the lightest option that
  fits (an unwired code path, a constant, a config toggle) until a real
  need for something heavier shows up.
- A PR that's naturally one unit of work (a single bug fix, a single
  focused check) doesn't need artificial splitting - the target is
  discreteness, not a line-count rule.

This is a companion to, not a substitute for, structural work on shared
artifacts and hot files, such as decomposing hot files and fixing
diff-scoped staleness checks. That work reduces *where* collisions can
happen; this policy reduces *how often* two things overlap enough to
collide in the first place.

## Alternatives considered

- **Leave PR scope as-is, rely only on the structural fixes** - rejected:
  the structural fixes address specific mechanisms (index reordering,
  hash drift) but don't address the general case of two unrelated large
  PRs touching the same ordinary file.
- **Enforce PR size with a line-count/file-count CI gate** - not adopted
  for now; scope is a judgment call (see Decision above), and a
  mechanical size limit would either be too strict for a genuinely
  atomic large change or too loose to catch a padded one. Revisit if the
  policy doesn't hold in practice without enforcement.

## Consequences

- Needs more cross-PR coordination/sequencing than before - smaller PRs
  land more often, so whatever is planning the work (human or agent)
  needs to track what order dependent pieces land in and what's already
  merged vs. still pending. Not yet tooled; currently just a discipline
  ask.
- The PR template's "Related issue" section (already in
  `.github/pull_request_template.md`, added independently of this
  decision) becomes more useful under this policy: a real issue per
  discrete change gives each small PR a natural, single linking target
  instead of one issue trying to describe a bundle of unrelated work.

## Reference

This decision responds to an investigation into concurrent-PR conflict
surfaces and the evidence of shared-artifact and hot-file collisions.
