from girdle.badge import badge_markdown, badge_url


def _data(overall_min: int) -> dict:
    return {"summary": {"overall_min": overall_min}}


def test_badge_url_absent():
    url = badge_url(_data(0))
    assert url == "https://img.shields.io/badge/girdle-absent-e05252"


def test_badge_url_configured():
    url = badge_url(_data(1))
    assert url == "https://img.shields.io/badge/girdle-configured-d9a441"


def test_badge_url_verified():
    url = badge_url(_data(2))
    assert url == "https://img.shields.io/badge/girdle-verified-4caf7d"


def test_badge_url_custom_label():
    url = badge_url(_data(2), label="my project")
    assert url.startswith("https://img.shields.io/badge/my%20project-verified-")


def test_badge_markdown_links_to_girdle_by_default():
    md = badge_markdown(_data(1))
    assert md == (
        "[![girdle](https://img.shields.io/badge/girdle-configured-d9a441)]"
        "(https://github.com/fupacat/girdle)"
    )


def test_badge_markdown_custom_link():
    md = badge_markdown(_data(1), link="https://example.com")
    assert md.endswith("(https://example.com)")
