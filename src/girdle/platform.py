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
    recommendations: list[str] = field(default_factory=list)

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
            "recommendations": self.recommendations,
        }


def compute_recommendations(result: PlatformResult) -> list[str]:
    """Pure function, kept separate from check_platform() for the same
    testability reason as extract_protection_facts().
    """
    if not result.available:
        return []
    settings_url = f"https://github.com/{result.repo}/settings/branches"
    if not result.protected:
        return [
            f"Enable branch protection on `{result.default_branch}` "
            f"(requiring at least 1 approving review before merge): {settings_url}"
        ]
    recs = []
    if result.required_approving_review_count < 1:
        recs.append(
            f"Require at least 1 approving review before merge on `{result.default_branch}`: "
            f"{settings_url}"
        )
    if not result.enforce_admins:
        recs.append("Enable 'Include administrators' so branch protection also applies to admins.")
    if result.allow_force_pushes:
        recs.append(f"Disable force-pushes on the protected branch `{result.default_branch}`.")
    if not result.required_status_check_contexts:
        recs.append(
            "Add required status checks (e.g. your CI job name) so PRs can't merge with "
            "failing CI."
        )
    return recs


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


def extract_ruleset_facts(rules_json: list[dict]) -> dict:
    """Fold a branch's active rules into a facts dict with the same shape as
    :func:`extract_protection_facts`.

    *rules_json* is the response from `GET repos/{owner}/{repo}/rules/branches/{branch}`
    - a flat list of ``{type, parameters}`` objects for the rules already
    active on that specific branch. Unlike the list-rulesets endpoint
    (`GET repos/{owner}/{repo}/rulesets`), which returns only ruleset
    summaries without `conditions`/`rules`, this endpoint has GitHub resolve
    org-level rulesets, `~DEFAULT_BRANCH`/`~ALL` targeting, and ref-pattern
    excludes server-side - no client-side ref matching needed here.
    """
    required_approving_review_count = 0
    require_code_owner_reviews = False
    allow_force_pushes = True   # a rule *restricts* force-push via non_fast_forward
    required_status_check_contexts: list[str] = []
    matched = False

    for rule in rules_json:
        rtype = rule.get("type")
        params = rule.get("parameters") or {}
        if rtype == "pull_request":
            matched = True
            count = params.get("required_approving_review_count", 0)
            if count > required_approving_review_count:
                required_approving_review_count = count
            if params.get("require_code_owner_review"):
                require_code_owner_reviews = True
        elif rtype == "required_status_checks":
            matched = True
            for check in params.get("required_status_checks") or []:
                ctx = check.get("context") or check.get("integrationId") or str(check)
                if ctx and ctx not in required_status_check_contexts:
                    required_status_check_contexts.append(ctx)
        elif rtype == "non_fast_forward":
            matched = True
            allow_force_pushes = False
        elif rtype == "deletion":
            matched = True  # noted but not surfaced in PlatformResult yet

    if not matched:
        return {}

    return {
        "required_approving_review_count": required_approving_review_count,
        "require_code_owner_reviews": require_code_owner_reviews,
        "enforce_admins": False,  # rulesets don't have an enforce_admins concept
        "allow_force_pushes": allow_force_pushes,
        "required_signatures": False,
        "required_status_check_contexts": required_status_check_contexts,
    }


def _merge_facts(classic: dict, ruleset: dict) -> dict:
    """Union protection facts from classic branch protection and rulesets."""
    if not ruleset:
        return classic
    if not classic:
        return ruleset
    return {
        "required_approving_review_count": max(
            classic.get("required_approving_review_count", 0),
            ruleset.get("required_approving_review_count", 0),
        ),
        "require_code_owner_reviews": (
            classic.get("require_code_owner_reviews", False)
            or ruleset.get("require_code_owner_reviews", False)
        ),
        "enforce_admins": classic.get("enforce_admins", False),
        "allow_force_pushes": (
            classic.get("allow_force_pushes", False)
            and ruleset.get("allow_force_pushes", False)
        ),
        "required_signatures": classic.get("required_signatures", False),
        "required_status_check_contexts": list(
            dict.fromkeys(
                classic.get("required_status_check_contexts", [])
                + ruleset.get("required_status_check_contexts", [])
            )
        ),
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

    # --- Classic branch-protection ---
    classic_facts: dict = {}
    classic_protected = False
    ok, out = _run(
        ["api", f"repos/{name_with_owner}/branches/{default_branch}/protection"], repo_root
    )
    if ok:
        classic_facts = extract_protection_facts(json.loads(out))
        classic_protected = True
    elif "404" not in out and "Branch not protected" not in out:
        return PlatformResult(available=False, reason=f"gh api call failed: {out}")

    # --- Rulesets, via the branch-rules endpoint (already resolves org-level
    # rulesets and ref targeting for this specific branch - see
    # extract_ruleset_facts's docstring for why not the list-rulesets one) ---
    ruleset_facts: dict = {}
    ok, out = _run(["api", f"repos/{name_with_owner}/rules/branches/{default_branch}"], repo_root)
    if ok:
        try:
            rules = json.loads(out)
            if isinstance(rules, list):
                ruleset_facts = extract_ruleset_facts(rules)
        except json.JSONDecodeError:
            pass  # best-effort; fall through to classic-only result

    protected = classic_protected or bool(ruleset_facts)
    merged = _merge_facts(classic_facts, ruleset_facts)

    result = PlatformResult(
        available=True,
        repo=name_with_owner,
        default_branch=default_branch,
        protected=protected,
        **merged,
    )
    result.recommendations = compute_recommendations(result)
    return result
