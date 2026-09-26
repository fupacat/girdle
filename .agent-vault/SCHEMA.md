# .agent-vault schema

A repo-scoped knowledge base, separate from AGENTS.md (operational
instructions for working in this repo) and the structural index
(mechanically derived from code, never hand-written). This is where the
*why* lives: design rationale, decisions, research, and reference material
that's specific to this repo rather than to Eric's broader work (that
belongs in the OKF vault instead).

## Folders / note types

| Folder | Type | Watches code? | Freshness model |
|---|---|---|---|
| `decisions/` | `decision` | No | Immutable once written, like an ADR. Superseded by a new note, never edited to reverse itself. |
| `context/` | `context` | Optional | Living "how/why this is shaped this way" documentation. The main candidate for `watches`. |
| `research/` | `research` | No | Point-in-time findings, spikes, benchmarks. Dated, never kept "in sync." |
| `brainstorm/` | `brainstorm` | No | A snapshot of a discussion, not living documentation. |
| `data-models/` | `data-model` | Optional | Schema/data-model documentation - drift-prone against migrations/schema files. |
| `diagrams/` | `diagram` | Optional | Mermaid-in-markdown, not binary images - stays git-diffable. |
| `ci/` | `ci` | Optional | Can watch `.github/workflows/*.yml` directly. |
| `environment/` | `environment` | Rarely | Generic facts only - hosting provider, services used, architecture-level shape. **No account IDs, hostnames, credentials, or anything secret-adjacent** - that stays out of this (public) repo entirely, in the private OKF vault instead. |
| `deployment/` | `deployment` | Sometimes | Same no-secrets rule as `environment/`. Watchable only if it references specific in-repo IaC/config files. |

## Frontmatter

```yaml
---
type: context            # one of the types above
watches:                 # optional - omit entirely for point-in-time notes
  - path: src/girdle/coverage_gate.py
    symbol: detect_gate   # optional - omit to watch the whole file instead
    hash: <sha256>        # recorded automatically, never hand-written
stale: false              # set to true automatically when a watch's hash no longer matches
reviewed_at: 2026-09-26   # optional, for notes without watches (environment/deployment) where
                          # freshness can only be human-attested, not hash-verified
---
```

## Workflow

- **Writing a new note**: pick the folder matching its type. Only add
  `watches` if the note is actually living documentation of something that
  can drift - most notes (decisions, research, brainstorm) don't need it.
- **Changing code a note watches**: edit the note in the *same commit* as
  the code change. The pre-commit hook (`girdle notes check`) recomputes
  the watched hash and auto-updates the note's frontmatter for you, since
  the note is already part of the commit - no manual hash editing required.
- **Confirming a note is still accurate, unchanged**: run
  `girdle notes ack path/to/note.md` before committing. This records the
  current hash and stages the note without requiring a content edit -
  distinct from just editing prose, so there's still a deliberate,
  discoverable action behind it rather than a silent auto-heal.
- **If you forget**: the commit blocks, listing which note(s) watch
  something that changed. Do one of the two above, then retry the commit.
- **Regenerating the catalog**: `girdle notes index .` rewrites the
  mechanical block in `index.md` - the same inject/staleness pattern
  AGENTS.md's structural index already uses.
