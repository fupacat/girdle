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
