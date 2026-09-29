---
type: context
---

# Generated structural index causes AGENTS.md merge conflicts

Not committed scope yet - live design discussion, recorded so the
reasoning survives across sessions. See
[[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]]
for a related-but-distinct problem (vault note hash drift) that may share
a fix shape with this one - decide both together before implementing
either.

## Problem found

`indexer.py`'s structural index (the mechanically generated symbol
manifest injected into `AGENTS.md` between
`<!-- girdle:index:start -->`/`<!-- girdle:index:end -->`, checked via
`girdle index . --check AGENTS.md` in
[ci.yml:70](../../.github/workflows/ci.yml:70)) is regenerated wholesale
from the full repo tree every time, not incrementally diffed against what
changed. Two things compound to make this a heavy merge-conflict source
under concurrent PRs and Mergify's batched queue
(see [[.agent-vault/ci/merge-pipeline|merge-pipeline]]):

- **Whole-block rewrite**: any commit that regenerates the index replaces
  the entire fenced block in `AGENTS.md`
  ([indexer.py:383-399](../../src/girdle/indexer.py:383)), not just the
  line(s) for the file(s) it actually touched.
- **Reorder amplification**: entries are ranked by symbol count
  descending, tiebroken by path
  ([indexer.py:319](../../src/girdle/indexer.py:319)) - not stable path
  order. Adding or removing a single symbol in *any* file can shift where
  many other, unrelated files' entries fall in the list, so even a
  single-symbol change can touch a large fraction of the block's lines.

Combined: two PRs touching unrelated files each regenerate a full block
from their own tree state: PR A's regenerated block and PR B's can differ
across many lines neither PR intended to touch, well beyond git's normal
line-level three-way merge tolerance - producing a literal merge conflict
in `AGENTS.md`, not just a CI mismatch. This is a harder failure mode than
the vault hash problem: a merge conflict blocks Mergify's queue outright
(unmergeable) rather than failing a check that could in principle be
re-run.

## Evidence (subagent investigation, 2026-09-29)

**Confirmed real and currently acute, not theoretical.**

- Git history: 23 merges touch `AGENTS.md`; at least 11 non-merge commits
  are explicit conflict-resolution commits (`git log --all --grep="conflict" -i`),
  including `13e4b5d`, `a429566`, `74f0730`, `ccf9569`, `020ccb1`,
  `90bc769` ("resolve conflicts with master"). `403140a` is a
  conflict-resolution commit with **zero** net `AGENTS.md` diff - pure
  churn resolved to a no-op.
- `0a2ca10` and `84e0ffc`: Eric had to push **empty commits to force
  Mergify re-evaluation** because GitHub reported `MERGEABLE` but
  Mergify's queue check kept showing a stale `-conflict` state - the same
  stuck-`-conflict` symptom already documented in
  [[.agent-vault/ci/merge-pipeline|merge-pipeline]], now tied concretely
  to this mechanism.
- `c645155` ("mergify: nudge Copilot to resolve merge conflicts
  reactively") + `4e28287`: dedicated Mergify automation was built
  specifically because Copilot PRs were piling up and drifting into
  conflict against master - organizational evidence the rate was
  disruptive enough to warrant tooling, not a one-off.
- Nearly all conflict/merge activity clusters on 2026-09-28 and 09-29 -
  the same window `2e27568` (`batch_size: 3`) landed. Consistent with the
  batching theory increasing collision odds; causation not proven from
  log alone.
- **Reorder-amplification confirmed concretely**: `git show 74f0730 -- AGENTS.md` - a conflict where each side's PR touched only a handful of
  files, but the `AGENTS.md` diff rewrites 20+ unrelated entry lines
  (e.g. `test_hygiene.py`, `test_platform.py`,
  `tests/test_js_variants.py` all shift position) purely because symbol
  counts changed elsewhere. Sampled conflict-commit diff sizes:
  `a429566`=23, `74f0730`=34, `ccf9569`=20 changed lines in one
  wholesale-regenerated block - well beyond what either PR's actual file
  set would justify. `74f0730` is a good worked example to cite when
  scoping the stable-sort-order fix.
- Caveat: `gh pr view --json mergeable,mergeStateStatus` only reflects
  *current* PR state, so historical PR-level conflict status isn't
  independently queryable via the API - the git log conflict-commit trail
  above is the primary evidence source.

**Recommendation from the investigation**: prioritize this alongside the
vault-freshness redesign, not after it - it's already consumed manual
intervention (forced re-evaluations, dedicated bot automation) within the
last two days, not a "someday" problem.

## External validation (web research, 2026-09-29)

This is a known, named class of problem for checked-in generated
content, with a settled-enough fix pattern:

- **Byte-deterministic generation** is the standard remedy: drop any
  non-deterministic content (timestamps, hash-map/set iteration order),
  emit with a stable, explicit sort key, fixed indentation, and a fixed
  trailing-newline convention, then add a test that generates the file
  twice and asserts the two outputs are byte-identical. A directly
  analogous real case:
  [apeGmsh#1214](https://github.com/nmorabowen/apeGmsh/issues/1214)
  ("Deterministic studio/\_api_index.json") - a generated index file
  producing spurious diffs/conflicts, fixed by dropping timestamps and
  switching to `sort_keys=True` plus fixed formatting.
- General framing from [Jonathan Hall, "Avoid merge conflicts, don't
  manage them"](https://jhall.io/posts/2023-09-11-avoid-merge-conflicts/):
  the point isn't to get better at resolving conflicts in generated
  content, it's to structure the generation so the conflict-prone
  surface doesn't exist in the first place.

For this repo specifically: switching `indexer.py`'s sort from
symbol-count-descending to stable path order (already flagged as one
candidate below) is exactly this pattern - it removes the
reorder-amplification that makes an unrelated single-symbol change
touch dozens of lines. It doesn't by itself fix the wholesale-rewrite
half of the problem (two PRs touching *the same* file's own entry can
still conflict) - that half needs the diff-scoped-check approach shared
with [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]],
or, per the deterministic-generation pattern, accepting that a
same-file collision is a genuine, narrow conflict worth having (unlike
today's every-file-everywhere reordering noise).

## Not yet decided

Whether this wants the same fix shape as the vault redesign (stop
comparing/regenerating from global repo state; make the check
diff-scoped to what this PR's own commits touched) or a different
approach specific to the reordering behavior - e.g. stable path-order
sorting alone would remove the reorder-amplification half of the problem
without touching the wholesale-regeneration half. Needs scoping before
implementation; explicitly deferred until it's decided alongside
[[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]].

## Related

- [[.agent-vault/context/vault-freshness-redesign|vault-freshness-redesign]] -
  the related vault-note hash-drift problem, may share a fix shape.
- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the batching/queue
  mechanics that amplify both problems.
- [[.agent-vault/context/concurrent-pr-conflict-surface|concurrent-pr-conflict-surface]] -
  the synthesis note tying this, the vault redesign, and `schema.py` as a
  hot file together as one root cause, plus the decomposition/CI scoping
  hypothesis.
