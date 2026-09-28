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
    }
    assert result.overall_percentage == 33.3


def test_overall_percentage_zero_when_no_applicable_checks(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {
            "unseen": CheckEntry("unseen", ("empty_category",), Difficulty.BASIC),
        },
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static")
    assert result.overall_percentage == 0.0


def test_ecosystem_checks_use_registry_categories_not_key_name(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {
            "custom_tests_check": CheckEntry("custom_tests_check", ("tests",), Difficulty.BASIC),
        },
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        ecosystems=[_eco(tests=2, lint=0, repro=0, ci=0, applicable=["tests"])],
    )

    assert result.category_percentages == {"tests": 100.0}
    assert result.overall_percentage == 100.0


def test_ecosystem_falls_back_when_key_result_not_applicable(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {
            "custom_tests_check": CheckEntry("custom_tests_check", ("tests",), Difficulty.BASIC),
        },
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        ecosystems=[
            EcosystemResult(
                id="x",
                language="x",
                toolchain="x",
                root=".",
                categories={
                    "custom_tests_check": CategoryResult(Tier.ABSENT),
                    "tests": CategoryResult(Tier.CONFIGURED),
                },
                applicable_categories=["tests"],
            )
        ],
    )

    assert result.category_percentages == {"tests": 100.0}
    assert result.overall_percentage == 100.0


def test_percentage_scoring_distinguishes_overall_from_category_double_counting(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
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
        "girdle.schema.CHECK_REGISTRY",
        {"x": CheckEntry("x", ("empty",), Difficulty.BASIC)},
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static")
    data = result.to_dict()["summary"]
    assert "empty" not in data["category_scores"]
    assert data["overall_percentage"] == 0.0


def test_zero_percent_is_neutral_state(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
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
        "girdle.schema.CHECK_REGISTRY",
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


def test_intermediate_only_category_can_earn_silver(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {"x": CheckEntry("x", ("cat",), Difficulty.INTERMEDIATE)},
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        hygiene=HygieneResult(checks={"x": CategoryResult(Tier.CONFIGURED)}),
    )
    score = result.to_dict()["summary"]["category_scores"]["cat"]
    assert score["state"] == "silver"


def test_active_harm_forces_red_state(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
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


def test_applicable_missing_category_result_counts_as_failing(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {"tests": CheckEntry("tests", ("tests",), Difficulty.INTERMEDIATE)},
    )
    eco = EcosystemResult(
        id="js-npm",
        language="javascript",
        toolchain="npm",
        root=".",
        categories={},
        applicable_categories=["tests"],
    )
    result = ScanResult(repo_root=".", scanned_at="now", mode="static", ecosystems=[eco])
    score = result.to_dict()["summary"]["category_scores"]["tests"]
    assert score["passed"] == 0
    assert score["outstanding"] == ["tests"]


def test_hygiene_and_ecosystem_contributions_both_count(monkeypatch):
    monkeypatch.setattr(
        "girdle.schema.CHECK_REGISTRY",
        {"shared": CheckEntry("shared", ("cat",), Difficulty.BASIC)},
    )
    eco = EcosystemResult(
        id="py-pip",
        language="python",
        toolchain="pip",
        root=".",
        categories={},
        applicable_categories=["shared"],
    )
    result = ScanResult(
        repo_root=".",
        scanned_at="now",
        mode="static",
        ecosystems=[eco],
        hygiene=HygieneResult(checks={"shared": CategoryResult(Tier.CONFIGURED)}),
    )
    checks = result.to_dict()["checks"]["shared"]
    assert not checks["passed"]
    assert checks["failing_in"] == ["py-pip"]
