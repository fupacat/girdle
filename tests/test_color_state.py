"""Tests for display color-state logic (issue #75)."""

from __future__ import annotations

from girdle.checks import CheckEntry, Difficulty
from girdle.color_state import DisplayState, badge_state


def _check(name: str, difficulty: Difficulty, *, reserved: bool = False) -> CheckEntry:
    return CheckEntry(name, ("x",), difficulty, reserved=reserved)


def test_no_applicable_checks_is_neutral():
    assert badge_state({}) == DisplayState.NEUTRAL


def test_no_passed_checks_is_neutral():
    checks = {
        _check("basic", Difficulty.BASIC): False,
        _check("advanced", Difficulty.ADVANCED): False,
    }
    assert badge_state(checks) == DisplayState.NEUTRAL


def test_basic_checks_passing_earns_bronze():
    checks = {
        _check("basic", Difficulty.BASIC): True,
        _check("intermediate", Difficulty.INTERMEDIATE): False,
        _check("advanced", Difficulty.ADVANCED): False,
    }
    assert badge_state(checks) == DisplayState.BRONZE


def test_every_basic_check_must_pass_for_bronze():
    checks = {
        _check("basic-1", Difficulty.BASIC): True,
        _check("basic-2", Difficulty.BASIC): False,
        _check("advanced", Difficulty.ADVANCED): True,
    }
    assert badge_state(checks) == DisplayState.NEUTRAL


def test_basic_and_intermediate_checks_passing_earns_silver():
    checks = {
        _check("basic", Difficulty.BASIC): True,
        _check("intermediate", Difficulty.INTERMEDIATE): True,
        _check("advanced", Difficulty.ADVANCED): False,
    }
    assert badge_state(checks) == DisplayState.SILVER


def test_all_non_reserved_checks_passing_earns_gold():
    checks = {
        _check("basic", Difficulty.BASIC): True,
        _check("intermediate", Difficulty.INTERMEDIATE): True,
        _check("advanced", Difficulty.ADVANCED): True,
    }
    assert badge_state(checks) == DisplayState.GOLD


def test_reserved_checks_do_not_affect_badge_tier():
    checks = {
        _check("basic", Difficulty.BASIC): True,
        _check("reserved", Difficulty.BASIC, reserved=True): False,
        _check("advanced", Difficulty.ADVANCED): False,
    }
    assert badge_state(checks) == DisplayState.BRONZE


def test_reserved_only_checks_are_neutral():
    checks = {_check("reserved", Difficulty.BASIC, reserved=True): True}
    assert badge_state(checks) == DisplayState.NEUTRAL


def test_active_harm_overrides_badge_tier():
    checks = {_check("basic", Difficulty.BASIC): True}
    assert badge_state(checks, active_harm=True) == DisplayState.RED


def test_display_state_values_are_strings():
    for state in DisplayState:
        assert isinstance(state.value, str)
