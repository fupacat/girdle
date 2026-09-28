from girdle.dashboard import render_dashboard


def test_dashboard_renders_percentage_and_outstanding_items():
    html = render_dashboard(
        {
            "repo_root": ".",
            "mode": "static",
            "scanned_at": "now",
            "girdle_version": "0.1.0",
            "ecosystems": [
                {
                    "id": "py-pip",
                    "language": "python",
                    "toolchain": "pip",
                    "root": ".",
                    "variants": [],
                    "categories": {},
                }
            ],
            "summary": {
                "ecosystem_count": 1,
                "overall_percentage": 66.7,
                "overall_state": "silver",
                "overall_outstanding": ["lint"],
                "category_scores": {
                    "quality": {
                        "percentage": 50.0,
                        "state": "neutral",
                        "passed": 1,
                        "total": 2,
                        "outstanding": ["lint"],
                    }
                },
            },
            "warnings": [],
            "platform": None,
        }
    )

    assert "Overall score" in html
    assert "66.7%" in html
    assert "Outstanding items" in html
    assert "lint" in html
