---
type: environment
reviewed_at: 2026-09-28
---

# External services girdle depends on

Generic facts only, per this vault's own rule - no account IDs, hostnames,
or credentials here (those stay in the private OKF vault). This is a
quick-reference index; the *why* behind each one lives in the linked notes.

- **GitHub** - source hosting, Issues (native `blockedBy`/`blocking`
  dependency relations, sub-issues), a single repo-wide Project (`Status`
  field extended to a 5-state lifecycle, built-in `Parent issue` field for
  initiative grouping), GitHub Actions (CI, scheduled automation), GitHub
  Pages (dashboard + badge JSON hosting).
- **Mergify** - merge queue orchestration. See
  [[.agent-vault/ci/merge-pipeline|merge-pipeline]].
- **Gitar** (Sonar) - AI PR review and CI-failure auto-fix. Same note as
  above.
- **SonarCloud** (Sonar) - static-analysis quality gate.
- **GitHub Copilot** - coding-agent PR authorship (assigned via issues),
  plus a backup/manual-only PR review path.

## Related

- [[.agent-vault/ci/merge-pipeline|merge-pipeline]] - the operational
  detail behind the GitHub/Mergify/Gitar/SonarCloud/Copilot relationship.
- [[.agent-vault/decisions/merge-pipeline-tool-roles-and-paths|merge-pipeline-tool-roles-and-paths]] -
  the ADR anchor for why these specific roles were assigned.
