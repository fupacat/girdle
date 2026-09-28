---
type: context
watches:
  - path: src/girdle/hygiene.py
    hash: dd61ff48972ee422d827eeeb0bb4029015af2aa7b24251c437ecb6bcc8f9c06a
stale: false
---

# LICENSE check and visibility design

## Context

The LICENSE hygiene check is conditional on repository visibility: public
repositories are expected to provide a recognized license, while private and
internal repositories are not scored. An unknown visibility is treated as
not applicable rather than guessed.

## Decisions

Visibility is resolved in this order:

1. Use a valid `GITHUB_REPOSITORY_VISIBILITY` value when supplied.
1. Read `repository.visibility` from the Actions event payload at
   `GITHUB_EVENT_PATH`.
1. If neither source provides a recognized value, make a best-effort
   `gh repo view --json visibility` probe. Failure to determine visibility
   leaves the check not applicable.

After visibility makes the check applicable, the check recognizes complete
license texts and compares any recognized manifest license declarations with
the detected license. Alias keys are normalized using the same text
normalization as incoming declarations, so SPDX spellings such as `MPL-2.0`
match both manifest fields and license text.

## Consequences

- The `gh` probe is a fallback for local environments and workflows without
  a usable visibility value; it is not required when either environment source
  provides visibility.
- Manifest declarations that identify a different recognized license from
  the root LICENSE cause the check to report a mismatch.
- BSD-2-Clause and BSD-3-Clause share their first two clauses, so detection
  can't just check "does BSD-3's signature match" first - `_detect_license_id`
  matches on the shared BSD-2 signature, then looks for the extra "neither
  the name of ... nor the names of" clause to upgrade the match to BSD-3.
  Checking BSD-3's fuller signature first (the original approach) missed
  real BSD-3 texts whose third clause was phrased slightly differently.
- `ScanResult.check_statuses` only counts a hygiene check as "seen" when
  `HygieneResult.is_applicable(key)` is true - a not-applicable check (e.g.
  LICENSE on a private repo, see above) must be excluded from scoring
  entirely, not counted as seen-and-passing or seen-and-failing.
