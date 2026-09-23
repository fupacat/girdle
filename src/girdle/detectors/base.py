"""Detector protocol: one detector per ecosystem row in the design matrix.

A detector's job is split in two so scoring stays mechanical:
- `detect(root)` returns fingerprint info if this ecosystem is present at `root`,
  or None if not. Detection must be marker-file based, never content-sniffed
  prose, per the structural-facts-only security stance.
- `scan(fingerprint, mode)` returns the four CategoryResults for that ecosystem.
  `mode="run"` may execute the repo's own tooling (e.g. `pytest --collect-only`
  or an actual test run); `mode="static"` must only read files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from girdle.schema import CategoryResult


@dataclass
class Fingerprint:
    id: str
    language: str
    toolchain: str
    root: Path
    variants: list[str]


class Detector(Protocol):
    def detect(self, root: Path) -> Fingerprint | None: ...

    def scan(self, fp: Fingerprint, mode: str) -> dict[str, CategoryResult]: ...

    def applicable_categories(self, fp: Fingerprint) -> list[str]: ...

    def run_commands(self, fp: Fingerprint) -> dict[str, list[str]]:
        """Optional: category name -> command to execute for --run (tier-2)
        verification. Only categories with an entry here are eligible for
        upgrade from CONFIGURED to VERIFIED; omit a category (or the whole
        method) if there's no safe/well-defined invocation for it. Detectors
        that don't implement this are treated as returning {}.
        """
        ...
