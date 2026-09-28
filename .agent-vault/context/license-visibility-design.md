---
type: context
watches:
  - path: src/girdle/hygiene.py
    hash: f8a9fc96e093a06b21744cca8d38e77cbbf9563e5682457b1d3d1096861d7cd9
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
