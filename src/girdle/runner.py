"""Executes a scanned repo's own tooling for --run (tier-2) verification.

This runs arbitrary code from the target repository. It is only invoked when
the caller explicitly passes --run (never the default), per the design
note's stance on untrusted-fork risk: static-only stays the safe default.

girdle does not manage environments - --run assumes whatever interpreter/
toolchain is already active (or on PATH) is the one appropriate for the
scanned repo; it does not install dependencies first.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 120


@dataclass
class RunOutcome:
    ran: bool
    passed: bool
    reason: str | None
    stdout: str = ""
    stderr: str = ""


def run_check(command: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT) -> RunOutcome:
    exe = command[0]
    resolved = shutil.which(exe, path=None) or shutil.which(exe, path=str(cwd))
    if resolved is None and not (cwd / exe).exists():
        return RunOutcome(ran=False, passed=False, reason=f"'{exe}' not found on PATH, skipped")
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return RunOutcome(ran=True, passed=False, reason=f"timed out after {timeout}s")
    except OSError as e:
        return RunOutcome(ran=False, passed=False, reason=f"failed to execute: {e}")

    if proc.returncode == 0:
        return RunOutcome(
            ran=True, passed=True, reason=None, stdout=proc.stdout, stderr=proc.stderr
        )
    return RunOutcome(
        ran=True, passed=False, reason=f"`{' '.join(command)}` exited {proc.returncode}",
        stdout=proc.stdout, stderr=proc.stderr,
    )
