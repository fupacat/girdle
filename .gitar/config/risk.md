This repository-level guidance can only raise, never lower, the
organization-level risk assessment (Gitar's default behavior).

- Changes to `.mergify.yml`, `.github/dependabot.yml`, or any GitHub
  Actions workflow under `.github/workflows/` are always at least
  medium risk: they affect merge/CI automation for every other PR, not
  just their own.
- Changes to `src/girdle/schema.py` are always at least medium risk: it
  is the single source of truth for scan output (CLI JSON and the HTML
  dashboard both render `ScanResult`), so a change there can silently
  break both consumers at once.
