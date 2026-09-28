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

Not every category can climb the same ladder:

1. **Verification ladder** (existing, for categories with a real execution
   proof - `tests`, `lint`, `coverage`, `ci_gating`): `configured` ->
   `verified`. Already implemented (`scan.py`'s `_verify`/`_run_and_record`,
   `--run` mode) - the gap was only that girdle's own CI never invoked it
   for the published dashboard/badge. See
   [issue #69](https://github.com/fupacat/girdle/issues/69) (filed,
   assigned to Copilot) to close that gap for girdle's own repo.

1. **Alignment ladder** (new, for prose/cross-file-consistency categories
   that have no execution proof - README, CONTRIBUTING, CODEOWNERS, agent
   instructions, `.editorconfig`/`.gitattributes`, vault notes):
   **bronze (configured) -> silver (adequate) -> gold (aligned)**.
   "Aligned" subsumes currency/freshness rather than needing a fourth rung

   - a vault note or AGENTS.md block that's stale relative to the code it
     documents isn't just old, it's *disagreeing* with the current repo
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

## Open, not yet resolved

- Concrete "adequate" (silver) bar per category - named as a concept, not
  yet defined for any specific category. README has a partial existing
  heuristic (`check_readme` already distinguishes an empty stub from real
  content); CODEOWNERS, CONTRIBUTING, AGENTS.md do not have a bar defined
  yet (more than one entry? real paths vs. a bare wildcard? something
  else?).
- Concrete "aligned" (gold) evidence source per new category - `align.py`
  and `vault.py` are the model for the categories they already cover;
  not yet mapped for CODEOWNERS, LICENSE, or the two new gap categories
  above.
- Whether the alignment ladder's silver/gold visual language (bronze/
  silver/gold) should look the same on the dashboard as the verification
  ladder's configured/verified, or be visually distinct so a viewer can
  tell which kind of claim a given badge is making.

## Related

- [[.agent-vault/ci/merge-pipeline]] - a similarly-shaped "make the
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
