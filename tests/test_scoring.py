from girdle.checks import CHECK_REGISTRY, CheckEntry, Difficulty
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


def test_ecosystem_category_percentages_count_shared_checks_per_category(monkeypatch):
    monkeypatch.setitem(
        CHECK_REGISTRY,
        "shared",
        CheckEntry("shared", ("tests", "lint"), Difficulty.INTERMEDIATE),
    )

    eco = EcosystemResult(
        id="x",
        language="x",
        toolchain="x",
        root=".",
        categories={
            "tests": CategoryResult(Tier.CONFIGURED),
            "lint": CategoryResult(Tier.ABSENT),
            "shared": CategoryResult(Tier.CONFIGURED),
        },
        applicable_categories=["tests", "lint"],
    )

    assert eco.category_percentages == {"tests": 100.0, "lint": 50.0}
    assert eco.overall_percentage == 66.67


def test_ecosystem_category_percentages_return_zero_for_empty_category(monkeypatch):
    monkeypatch.setitem(
        CHECK_REGISTRY,
        "tests",
        CheckEntry("tests", ("tests",), Difficulty.INTERMEDIATE),
    )
    monkeypatch.setitem(
        CHECK_REGISTRY,
        "lint",
        CheckEntry("lint", ("lint",), Difficulty.INTERMEDIATE),
    )

    eco = EcosystemResult(
        id="x",
        language="x",
        toolchain="x",
        root=".",
        categories={"tests": CategoryResult(Tier.CONFIGURED)},
        applicable_categories=["tests", "lint"],
    )

    assert eco.category_percentages == {"tests": 100.0, "lint": 0.0}
    assert eco.overall_percentage == 100.0


def test_scan_result_overall_percentage_dedupes_shared_checks_within_overall(monkeypatch):
    monkeypatch.setitem(
        CHECK_REGISTRY,
        "shared",
        CheckEntry("shared", ("tests", "lint"), Difficulty.INTERMEDIATE),
    )

    eco = EcosystemResult(
        id="x",
        language="x",
        toolchain="x",
        root=".",
        categories={
            "tests": CategoryResult(Tier.CONFIGURED),
            "lint": CategoryResult(Tier.ABSENT),
            "shared": CategoryResult(Tier.CONFIGURED),
        },
        applicable_categories=["tests", "lint"],
    )

    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[eco])

    assert result.category_percentages["tests"] == 100.0
    assert result.category_percentages["lint"] == 50.0
    assert result.overall_percentage == 66.67


def test_scan_result_overall_percentage_counts_checks_not_ecosystem_averages():
    first = EcosystemResult(
        id="a",
        language="x",
        toolchain="x",
        root=".",
        categories={"tests": CategoryResult(Tier.CONFIGURED)},
        applicable_categories=["tests"],
    )
    second = EcosystemResult(
        id="b",
        language="x",
        toolchain="x",
        root=".",
        categories={
            "lint": CategoryResult(Tier.ABSENT),
            "coverage": CategoryResult(Tier.ABSENT),
        },
        applicable_categories=["lint", "coverage"],
    )

    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[first, second])

    assert first.overall_percentage == 100.0
    assert second.overall_percentage == 0.0
    assert result.overall_percentage == 33.33


def test_scan_result_overall_percentage_dedupes_duplicate_check_keys_by_worst_tier():
    first = EcosystemResult(
        id="a",
        language="x",
        toolchain="x",
        root=".",
        categories={"tests": CategoryResult(Tier.CONFIGURED)},
        applicable_categories=["tests"],
    )
    second = EcosystemResult(
        id="b",
        language="x",
        toolchain="x",
        root=".",
        categories={"tests": CategoryResult(Tier.ABSENT)},
        applicable_categories=["tests"],
    )

    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[first, second])

    assert result.category_percentages["tests"] == 0.0
    assert result.overall_percentage == 0.0


def test_scan_result_category_percentages_omit_categories_without_applicable_checks():
    eco = EcosystemResult(
        id="x",
        language="x",
        toolchain="x",
        root=".",
        categories={"tests": CategoryResult(Tier.CONFIGURED)},
        applicable_categories=["tests"],
    )

    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[eco])

    assert result.category_percentages == {"tests": 100.0}
