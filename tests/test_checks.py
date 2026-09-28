"""Tests for the check registry (src/girdle/checks.py)."""

from __future__ import annotations

import pytest

from girdle.checks import CHECK_REGISTRY, CheckEntry, Difficulty, checks_by_difficulty

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _live(difficulty: Difficulty) -> list[str]:
    """Keys of non-reserved entries with the given difficulty."""
    return [e.key for e in checks_by_difficulty(difficulty) if not e.reserved]


def _reserved(difficulty: Difficulty) -> list[str]:
    """Keys of reserved entries with the given difficulty."""
    return [e.key for e in checks_by_difficulty(difficulty) if e.reserved]


# ---------------------------------------------------------------------------
# Basic structural checks
# ---------------------------------------------------------------------------

def test_registry_is_not_empty():
    assert len(CHECK_REGISTRY) > 0


def test_registry_keys_are_unique():
    keys = list(CHECK_REGISTRY.keys())
    assert len(keys) == len(set(keys))


def test_every_entry_has_at_least_one_category():
    for entry in CHECK_REGISTRY.values():
        assert entry.categories, f"{entry.key!r} has no categories"


def test_every_entry_has_a_difficulty():
    for entry in CHECK_REGISTRY.values():
        assert isinstance(entry.difficulty, Difficulty)


def test_lookup_by_key():
    entry = CHECK_REGISTRY["readme"]
    assert isinstance(entry, CheckEntry)
    assert entry.key == "readme"


# ---------------------------------------------------------------------------
# Difficulty groupings
# ---------------------------------------------------------------------------

def test_basic_checks_present():
    keys = [e.key for e in checks_by_difficulty(Difficulty.BASIC)]
    assert "readme" in keys
    assert "gitignore" in keys
    assert "contributing" in keys


def test_intermediate_checks_present():
    keys = [e.key for e in checks_by_difficulty(Difficulty.INTERMEDIATE)]
    for expected in [
        "tests", "lint", "coverage", "ci_gating", "codeowners",
        "dependency_monitoring", "editorconfig", "gitattributes", "precommit",
    ]:
        assert expected in keys, f"expected {expected!r} in intermediate checks"


def test_advanced_checks_present():
    keys = [e.key for e in checks_by_difficulty(Difficulty.ADVANCED)]
    assert "static_analysis" in keys
    assert "agent_instructions" in keys
    assert "agent_sandbox_bootstrap" in keys


# ---------------------------------------------------------------------------
# Reserved slots
# ---------------------------------------------------------------------------

def test_license_is_reserved():
    assert CHECK_REGISTRY["license"].reserved is True


def test_reproducibility_is_reserved():
    assert CHECK_REGISTRY["reproducibility"].reserved is True


def test_live_checks_are_not_reserved():
    live_keys = [
        "readme", "gitignore", "contributing",
        "tests", "lint", "coverage", "ci_gating", "codeowners",
        "dependency_monitoring", "editorconfig", "gitattributes", "precommit",
        "static_analysis",
        "agent_instructions", "agent_sandbox_bootstrap",
    ]
    for key in live_keys:
        assert not CHECK_REGISTRY[key].reserved, f"{key!r} should not be reserved"


# ---------------------------------------------------------------------------
# Category membership
# ---------------------------------------------------------------------------

def test_categories_are_tuples():
    for entry in CHECK_REGISTRY.values():
        assert isinstance(entry.categories, tuple)


@pytest.mark.parametrize("key,expected_category", [
    ("readme", "readme"),
    ("gitignore", "gitignore"),
    ("tests", "tests"),
    ("lint", "lint"),
    ("coverage", "coverage"),
    ("ci_gating", "ci_gating"),
    ("static_analysis", "static_analysis"),
    ("codeowners", "codeowners"),
    ("dependency_monitoring", "dependency_monitoring"),
    ("editorconfig", "editorconfig"),
    ("gitattributes", "gitattributes"),
    ("precommit", "precommit"),
    ("agent_instructions", "agent_instructions"),
    ("agent_sandbox_bootstrap", "agent_sandbox_bootstrap"),
    ("contributing", "contributing"),
    ("license", "license"),
    ("reproducibility", "reproducibility"),
])
def test_check_maps_to_expected_category(key, expected_category):
    assert expected_category in CHECK_REGISTRY[key].categories


# ---------------------------------------------------------------------------
# Total count
# ---------------------------------------------------------------------------

def test_registry_covers_all_17_categories():
    """Registry must cover all 17 categories enumerated in the design doc."""
    expected_categories = {
        "readme", "gitignore", "license", "contributing",
        "tests", "lint", "coverage", "ci_gating", "static_analysis", "codeowners",
        "dependency_monitoring", "editorconfig", "gitattributes", "precommit",
        "agent_instructions", "agent_sandbox_bootstrap", "reproducibility",
    }
    all_categories: set[str] = set()
    for entry in CHECK_REGISTRY.values():
        all_categories.update(entry.categories)
    assert expected_categories <= all_categories
