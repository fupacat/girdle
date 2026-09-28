---
type: decision
---

# Dependabot queues use `branch_protection_injection_mode: merge`, not the default

## Context

Mergify's default queue mode (`queue`) injects the branch ruleset into
both queue *entry* and the merge gate. For Dependabot PRs this deadlocked:
entry required `check-success=Gitar`/`SonarCloud`, but those checks don't
reliably run on a Dependabot-authored branch at all (GitHub withholds some
secrets from Dependabot-triggered workflow runs). Confirmed live as
"Waiting for queue conditions," stuck permanently.

## Decision

Both Dependabot queues (`Dependabot`, `Dependabot-major`) use
`branch_protection_injection_mode: merge` (ruleset only enforced at the
merge gate, not entry) combined with `max_checks_retries: 1`, which forces
Mergify to always build its own `mergify/merge-queue/*` draft branch -
authored as `mergify`, not `dependabot[bot]` - giving Gitar/SonarCloud a
branch they actually run checks on.

## Alternatives considered

- **Default `queue` injection mode** - the status quo that produced the
  deadlock; not viable as-is.
- **The `default` (non-Dependabot) queue does not need this** - confirmed
  Gitar/SonarCloud already run natively on human/agent-authored branches,
  so the draft-branch workaround is Dependabot-specific, not applied
  universally.

## Consequences

- No `merge_bot_account` is needed for this mode - Mergify merges under
  its own identity once the ruleset is satisfied at the merge gate, unlike
  the `none` injection mode (briefly tried and reverted) which requires an
  explicit bot account.

## Reference

Full mechanism detail:
[[.agent-vault/ci/merge-pipeline|merge-pipeline]] (watches `.mergify.yml`).
