# Risk rubric

Risk guidance for reviewers (human or agent). It can only raise, never
lower, a PR's assessed risk.

Block and request changes for:

- security-sensitive mistakes, data loss, or privilege boundary violations
- broken behavior, failing logic, or missing required validation
- trust-boundary regressions in workflows handling untrusted PR content

Do not block for:

- style-only nits with no behavioral impact
- purely subjective preferences

Always at least medium risk:

- Changes to `.mergify.yml`, `.github/dependabot.yml`, or any GitHub
  Actions workflow under `.github/workflows/`: they affect merge/CI
  automation for every other PR, not just their own.
- Changes to `src/girdle/schema.py`: it is the single source of truth for
  scan output (CLI JSON and the HTML dashboard both render `ScanResult`),
  so a change there can silently break both consumers at once.
