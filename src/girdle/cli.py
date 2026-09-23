from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from girdle.dashboard import render_dashboard
from girdle.scan import run_scan

TIER_LABEL = {0: "absent", 1: "configured", 2: "verified"}


@click.group()
def main() -> None:
    """girdle: agent-readiness scanner for verification infrastructure."""


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--run/--static", "do_run", default=False, help="Actually execute test/lint tooling (tier 2)."
)
@click.option("--json", "as_json", is_flag=True, help="Force JSON output even on a TTY.")
@click.option(
    "--fail-under", type=int, default=1,
    help="Exit nonzero if overall_min is below this tier (0-2)."
)
def scan(path: str, do_run: bool, as_json: bool, fail_under: int) -> None:
    """Scan PATH and report verification-infrastructure readiness."""
    result = run_scan(Path(path), mode="run" if do_run else "static")
    data = result.to_dict()

    if as_json or not sys.stdout.isatty():
        click.echo(json.dumps(data, indent=2))
    else:
        _print_human(data)

    sys.exit(0 if result.overall_min >= fail_under else 1)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--run/--static", "do_run", default=False)
@click.option("-o", "--output", default="girdle-report.html", type=click.Path())
def dashboard(path: str, do_run: bool, output: str) -> None:
    """Scan PATH and render an HTML dashboard from the same scan data the CLI uses."""
    result = run_scan(Path(path), mode="run" if do_run else "static")
    html = render_dashboard(result.to_dict())
    Path(output).write_text(html, encoding="utf-8")
    click.echo(f"wrote {output}")


def _print_human(data: dict) -> None:
    click.echo(f"girdle scan  {data['repo_root']}  ({data['mode']})")
    click.echo("")
    for eco in data["ecosystems"]:
        click.echo(f"[{eco['id']}]  {eco['language']}/{eco['toolchain']}  root={eco['root']}")
        for cat_name, cat in eco["categories"].items():
            if cat_name not in eco["applicable_categories"]:
                marker = "n/a"
            else:
                marker = TIER_LABEL[cat["tier"]]
            click.echo(f"  {cat_name:<18} {marker}")
            if cat["reason"]:
                click.echo(f"    reason: {cat['reason']}")
        click.echo("")
    summary = data["summary"]
    click.echo(
        f"summary: {summary['ecosystem_count']} ecosystem(s), "
        f"overall_min={TIER_LABEL[summary['overall_min']]}, "
        f"weakest={summary['weakest_category']}"
    )
    if data["warnings"]:
        for w in data["warnings"]:
            click.echo(f"warning: {w}")


if __name__ == "__main__":
    main()
