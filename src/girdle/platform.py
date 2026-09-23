"""GitHub platform-level enforcement check (branch protection, required
reviews, required status checks) via the `gh` CLI.

Distinct trust category from everything else girdle does: every other check
is a local file read, zero auth, zero network. This one shells out to `gh`
and hits the GitHub API as the currently-authenticated user, so it is opt-in
only (--platform flag), never part of the default scan. girdle does not
implement its own OAuth flow - it reuses whatever `gh auth login` session is
already active, exactly so a user is never asked to newly authorize girdle
itself just to run this check.

Branch protection lives on GitHub's side, not in the repo's files, so this
genuinely cannot be answered by static analysis - unlike the local
policy-as-code case (a committed `.github/settings.yml` or Terraform GitHub-
provider config declaring intended protection), which stays fully within
the zero-auth model and is a separate, complementary signal this module
does not attempt to detect.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT = 15


@dataclass
class PlatformResult:
    available: bool
    reason: str | None = None
    repo: str | None = None
    default_branch: str | None = None
    protected: bool = False
    required_approving_review_count: int = 0
    require_code_owner_reviews: bool = False
    enforce_admins: bool = False
    allow_force_pushes: bool = False
    required_signatures: bool = False
    required_status_check_contexts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        if not self.available:
            return {"available": False, "reason": self.reason}
        return {
            "available": True,
            "repo": self.repo,
            "default_branch": self.default_branch,
            "protected": self.protected,
            "required_approving_review_count": self.required_approving_review_count,
            "require_code_owner_reviews": self.require_code_owner_reviews,
            "enforce_admins": self.enforce_admins,
            "allow_force_pushes": self.allow_force_pushes,
            "required_signatures": self.required_signatures,
            "required_status_check_contexts": self.required_status_check_contexts,
        }


def _run(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["gh", *args], cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout


def extract_protection_facts(protection_json: dict) -> dict:
    """Pure parsing step, kept separate from the subprocess calls so it's
    unit-testable against synthetic GitHub API responses without gh/network.
    """
    reviews = protection_json.get("required_pull_request_reviews") or {}
    status_checks = protection_json.get("required_status_checks") or {}
    return {
        "required_approving_review_count": reviews.get("required_approving_review_count", 0),
        "require_code_owner_reviews": reviews.get("require_code_owner_reviews", False),
        "enforce_admins": (protection_json.get("enforce_admins") or {}).get("enabled", False),
        "allow_force_pushes": (protection_json.get("allow_force_pushes") or {}).get(
            "enabled", False
        ),
        "required_signatures": (protection_json.get("required_signatures") or {}).get(
            "enabled", False
        ),
        "required_status_check_contexts": status_checks.get("contexts", []),
    }


def check_platform(repo_root: Path) -> PlatformResult:
    if shutil.which("gh") is None:
        return PlatformResult(available=False, reason="gh CLI not found on PATH")

    ok, _ = _run(["auth", "status"], repo_root)
    if not ok:
        return PlatformResult(
            available=False, reason="gh CLI not authenticated (run `gh auth login`)"
        )

    ok, out = _run(["repo", "view", "--json", "nameWithOwner,defaultBranchRef"], repo_root)
    if not ok:
        return PlatformResult(
            available=False, reason=f"not a GitHub repo or no remote configured: {out}"
        )
    repo_data = json.loads(out)
    name_with_owner = repo_data["nameWithOwner"]
    default_branch = (repo_data.get("defaultBranchRef") or {}).get("name") or "main"

    ok, out = _run(
        ["api", f"repos/{name_with_owner}/branches/{default_branch}/protection"], repo_root
    )
    if not ok:
        if "404" in out or "Branch not protected" in out:
            return PlatformResult(
                available=True, repo=name_with_owner, default_branch=default_branch,
                protected=False,
            )
        return PlatformResult(available=False, reason=f"gh api call failed: {out}")

    facts = extract_protection_facts(json.loads(out))
    return PlatformResult(
        available=True,
        repo=name_with_owner,
        default_branch=default_branch,
        protected=True,
        **facts,
    )
