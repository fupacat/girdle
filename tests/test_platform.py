from pathlib import Path
from unittest.mock import patch

from girdle.platform import (
    PlatformResult,
    check_platform,
    compute_recommendations,
    extract_protection_facts,
    extract_ruleset_facts,
)

PROTECTION_RESPONSE = {
    "required_pull_request_reviews": {
        "required_approving_review_count": 2,
        "require_code_owner_reviews": True,
    },
    "required_status_checks": {"contexts": ["ci/test", "ci/lint"]},
    "enforce_admins": {"enabled": True},
    "allow_force_pushes": {"enabled": False},
    "required_signatures": {"enabled": True},
}


def test_extract_protection_facts_full():
    facts = extract_protection_facts(PROTECTION_RESPONSE)
    assert facts["required_approving_review_count"] == 2
    assert facts["require_code_owner_reviews"] is True
    assert facts["enforce_admins"] is True
    assert facts["allow_force_pushes"] is False
    assert facts["required_signatures"] is True
    assert facts["required_status_check_contexts"] == ["ci/test", "ci/lint"]


def test_extract_protection_facts_empty_response():
    facts = extract_protection_facts({})
    assert facts["required_approving_review_count"] == 0
    assert facts["require_code_owner_reviews"] is False
    assert facts["enforce_admins"] is False
    assert facts["required_status_check_contexts"] == []


def test_check_platform_gh_not_found(tmp_path: Path):
    with patch("girdle.platform.shutil.which", return_value=None):
        result = check_platform(tmp_path)
    assert result.available is False
    assert "not found" in result.reason


def test_check_platform_not_authenticated(tmp_path: Path):
    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", return_value=(False, "not logged in")):
            result = check_platform(tmp_path)
    assert result.available is False
    assert "authenticated" in result.reason


def test_check_platform_no_remote(tmp_path: Path):
    def fake_run(args, cwd):
        if args[0] == "auth":
            return True, ""
        return False, "no git remotes found"

    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", side_effect=fake_run):
            result = check_platform(tmp_path)
    assert result.available is False
    assert "not a GitHub repo" in result.reason


def test_check_platform_unprotected_branch(tmp_path: Path):
    import json

    def fake_run(args, cwd):
        if args[0] == "auth":
            return True, ""
        if args[0] == "repo":
            return True, json.dumps(
                {"nameWithOwner": "user/repo", "defaultBranchRef": {"name": "main"}}
            )
        return False, '{"message":"Branch not protected","status":"404"}'

    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", side_effect=fake_run):
            result = check_platform(tmp_path)
    assert result.available is True
    assert result.protected is False
    assert result.repo == "user/repo"


def test_check_platform_protected_branch(tmp_path: Path):
    import json

    def fake_run(args, cwd):
        if args[0] == "auth":
            return True, ""
        if args[0] == "repo":
            return True, json.dumps(
                {"nameWithOwner": "user/repo", "defaultBranchRef": {"name": "main"}}
            )
        return True, json.dumps(PROTECTION_RESPONSE)

    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", side_effect=fake_run):
            result = check_platform(tmp_path)
    assert result.available is True
    assert result.protected is True
    assert result.required_approving_review_count == 2
    assert result.enforce_admins is True


def test_to_dict_unavailable():
    result = PlatformResult(available=False, reason="gh not found")
    assert result.to_dict() == {"available": False, "reason": "gh not found"}


def test_compute_recommendations_unavailable_is_empty():
    result = PlatformResult(available=False, reason="gh not found")
    assert compute_recommendations(result) == []


def test_compute_recommendations_unprotected():
    result = PlatformResult(
        available=True, repo="user/repo", default_branch="main", protected=False
    )
    recs = compute_recommendations(result)
    assert len(recs) == 1
    assert "branch protection" in recs[0]


def test_compute_recommendations_protected_but_weak():
    result = PlatformResult(
        available=True, repo="user/repo", default_branch="main", protected=True,
        required_approving_review_count=0, enforce_admins=False, allow_force_pushes=True,
        required_status_check_contexts=[],
    )
    recs = compute_recommendations(result)
    assert any("approving review" in r for r in recs)
    assert any("administrators" in r for r in recs)
    assert any("force-pushes" in r for r in recs)
    assert any("status checks" in r for r in recs)


def test_compute_recommendations_fully_hardened_is_empty():
    result = PlatformResult(
        available=True, repo="user/repo", default_branch="main", protected=True,
        required_approving_review_count=2, enforce_admins=True, allow_force_pushes=False,
        required_status_check_contexts=["ci/test"],
    )
    assert compute_recommendations(result) == []


def test_to_dict_available_and_protected():
    result = PlatformResult(
        available=True, repo="user/repo", default_branch="main", protected=True,
        required_approving_review_count=1,
    )
    d = result.to_dict()
    assert d["available"] is True
    assert d["protected"] is True
    assert d["required_approving_review_count"] == 1


# ---------------------------------------------------------------------------
# Ruleset tests
# ---------------------------------------------------------------------------

# Shape returned by GET repos/{owner}/{repo}/rules/branches/{branch} - a
# flat list of {type, parameters} for the rules already active on that
# specific branch (GitHub resolves org-level rulesets and ref targeting
# server-side; nothing here carries a ruleset id/conditions/enforcement).
BRANCH_RULES_RESPONSE = [
    {
        "type": "pull_request",
        "parameters": {
            "required_approving_review_count": 1,
            "require_code_owner_review": False,
        },
    },
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "ci/test"},
                {"context": "ci/lint"},
            ]
        },
    },
    {"type": "non_fast_forward"},
    {"type": "deletion"},
]


def test_extract_ruleset_facts_active_rules():
    facts = extract_ruleset_facts(BRANCH_RULES_RESPONSE)
    assert facts["required_approving_review_count"] == 1
    assert facts["allow_force_pushes"] is False
    assert "ci/test" in facts["required_status_check_contexts"]
    assert "ci/lint" in facts["required_status_check_contexts"]


def test_extract_ruleset_facts_no_rules_is_empty():
    assert extract_ruleset_facts([]) == {}


def test_extract_ruleset_facts_unrecognized_rule_types_ignored():
    # A rule type this module doesn't model yet must not crash or count as
    # "matched" on its own.
    assert extract_ruleset_facts([{"type": "creation"}, {"type": "update"}]) == {}


def test_check_platform_ruleset_only_protected(tmp_path: Path):
    """Classic API returns 404 but an active ruleset protects the branch."""
    import json

    def fake_run(args, cwd):
        if args[0] == "auth":
            return True, ""
        if args[0] == "repo":
            return True, json.dumps(
                {"nameWithOwner": "user/repo", "defaultBranchRef": {"name": "main"}}
            )
        if "protection" in " ".join(args):
            return False, '{"message":"Branch not protected","status":"404"}'
        if "rules/branches" in " ".join(args):
            return True, json.dumps(BRANCH_RULES_RESPONSE)
        return False, "unexpected"

    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", side_effect=fake_run):
            result = check_platform(tmp_path)

    assert result.available is True
    assert result.protected is True
    assert result.required_approving_review_count == 1
    assert result.allow_force_pushes is False
    assert "ci/test" in result.required_status_check_contexts


def test_check_platform_classic_and_ruleset_unioned(tmp_path: Path):
    """Classic protection + branch rules: facts are unioned (max reviews, combined contexts)."""
    import json

    classic = {
        "required_pull_request_reviews": {"required_approving_review_count": 2},
        "required_status_checks": {"contexts": ["classic/ci"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "required_signatures": {"enabled": False},
    }
    branch_rules = [
        {"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": "ruleset/extra"}]
        }},
    ]

    def fake_run(args, cwd):
        if args[0] == "auth":
            return True, ""
        if args[0] == "repo":
            return True, json.dumps(
                {"nameWithOwner": "user/repo", "defaultBranchRef": {"name": "main"}}
            )
        if "protection" in " ".join(args):
            return True, json.dumps(classic)
        if "rules/branches" in " ".join(args):
            return True, json.dumps(branch_rules)
        return False, "unexpected"

    with patch("girdle.platform.shutil.which", return_value="/usr/bin/gh"):
        with patch("girdle.platform._run", side_effect=fake_run):
            result = check_platform(tmp_path)

    assert result.available is True
    assert result.protected is True
    assert result.required_approving_review_count == 2  # classic wins (higher)
    assert "classic/ci" in result.required_status_check_contexts
    assert "ruleset/extra" in result.required_status_check_contexts
    assert result.enforce_admins is True  # from classic
