---
type: brainstorm
---

# Dashboard scoring redesign: bronze/silver/gold alignment ladder

Checkpoint of an in-progress brainstorm (not yet a decision - no code
changed as a result of this note). Triggered by a real complaint: girdle's
own dashboard shows most categories as `configured` (yellow), which reads
as a warning even on a well-built repo, because most categories have no
"verified" rung to climb to in the first place.

## Where this started

Market research on how comparable tools present scores, done before
narrowing:

- **Lighthouse** (red/orange/green) calibrates its bands against
  real-world percentile data - orange means "mediocre relative to the
  web," not "missing a technical step." Girdle's yellow means something
  much narrower and more forgivable ("the tool exists, we haven't watched
  it run"), so the same color reads as a much harsher verdict than
  intended.
- **OpenSSF Best Practices Badge** uses a ladder (Passing -> Silver ->
  Gold) instead of traffic lights - not having gold reads as "you've
  achieved X, here's what's next," not a warning.
- **SonarQube** shows one binary pass/fail quality gate up top, with
  granular metrics as plain numbers underneath - it doesn't alarm-color
  every sub-metric.
- **Socket.dev** shows five separate 0-100 numeric scores per dimension,
  no traffic lights at all.

Settled direction: a ladder (bronze/silver/gold), not a palette change -
this is a semantics problem (what does the middle rung mean), not a color
problem.

## The two-ladder split

> **Superseded as the overall scoring mechanism** by "Decision:
> percentage-of-checks-passed model supersedes the strict ladder" later
> in this note. The per-category adequate/aligned bars and the
> execution-provability distinction below are still valid and feed into
> the newer model as the check list itself - read on for that reasoning,
> but the rigid bronze/silver/gold-per-category progression described
> here is not the final design.

Not every category can climb the same ladder:

1. **Verification ladder** (existing, for categories with a real execution
   proof - `tests`, `lint`, `coverage` only, confirmed against
   `run_commands` in every detector; `ci_gating` does NOT belong here
   despite an earlier draft of this note claiming otherwise - it has no
   execution path and is capped at absent/configured like everything
   else in the taxonomy below): `configured` -> `verified`. Already
   implemented (`scan.py`'s `_verify`/`_run_and_record`,
   `--run` mode) - the gap was only that girdle's own CI never invoked it
   for the published dashboard/badge. See
   [issue #69](https://github.com/fupacat/girdle/issues/69) (filed,
   assigned to Copilot) to close that gap for girdle's own repo.

1. **Alignment ladder** (new, for prose/cross-file-consistency categories
   that have no execution proof - README, CONTRIBUTING, CODEOWNERS, agent
   instructions, `.editorconfig`/`.gitattributes`, vault notes):
   **bronze (configured) -> silver (adequate) -> gold (aligned)**.
   "Aligned" subsumes currency/freshness rather than needing a fourth
   rung; a vault note or AGENTS.md block that's stale relative to the code
   it documents isn't just old, it's *disagreeing* with the current repo
   state, which is the same failure mode as any other alignment break.
   `vault.py`'s existing hash-based staleness check already treats
   staleness this way.

This is where girdle's actual differentiator (`align.py`'s cross-file
derivation, `vault.py`'s staleness tracking) becomes the scoring mechanism
itself, instead of sitting off to the side as separate CLI subcommands
disconnected from the main scan score.

## Hard constraint settled: deterministic scoring only

Every scored rung must come from a deterministic check (hash comparison,
parse, pattern match) - never an LLM judgment. `audit.py`'s agent-invoked
instruction-quality review stays a separate, opt-in *assistant* that helps
a repo climb the ladder (e.g., improve AGENTS.md content), not a scored
input itself. Reasoning: LLM judgment is slow, costs money, and isn't
deterministic run-to-run - none of which is acceptable for a score that's
supposed to be reproducible and comparable across runs.

## Category taxonomy, reworked

Starting from girdle's existing `hygiene.py` checks (already
platform-generalized - e.g. `check_agent_instructions` already accepts
`AGENTS.md`/`CLAUDE.md`/`copilot-instructions.md` as the same underlying
category) and revised in this session:

- **Agent-facing context**: agent instructions, agent sandbox bootstrap -
  unchanged, already generalized.
- **Human-facing governance**: README, CONTRIBUTING, CODEOWNERS -
  unchanged.
- **Pulled OUT of the alignment cluster - unconditional bronze on its
  own**: `.gitignore`. It has independent value regardless of any
  alignment question (every ecosystem generates artifacts that shouldn't
  be committed) - unlike the other two dotfiles below, "configured but
  nothing to align against" is not a coherent excuse for this one.
- **Stays alignment-only, deliberately**: `.editorconfig`,
  `.gitattributes`. Their entire value proposition *is* "does this agree
  with the detected formatter/CI config" - a repo with one strict
  formatter enforced in CI has genuinely little use for `.editorconfig`
  (the formatter already *is* the enforcement mechanism). `align.py`
  already encodes this correctly: no detected formatter means no plan is
  generated at all, not a missing-category flag. Scoring these as
  "should exist unconditionally" would create false positives.
- **New gaps identified, not yet built**:
  - Structural/repo index (a mechanically-generated code map for agent
    context) - what `girdle index` does for girdle's own repo, not yet
    scored for *other* repos. Ties back to the vault's own
    [[Agent-Ready Repository Design]] research (Vercel's 100%-vs-53%
    deterministic-index result was the highest-evidence finding there).
  - Design/decision notes (an ADR-equivalent) - what `.agent-vault/` is
    for girdle itself; not yet a scored category for other repos.
- **New visibility-conditional category**: **LICENSE**, gated on the repo
  being public (the only one of this class with a real legal
  consequence - no LICENSE on a public repo defaults to all-rights-reserved).
  Priority add.
- **Named but deliberately deferred** (same conditional class as LICENSE,
  lower priority): SECURITY.md, CODE_OF_CONDUCT.md, issue/PR templates,
  FUNDING.yml - these gate more on "accepts external contributions" than
  strictly public/private, and don't carry LICENSE's legal-ambiguity
  consequence.

## Per-category deterministic checks - what "adequate"/"aligned" can concretely mean

Working through the taxonomy category by category to answer the open
"what's the actual bar" question. One thing fell out of doing this: several
categories share the *exact same* underlying mechanism - extract
code-fenced commands/paths from prose, diff against what's actually
configured (manifests, CI, pre-commit) - so this is shared infrastructure
to build once, not N separate detectors.

- **README**: adequate = has recognizable installation and basic-usage
  sections (lenient synonym/heading matching - "Install"/"Getting
  Started"/"Setup", "Usage"/"Quickstart"/"Examples" - not a single exact
  heading, to avoid false negatives on unconventional styles), plus
  absence of unedited generator-template boilerplate. Aligned = the
  command-extraction-and-diff mechanism above; also badge targets (a
  Codecov badge with no Codecov config anywhere is checkable drift).
- **CONTRIBUTING**: adequate = non-stub length. Aligned = same
  command-extraction-and-diff mechanism as README - and this exact
  failure mode bit this repo directly this session (CONTRIBUTING.md's
  branch-protection section went stale and needed a human to notice and
  rewrite it by hand - this check would have caught it automatically).
- **CODEOWNERS**: adequate = more than a single bare `*` entry. Aligned =
  cross-reference referenced usernames/teams against the GitHub API's
  actual collaborator/team list (precedent: `platform.py` already makes
  platform API calls), and referenced paths against the actual tree - a
  stale entry pointing at a deleted directory is directly checkable.
- **`.gitignore`**: already well-covered. New alignment angle: is
  anything in `git ls-files` that matches a pattern the file *should*
  cover but doesn't - generalizing the existing `is_lockfile_gitignored`
  check beyond just lockfiles.
- **`.editorconfig`/`.gitattributes`**: already fully covered by
  `align.py`'s derivation-vs-actual-content comparison. Nothing new.
- **Dependency monitoring**: adequate = config covers every detected
  ecosystem's manifest type. Aligned/current = has a `dependabot[bot]`
  PR/commit within a recent window (GitHub API) - evidence the automation
  is actually firing, not just configured on paper.
- **LICENSE**: adequate = a real, recognized license text, not empty or a
  placeholder - **`licensee` (the exact library GitHub itself uses for
  the repo-page license badge) does this via deterministic text-fingerprint
  matching against known SPDX texts, no LLM involved.** Aligned = the
  identified license matches the `license` field in
  `package.json`/`pyproject.toml`/`Cargo.toml` - a LICENSE saying MIT
  while `pyproject.toml` declares Apache-2.0 is a real, checkable
  mismatch.
- **Agent instructions**: verified the actual AGENTS.md spec rather than
  assuming - it "standardises a filename and a location, not a format":
  no required fields, no schema, no frontmatter. So there's no real
  format-conformance dimension to check (girdle's own index/guidance
  conventions can't conflict with a spec that imposes none) - a
  "recommended sections present" check would be the same soft heuristic
  as README's, not true spec compliance. One thing the spec *does*
  mandate, and this is a genuine spec-grounded alignment check: in a
  monorepo, "place an AGENTS.md in each package - the closest file wins."
  So: does a detected monorepo (multiple ecosystem roots) have an
  AGENTS.md per subproject, or one root file the spec's own resolution
  rule says won't reliably reach nested packages? Also (unique to this
  category): when a repo has more than one instruction file (AGENTS.md
  *and* CLAUDE.md *and* copilot-instructions.md), do they agree with each
  other - a cross-file alignment check with no README/CONTRIBUTING
  equivalent. Also note the *inverted* adequacy heuristic vs. every other
  category: the vault's own research found verbosity actively harmful, so
  "too long/prose-heavy instead of pointing at a generated index" is
  itself a flaggable condition, not just "too short."
- **Agent sandbox bootstrap**: already covered for presence/wiring. New
  alignment angle: does the bootstrap step actually install/run the
  *same* checks `.pre-commit-config.yaml` defines, or a silently
  diverging subset.
- **Structural/repo index**: the most deterministic category of all -
  it's literally "regenerate and diff," exactly what `girdle index --check`
  already does for girdle's own repo. Needs generalizing to score *other*
  repos, not new detection logic.
- **Design/decision notes - genuinely different confidence class than
  every other category above.** Verified rather than assumed: there is
  no dominant convention the way there is for LICENSE/README/AGENTS.md.
  `doc/adr/` (Nygard/adr-tools) is the closest thing to a standard, but
  MADR, `docs/decisions/`, numbered-file variants, and ad-hoc single
  files all coexist with no clear winner - and a repo can legitimately
  keep decisions in GitHub Discussions or a wiki, invisible to a
  git-tree scanner entirely. Detection here can only ever be "no
  recognized convention found at any known path," never a confident
  "doesn't have design notes" the way LICENSE-absent can be confident.
  This category should probably render with visibly lower confidence
  than the rest of the taxonomy, not a flat absent/configured/aligned
  claim like everything else.

## Universal vs. agentic-specific split

Cutting the taxonomy above along a second axis - does this category apply
to any repo, or specifically because agents work on it:

- **Universal**: README, CONTRIBUTING, CODEOWNERS, `.gitignore`,
  `.editorconfig`/`.gitattributes`, dependency monitoring, LICENSE,
  `ci_gating`, `reproducibility`, `precommit`, the deferred
  SECURITY.md/CODE_OF_CONDUCT/templates/FUNDING.yml cluster, and the
  verification ladder itself (tests/lint/coverage only - see correction
  above; this predates agentic development entirely).
- **Agentic-specific**: agent instructions (AGENTS.md/CLAUDE.md/
  copilot-instructions.md), agent sandbox bootstrap.
- **Ambiguous, called out rather than forced into one bucket**:
  - Structural/repo index - the evidence behind it (Vercel's
    100%-vs-53% result) is specifically about *agent* task success from
    deterministic context-loading. Leaning agentic-specific.
  - Design/decision notes (ADR-equivalent) - the *concept* is
    decades older than agents and useful to any team, but the specific
    hash-linked `watches` enforcement mechanism girdle uses is solving a
    problem that's much sharper in an agent-heavy workflow (an agent
    won't carry yesterday's rationale the way a human teammate might).
    Category is universal; the enforcement mechanism is agentic-relevant.

## Personal/machine-local config leaked into version control

New category, prompted by asking whether `.claude/`, `.codex/`, `.copilot/`
directories should be scored as signals of agentic-tool adoption. Verified
per-tool behavior (not assumed) before concluding anything:

- **`.github/`** - never auto-generated by GitHub itself. Always
  deliberate. Already fully covered by existing checks.
- **`.codex/`** - `.codex/config.toml` is only created when someone adds
  project-specific overrides, not on first run. Safe to treat presence as
  deliberate. Codex's *personal* profile config lives at
  `~/.codex/<profile>.toml` - outside the repo entirely, so it cannot leak
  into a commit by construction.
- **`.claude/` - mixed, needs care.** `.claude/settings.local.json` is
  auto-created the instant a user approves any "don't ask again"
  permission - incidental, not deliberate team setup - and Claude Code
  auto-adds a gitignore rule for it. `.claude/settings.json` (checked-in,
  shared) and `.claude/commands/`/`agents/`/`skills/` are deliberate. A
  detector needs to check for the specific deliberate paths, not
  directory presence alone, or a stray committed `settings.local.json`
  false-positives as "configured." Structurally the riskiest of the three
  tools here: it's the only one that writes personal state *into* the
  project directory by design, relying on gitignore (a fallible,
  editable file) to keep it out - Codex's design makes the leak class of
  bug impossible, Claude's makes it merely unlikely.
- **`.copilot/` doesn't apply to a repo at all.** Copilot's repo-scoped
  config actually lives under `.github/` (`copilot-instructions.md`,
  `instructions/`, `skills/`, `agents/`, `hooks/`). `~/.copilot/` is a
  user-level, home-directory location for personal preferences - never a
  repo-level convention. A `.copilot/` folder in a repo isn't a signal
  Copilot itself produces.

This didn't become a new taxonomy category for "agentic tool adoption" -
it sharpens detection for the two agentic-specific categories already
named above (look for the specific deliberate file, not directory
presence). But it surfaced a genuinely new, separate category: **personal/
machine-local artifacts committed that shouldn't be** (`.claude/settings.local.json`,
`.idea/`, `.DS_Store`, `Thumbs.db`, and more seriously `.env`/credential
files/private keys). Precedent already exists in girdle for this shape of
check, just narrowly scoped: `is_lockfile_gitignored`
(python_common.py/js_common.py) already flags a lockfile that should be
gitignored but isn't.

**Severity split, settled**: committed secrets vs. general hygiene noise
are not the same severity and get routed through two different existing
mechanisms rather than one new penalty system:

- **Secrets -> reuse the existing weakest-link gating.** Girdle's overall
  score is already computed as the minimum across categories (category
  min gates the ecosystem, weakest ecosystem gates the overall score). A
  secrets-detected finding reporting as its own category at `ABSENT`
  automatically drags the whole repo's overall score to the floor via
  gating that already exists - no new override mechanism needed.
- **Hygiene noise -> `ScanResult.warnings`.** A stray `.DS_Store`
  shouldn't drag a repo to the same floor as a structurally missing
  README/CI/tests - those aren't comparable severities, and min-gating
  can't tell them apart if both just report as `ABSENT`. Girdle already
  has a non-gating, advisory mechanism for exactly this (currently used
  for things like "no known ecosystem detected"). Settled: hygiene noise
  doesn't represent anything that actually impacts trust in the repo, so
  advisory-only is correct, not a gap to fill later.

## Full category enumeration (ground truth, read from the code)

Every category girdle actually computes today, enumerated directly from
`run_commands` across all detectors and `build_hygiene` - 15 categories
total, not worked from memory. This is what grounded the `ci_gating`
correction above.

| Category                                               | Ladder                                                                                                       | Universal/Agentic |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ----------------- |
| `tests`, `lint`, `coverage` (per ecosystem)            | Verification (real)                                                                                          | Universal         |
| `ci_gating`                                            | Alignment-eligible, capped today                                                                             | Universal         |
| `reproducibility`                                      | Alignment-eligible, capped today                                                                             | Universal         |
| `editorconfig`, `gitattributes`                        | Alignment-only (settled)                                                                                     | Universal         |
| `gitignore`                                            | Unconditional bronze, no ladder                                                                              | Universal         |
| `precommit`                                            | Alignment-eligible, capped today                                                                             | Universal         |
| `agent_sandbox_bootstrap`                              | Alignment-eligible (bar defined)                                                                             | Agentic           |
| `codeowners`                                           | Alignment-eligible (bar defined)                                                                             | Universal         |
| `agent_instructions`                                   | Alignment-eligible (bar defined)                                                                             | Agentic           |
| `readme`, `contributing`                               | Alignment-eligible (bar defined)                                                                             | Universal         |
| `dependency_monitoring`                                | Alignment-eligible (bar defined)                                                                             | Universal         |
| LICENSE *(not yet implemented)*                        | Alignment-eligible (bar defined)                                                                             | Universal         |
| structural index, design notes *(not yet implemented)* | New gap pillars                                                                                              | Agentic/mixed     |
| personal-config-leak/secrets *(not yet implemented)*   | Not a ladder (warnings/min-gate)                                                                             | Universal         |
| `platform.py` branch-protection/ruleset checks         | **Doesn't fit the tier model at all** - separate `PlatformResult` structure, not `CategoryResult`/tier-based | Universal         |

Doing this enumeration surfaced three new alignment-check candidates not
previously named anywhere in this note, added to the backlog:

- `ci_gating` vs. `tests`: does the CI-detected test command actually
  match the `tests` category's own configured command?
- `reproducibility`: does the lockfile actually match the manifest (no
  version drift between e.g. `package.json` and `package-lock.json`)?
- `precommit` vs. CI: does pre-commit wire the *same* checks CI actually
  runs, or a silently diverging subset?

- ~~**Scope note for the Option A dashboard update** (settled direction -
  recolor the existing `configured` state away from alarm-yellow, no new
  labels, no new detection - see below): only `tests`/`lint`/`coverage` can
  ever reach the green "verified" state today. The other 12 tier-based
  categories in the table above only ever show absent/configured, so their
  `configured` color is exactly what Option A needs to fix.~~ - dropped.

## Comparison against Factory.ai's Agent Readiness rubric

Prompted by recalling "community guidance" for this kind of scoring - it
turned out to mean Factory.ai's rubric specifically (OKF vault:
[[Factory.ai Agent Readiness]], previously an unresearched `status: draft`
stub - actually researched now rather than left as a placeholder).
Corrected the stub's own numbers in the process: **9 pillars**, not 8 -
Style & Validation, Build System, Testing, Documentation, Development
Environment, Debugging & Observability, Security, Task Discovery, Product
& Experimentation - rolling up to 5 maturity levels, gated by **passing
80% of a level's criteria**, not 100%.

Pillar-by-pillar against what this brainstorm has built:

- **Style & Validation, Testing** - already covered (verification ladder).
- **Documentation** - Factory treats this as one axis; girdle already
  splits it more finely (human-facing governance vs. agent-facing
  context as separate pillars) - a deliberate difference, not a gap.
- **Development Environment** - already covered under different names
  (girdle's existing `reproducibility` category, referenced in `scan.py`'s
  own docstring, plus agent sandbox bootstrap).
- **Security** - mostly covered (CODEOWNERS, branch protection via
  `platform.py`). Secret scanning specifically is exactly the
  personal-config-leak category designed independently earlier in this
  same session - good cross-validation against a real competitor's rubric.
- **Build System** (deterministic build commands) - **possible gap**, not
  yet confirmed whether this is folded into an existing per-ecosystem
  check or genuinely missing from girdle's taxonomy.
- **Debugging & Observability** (structured logging, tracing, metrics) -
  **genuine gap**. Girdle has nothing like this today.
- **Task Discovery** (infrastructure for an agent to autonomously find
  and scope work, not just human-facing issue templates) - **genuine
  gap, and a new angle** not discussed anywhere else in this brainstorm.
- **Product & Experimentation** (feature-impact measurement) - out of
  scope for girdle entirely, not a gap - different product category.

Two data points relevant to this brainstorm's own open questions:
Factory's 80%-of-criteria-per-level rule is a real answer to the deferred
"aggregate vs. per-category" scoring question (a percentage threshold per
tier, not pure minimum-gating). Factory also scores "at repository scope
and application scope (per-app in monorepos)" - independent validation
of the AGENTS.md per-monorepo-package concern raised earlier in this note.

Candidates (Build System confirmation, Debugging & Observability, Task
Discovery) moved to a tracked backlog rather than left buried in this
narrative note - see
[[.agent-vault/context/dashboard-pillars-backlog|dashboard-pillars-backlog]].

## Decision: percentage-of-checks-passed model supersedes the strict ladder

**This supersedes "The two-ladder split" and the bronze/silver/gold
framing earlier in this note as the overall scoring mechanism.** That
earlier reasoning (per-category adequate/aligned bars, the two-ladder
split by execution-provability) is still valid and kept - it now feeds
*into* this model as the check list, rather than defining a rigid 3-rung
progression per category.

**The model**: categories are many-to-many *groupings* of checks, not a
strict partition - a single check (e.g. `agent_instructions`) can count
toward multiple categories (e.g. "Agent-facing context" and
"Documentation") simultaneously. Score = percentage of applicable checks
passed, computed **both per-category and overall** - this resolves the
earlier-deferred "aggregate vs. per-category" question by doing both, not
choosing one.

- **Double-counting a check across categories is intentional, not a bug
  to dedupe.** It's a natural weighting mechanism: a check that's
  relevant to more categories pulls more weight on the overall score
  automatically, without needing a separate manually-assigned importance
  weight. No special-case dedup logic needed anywhere.
- **Color model: neutral by default, not alarmed, until either (a) a
  badge tier is earned, or (b) something actively harmful is found.**
  Nothing reads as a warning just for being incomplete - `absent`
  categories show 0%/neutral with an outstanding-items list, the same as
  a partially-complete category, **not red**. Red is reserved
  specifically for active-harm findings: committed secrets, and (newly
  identified in this exchange) evidence of malicious/poisoned agent
  instructions (prompt-injection-style content hidden in AGENTS.md/
  CLAUDE.md - a real, growing threat class specific to repos agents
  work in, not previously named anywhere in this brainstorm). This is a
  deliberate departure from most scoring tools, which typically redden
  "missing README" even though absence isn't actually harmful, just
  incomplete.
- **Check difficulty/rarity is a static property of the check itself,
  independent of which category(ies) count it** - matches Factory.ai's
  model, where each criterion has one difficulty tier regardless of
  context. Tiers gate badge levels (a repo needs some threshold of
  basic-tier checks passed before intermediate/advanced checks count
  toward a higher badge, echoing Factory's 80%-of-a-level rule rather
  than requiring every single check).
- **Tier assignment is manually judgment-calibrated for v1**, not
  empirically derived. This closes a loop back to this note's very first
  research finding: Lighthouse's color bands are calibrated against real
  percentile data (HTTP Archive), which is the model being gestured at
  here ("README is likely, CI is less likely, security/SAST is
  uncommon") - but girdle has no infrastructure to scan a large sample of
  real repos the way Lighthouse can. Empirical calibration is an
  explicit stretch goal, not a v1 blocker. Factory.ai's own tiers are
  presumably hand-curated too, not published as empirically derived
  either.

**Draft tier assignment** (first pass, reacted to and confirmed in this
session - not yet final/exhaustive as new checks get added):

- **Basic** (near-universal, often scaffolded by GitHub itself at repo
  creation): `readme`, `gitignore`, LICENSE, `contributing`
- **Intermediate** (deliberate setup, moderately common): `tests`,
  `lint`, `coverage`, `ci_gating`, `codeowners`, `dependency_monitoring`,
  `editorconfig`/`gitattributes`, `precommit`
- **Advanced/rare**: SAST/static-analysis-configured (**new check
  candidate**, distinct from `lint` - girdle dogfoods SonarCloud itself
  but doesn't score "does a repo have CodeQL/Semgrep/similar configured"
  as its own category today), `agent_instructions`,
  `agent_sandbox_bootstrap`, `reproducibility`, structural index,
  design/decision notes, Debugging & Observability, Task Discovery

**Extensibility payoff, the actual point of this model over the rigid
ladder**: as new checks get introduced, they're just added to whichever
category/tier they belong in, and scores recalculate - no need to
redesign a 3-rung progression for every category a new check touches.

## Decision: ship the color fix now, defer the ladder rebrand (dropped)

> Dropped, confirmed moot: the percentage-of-checks-passed model above
> answers the same complaint more completely, so this was never shipped.
> Kept for the record, not as live guidance.

Converged on a concrete near-term direction rather than waiting for the
full alignment ladder to be built. Two options were weighed:

- **Option A (chosen)**: pure color fix, no new labels. Keep the existing
  `absent`/`configured`/`verified` labels exactly as they are today; stop
  coloring `configured` as an alarm (move it off yellow to a neutral
  tone), reserve red for genuine gaps (`absent`) and green for proven
  (`verified`). Ships immediately, zero new detection logic, directly
  fixes the original complaint that prompted this whole brainstorm.
- **Option B (rejected, for now)**: introduce bronze/silver/gold visual
  language immediately, with silver/gold rendered as greyed-out
  "not yet checked" placeholders on the 12 categories that can't back
  them with real data yet (everything except tests/lint/coverage - see
  the enumeration above). Rejected because it risks reading as a broken
  or incomplete ladder rather than a deliberate preview, and commits to
  naming/visual design before the detectors that would make it
  meaningful actually exist.

The bronze/silver/gold rebrand itself is *not* abandoned - it's
sequenced to land together with enough real silver/gold detectors
(per-category work tracked in
[[.agent-vault/context/dashboard-pillars-backlog|dashboard-pillars-backlog]])
that the ladder means something everywhere it appears, rather than
being introduced as a visibly incomplete preview.

## Open, not yet resolved

- Concrete adequate/aligned bars are now defined per-category (see the
  section above) for README, CONTRIBUTING, CODEOWNERS, `.gitignore`,
  dependency monitoring, LICENSE, agent instructions, agent sandbox
  bootstrap, and the structural-index gap. Still genuinely unresolved:
  design/decision notes, which can't carry the same confidence as the
  rest (no dominant file convention - see above).
- **Shared command-extraction-and-diff mechanism - design settled at the
  scope level.** Explicitly out of scope: validating command *syntax* or
  full command-line correctness (README says `pytest --cov`, CI actually
  runs `pytest --cov --cov-report=xml` - a reasonable simplification, not
  a mismatch worth flagging; a strict flag-for-flag matcher would cry
  wolf on legitimate documentation choices and erode trust in the tool).
  What's in scope: **presence and staleness/incorrectness of the
  referenced name or path**, nothing more. Concretely, every command type
  reduces to the same shape of check - extract a name/path token, check
  it against the relevant manifest or filesystem: `npm run build` ->
  does `build` exist in `package.json`'s `scripts`; `python scripts/deploy.py` -> does `scripts/deploy.py` exist as a file; `make test` -> does a `test` target exist. One general mechanism, not N
  bespoke per-tool validators.
  - **Extraction confidence tiers**: fenced blocks tagged
    `bash`/`sh`/`shell`/`console`/`zsh`, with `$`/`>`-prefixed lines, are
    high-confidence. Untagged fenced blocks and inline single-backtick
    spans are excluded from v1 - too noisy (could be a filename, a
    variable, a package name, not a runnable command).
  - **Known real limitation, accepted rather than solved**: distinguishing
    a command line from pasted terminal *output* inside the same
    shell-tagged block isn't fully reliable without a prompt marker - some
    READMEs paste raw output directly below a command with no
    distinguishing syntax. Will produce some false negatives; acceptable.
  - **Filtering layer**: a static, non-exhaustive allowlist of generic
    shell vocabulary (git, cd, npm, python, curl, docker, make, etc.) -
    its only job is recognizing commands that are generically valid
    regardless of this repo's own config (`git clone ...`), so they're
    never checked against repo-specific manifests at all.
- `licensee`-style deterministic license-text fingerprinting is a new
  dependency to evaluate (language/packaging fit, licensing itself) -
  not yet checked whether a suitable library exists for girdle's Python
  stack specifically or if it would mean shelling out / vendoring
  license-text data.
- Whether the alignment ladder's silver/gold visual language (bronze/
  silver/gold) should look the same on the dashboard as the verification
  ladder's configured/verified, or be visually distinct so a viewer can
  tell which kind of claim a given badge is making.
- The personal/machine-local-artifact category needs its own detector
  design (per-tool known-pattern list: `.claude/settings.local.json`,
  `.idea/`, `.DS_Store`, `.env`, etc.) and a decision on where secrets
  detection draws its line - a real secret-scanning implementation
  (entropy/pattern-based) is a much bigger scope question than the
  gitignore-style presence check this brainstorm has been assuming.
- ~~Whether "silver" is scored per-category or as some aggregate across
  categories~~ - resolved: both (see "Decision: percentage-of-checks-passed
  model supersedes the strict ladder").

## Related

- [[merge-pipeline]] - a similarly-shaped "make the
  settled reasoning discoverable, not just chat history" note, same
  session's broader documentation pass.
- OKF vault: [[Agent-Ready Repository Design]] - the structural-index
  evidence this brainstorm leans on for the new gap category.

## Sources (from the market-research pass)

- [OpenSSF Scorecard](https://scorecard.dev/) - 0-10 numeric score per check
- [OpenSSF Best Practices Badge](https://www.bestpractices.dev/) - Passing/Silver/Gold tier ladder
- [SonarQube Cloud quality gates](https://docs.sonarsource.com/sonarqube-cloud/standards/managing-quality-gates/introduction-to-quality-gates)
- [Socket.dev package scores](https://docs.socket.dev/docs/package-scores) - five 0-100 dimension scores, no traffic lights
- [Lighthouse scoring](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring) - percentile-calibrated red/orange/green bands
