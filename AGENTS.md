# girdle

Agent-readiness scanner. `src/girdle/schema.py` is the single source of truth
for scan output — CLI JSON and the HTML dashboard both render `ScanResult`,
never a second representation. Keep it that way.

New ecosystem support = new file in `src/girdle/detectors/` implementing the
`Detector` protocol (`detectors/base.py`), registered in `detectors/registry.py`.
Design rationale and the full detection matrix: see the vault note
`Agent-Ready Repository Design` (not duplicated here — read it before adding
scoring behavior, not this file).

Run checks: `pytest` / `ruff check .`.
