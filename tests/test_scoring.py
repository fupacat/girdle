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


def test_percentages_multi_category_and_overall_distinct(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {
            "shared": CheckEntry("shared", ("category_a", "category_b"), Difficulty.BASIC),
            "a_only": CheckEntry("a_only", ("category_a",), Difficulty.BASIC),
            "b_only": CheckEntry("b_only", ("category_b",), Difficulty.BASIC),
            "unseen": CheckEntry("unseen", ("empty_category",), Difficulty.BASIC),
        },
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        hygiene=HygieneResult(
            checks={
                "shared": CategoryResult(Tier.CONFIGURED),
                "a_only": CategoryResult(Tier.ABSENT),
                "b_only": CategoryResult(Tier.ABSENT),
            }
        ),
    )

    assert result.category_percentages == {
        "category_a": 50.0,
        "category_b": 50.0,
        "empty_category": None,
    }
    assert result.overall_percentage == 33.33


def test_overall_percentage_none_when_no_applicable_checks(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {
            "unseen": CheckEntry("unseen", ("empty_category",), Difficulty.BASIC),
        },
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static")
    assert result.overall_percentage is None
