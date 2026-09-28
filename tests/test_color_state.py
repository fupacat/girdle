"""Tests for display color-state logic (issue #75)."""

from __future__ import annotations

import pytest

from girdle.checks import CheckEntry, Difficulty
from girdle.color_state import (
    BRONZE_THRESHOLD,
    GOLD_THRESHOLD,
    SILVER_THRESHOLD,
    DisplayState,
    _badge_thresholds,
    display_state,
)

# ---------------------------------------------------------------------------
# Acceptance-criteria tests
# ---------------------------------------------------------------------------


def test_absent_percentage_is_neutral():
    """None (no applicable checks) → neutral, never a warning."""
    assert display_state(None) == DisplayState.NEUTRAL


def test_zero_percentage_is_neutral():
    """0 % → neutral; incompleteness is never a warning color."""
    assert display_state(0.0) == DisplayState.NEUTRAL


def test_just_below_bronze_is_neutral():
    assert display_state(BRONZE_THRESHOLD - 0.01) == DisplayState.NEUTRAL


def test_at_bronze_threshold_is_bronze():
    assert display_state(BRONZE_THRESHOLD) == DisplayState.BRONZE


def test_above_bronze_below_silver_is_bronze():
    midpoint = (BRONZE_THRESHOLD + SILVER_THRESHOLD) / 2
    assert display_state(midpoint) == DisplayState.BRONZE


def test_at_silver_threshold_is_silver():
    assert display_state(SILVER_THRESHOLD) == DisplayState.SILVER


def test_above_silver_below_gold_is_silver():
    midpoint = (SILVER_THRESHOLD + GOLD_THRESHOLD) / 2
    assert display_state(midpoint) == DisplayState.SILVER


def test_at_gold_threshold_is_gold():
    assert display_state(GOLD_THRESHOLD) == DisplayState.GOLD


def test_active_harm_at_zero_is_red():
    """Active-harm flag forces red regardless of percentage."""
    assert display_state(0.0, active_harm=True) == DisplayState.RED


def test_active_harm_at_high_percentage_is_red():
    """Active-harm flag overrides even a perfect score."""
    assert display_state(100.0, active_harm=True) == DisplayState.RED


def test_active_harm_with_absent_percentage_is_red():
    """Active-harm flag with no applicable checks still returns red."""
    assert display_state(None, active_harm=True) == DisplayState.RED


# ---------------------------------------------------------------------------
# Threshold-derivation tests
# ---------------------------------------------------------------------------


def test_badge_thresholds_proportional_to_difficulty(monkeypatch):
    """Thresholds are derived from the non-reserved check distribution."""
    # 2 BASIC, 2 INTERMEDIATE, 2 ADVANCED = 6 total
    # bronze = 2/6 * 100 ≈ 33.33, silver = 4/6 * 100 ≈ 66.67
    monkeypatch.setattr(
        "girdle.color_state.CHECK_REGISTRY",
        {
            "b1": CheckEntry("b1", ("x",), Difficulty.BASIC),
            "b2": CheckEntry("b2", ("x",), Difficulty.BASIC),
            "i1": CheckEntry("i1", ("x",), Difficulty.INTERMEDIATE),
            "i2": CheckEntry("i2", ("x",), Difficulty.INTERMEDIATE),
            "a1": CheckEntry("a1", ("x",), Difficulty.ADVANCED),
            "a2": CheckEntry("a2", ("x",), Difficulty.ADVANCED),
        },
    )
    bronze, silver, gold = _badge_thresholds()
    assert bronze == pytest.approx(33.33)
    assert silver == pytest.approx(66.67)
    assert gold == 100.0


def test_badge_thresholds_exclude_reserved(monkeypatch):
    """Reserved checks do not count toward any threshold denominator."""
    monkeypatch.setattr(
        "girdle.color_state.CHECK_REGISTRY",
        {
            "b1": CheckEntry("b1", ("x",), Difficulty.BASIC),
            "r1": CheckEntry("r1", ("x",), Difficulty.BASIC, reserved=True),
        },
    )
    bronze, silver, gold = _badge_thresholds()
    # Only b1 is active; it is BASIC → bronze threshold = 1/1 = 100 %
    assert bronze == 100.0
    assert gold == 100.0


def test_badge_thresholds_empty_registry_returns_safe_defaults(monkeypatch):
    monkeypatch.setattr("girdle.color_state.CHECK_REGISTRY", {})
    bronze, silver, gold = _badge_thresholds()
    assert bronze == 0.0
    assert silver == 0.0
    assert gold == 100.0


# ---------------------------------------------------------------------------
# DisplayState enum invariants
# ---------------------------------------------------------------------------


def test_display_state_values_are_strings():
    for state in DisplayState:
        assert isinstance(state.value, str)


def test_no_active_harm_never_returns_red():
    for pct in (None, 0.0, 50.0, 100.0):
        assert display_state(pct, active_harm=False) != DisplayState.RED
