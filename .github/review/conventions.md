- `src/girdle/schema.py` is the single source of truth for scan output.
  Both the CLI JSON and the HTML dashboard render `ScanResult` - a PR
  that adds a second representation of scan data (a parallel dict shape,
  a duplicated dataclass) instead of extending `ScanResult` is a
  regression, not a stylistic choice.
- New ecosystem support belongs in `src/girdle/detectors/` as a new file
  implementing the `Detector` protocol (`detectors/base.py`), registered
  in `detectors/registry.py`. A detector that duplicates scanning logic
  already provided by `detectors/_util.py`, `python_common.py`, or
  `js_common.py` instead of reusing it should be flagged.
- `.agent-vault/` holds this repo's design-rationale notes, separate
  from `AGENTS.md` (operational instructions). A PR that changes
  non-obvious scoring/detection behavior without updating the
  corresponding vault note is incomplete, not just under-documented.
