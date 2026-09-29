"""HTML dashboard renderer. Pure presentation over the same dict the CLI's
--json output produces — never a second scan path.
"""

from __future__ import annotations

from importlib import resources

from jinja2 import Environment, FileSystemLoader, select_autoescape

STATE_LABEL = {
    "neutral": "Neutral",
    "bronze": "Bronze",
    "silver": "Silver",
    "gold": "Gold",
    "red": "Active harm",
}
STATE_CLASS = {
    "neutral": "state-neutral",
    "bronze": "state-bronze",
    "silver": "state-silver",
    "gold": "state-gold",
    "red": "state-red",
}


def render_dashboard(data: dict) -> str:
    template_dir = resources.files("girdle") / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["state_label"] = lambda s: STATE_LABEL.get(s, "Unknown")
    env.filters["state_class"] = lambda s: STATE_CLASS.get(s, "state-unknown")
    template = env.get_template("dashboard.html.jinja")
    return template.render(data=data)
