from girdle.badge import badge_endpoint, badge_markdown, badge_url


def _data(overall_percentage: float, overall_state: str) -> dict:
    return {"summary": {"overall_percentage": overall_percentage, "overall_state": overall_state}}


def test_badge_url_neutral():
    url = badge_url(_data(0.0, "neutral"))
    assert url == "https://img.shields.io/badge/girdle-0%25-7f8794"


def test_badge_url_bronze():
    url = badge_url(_data(50.0, "bronze"))
    assert url == "https://img.shields.io/badge/girdle-50%25%20bronze-cd7f32"


def test_badge_url_red():
    url = badge_url(_data(12.5, "red"))
    assert url == "https://img.shields.io/badge/girdle-12.5%25-e05252"


def test_badge_url_custom_label():
    url = badge_url(_data(100, "gold"), label="my project")
    assert url.startswith("https://img.shields.io/badge/my%20project-100%25%20gold-")


def test_badge_markdown_links_to_girdle_by_default():
    md = badge_markdown(_data(50, "bronze"))
    assert md == (
        "[![girdle](https://img.shields.io/badge/girdle-50%25%20bronze-cd7f32)]"
        "(https://github.com/fupacat/girdle)"
    )


def test_badge_markdown_custom_link():
    md = badge_markdown(_data(50, "bronze"), link="https://example.com")
    assert md.endswith("(https://example.com)")


def test_badge_endpoint_schema():
    endpoint = badge_endpoint(_data(100, "gold"))
    assert endpoint == {
        "schemaVersion": 1,
        "label": "girdle",
        "message": "100% gold",
        "color": "d4af37",
    }


def test_badge_endpoint_custom_label():
    endpoint = badge_endpoint(_data(0, "neutral"), label="my-repo")
    assert endpoint["label"] == "my-repo"
    assert endpoint["message"] == "0%"


def test_badge_falls_back_to_legacy_overall_min():
    endpoint = badge_endpoint({"summary": {"overall_min": 2}})
    assert endpoint["message"] == "verified"
