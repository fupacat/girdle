"""HTML dashboard renderer. Pure presentation over the same dict the CLI's
--json output produces — never a second scan path.
"""

from __future__ import annotations

from importlib import resources

from jinja2 import Environment, FileSystemLoader, select_autoescape

TIER_LABEL = {0: "Absent", 1: "Configured", 2: "Verified"}
TIER_CLASS = {0: "tier-absent", 1: "tier-configured", 2: "tier-verified"}


def render_dashboard(data: dict) -> str:
    template_dir = resources.files("girdle") / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["tier_label"] = lambda t: TIER_LABEL.get(t, "Unknown")
    env.filters["tier_class"] = lambda t: TIER_CLASS.get(t, "tier-unknown")
    template = env.get_template("dashboard.html.jinja")
    return template.render(data=data)
