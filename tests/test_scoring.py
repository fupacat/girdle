from girdle import schema as schema_mod
from girdle.checks import CheckEntry, Difficulty
from girdle.hygiene import HygieneResult
from girdle.schema import CategoryResult, EcosystemResult, ScanResult, Tier


def _eco(tests, lint, repro, ci, applicable=None):
    return EcosystemResult(
        id="x", language="x", toolchain="x", root=".",
        categories={
            "tests": CategoryResult(Tier(tests)),
            "lint": CategoryResult(Tier(lint)),
            "reproducibility": CategoryResult(Tier(repro)),
            "ci_gating": CategoryResult(Tier(ci)),
        },
        applicable_categories=applicable or ["tests", "lint", "reproducibility", "ci_gating"],
    )


def test_category_min_is_gated_by_weakest():
    eco = _eco(tests=0, lint=2, repro=2, ci=2)
    assert eco.category_min == 0


def test_inapplicable_categories_excluded_from_min():
    eco = _eco(tests=2, lint=2, repro=0, ci=2, applicable=["tests", "lint", "ci_gating"])
    assert eco.category_min == 2


def test_scan_result_overall_min_is_weakest_ecosystem():
    good = _eco(2, 2, 2, 2)
    bad = _eco(0, 1, 1, 1)
    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[good, bad])
    assert result.overall_min == 0
    assert result.weakest_category == "tests"


def test_percentage_scoring_distinguishes_overall_from_category_double_counting(monkeypatch):
    monkeypatch.setattr(
        schema_mod,
        "CHECK_REGISTRY",
        {
            "a": CheckEntry("a", ("cat1", "cat2"), Difficulty.BASIC),
            "b": CheckEntry("b", ("cat1",), Difficulty.INTERMEDIATE),
            "c": CheckEntry("c", ("cat2",), Difficulty.INTERMEDIATE),
            "d": CheckEntry("d", ("cat3",), Difficulty.ADVANCED),
        },
    )
    hygiene = HygieneResult(
        checks={
            "a": CategoryResult(Tier.CONFIGURED),
            "b": CategoryResult(Tier.ABSENT),
            "c": CategoryResult(Tier.CONFIGURED),
        }
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static", hygiene=hygiene)
    data = result.to_dict()

    assert data["summary"]["category_scores"]["cat1"]["percentage"] == 50.0
    assert data["summary"]["category_scores"]["cat2"]["percentage"] == 100.0
    assert data["summary"]["overall_percentage"] == 66.7


def test_category_with_zero_applicable_checks_is_safe(monkeypatch):
    monkeypatch.setattr(
        schema_mod,
        "CHECK_REGISTRY",
        {"x": CheckEntry("x", ("empty",), Difficulty.BASIC)},
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static")
    score = result.to_dict()["summary"]["category_scores"]["empty"]
    assert score["total"] == 0
    assert score["percentage"] == 0.0
    assert score["state"] == "neutral"


def test_zero_percent_is_neutral_state(monkeypatch):
    monkeypatch.setattr(
        schema_mod,
        "CHECK_REGISTRY",
        {"x": CheckEntry("x", ("cat",), Difficulty.BASIC)},
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        hygiene=HygieneResult(checks={"x": CategoryResult(Tier.ABSENT)}),
    )
    assert result.to_dict()["summary"]["category_scores"]["cat"]["state"] == "neutral"


def test_crossing_difficulty_threshold_earns_badge_state(monkeypatch):
    monkeypatch.setattr(
        schema_mod,
        "CHECK_REGISTRY",
        {
            "basic": CheckEntry("basic", ("cat",), Difficulty.BASIC),
            "intermediate": CheckEntry("intermediate", ("cat",), Difficulty.INTERMEDIATE),
            "advanced": CheckEntry("advanced", ("cat",), Difficulty.ADVANCED),
        },
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        hygiene=HygieneResult(
            checks={
                "basic": CategoryResult(Tier.CONFIGURED),
                "intermediate": CategoryResult(Tier.CONFIGURED),
                "advanced": CategoryResult(Tier.ABSENT),
            }
        ),
    )
    score = result.to_dict()["summary"]["category_scores"]["cat"]
    assert score["state"] == "silver"


def test_active_harm_forces_red_state(monkeypatch):
    monkeypatch.setattr(
        schema_mod,
        "CHECK_REGISTRY",
        {"x": CheckEntry("x", ("cat",), Difficulty.BASIC)},
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        hygiene=HygieneResult(checks={"x": CategoryResult(Tier.CONFIGURED)}),
        active_harm=True,
    )
    data = result.to_dict()["summary"]
    assert data["overall_state"] == "red"
    assert data["category_scores"]["cat"]["state"] == "red"
