from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from girdle.dashboard import render_dashboard
from girdle.indexer import build_index, inject_into, is_stale, render_manifest
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
@click.option(
    "--platform", "check_platform_flag", is_flag=True,
    help="Also check GitHub branch protection via `gh` (opt-in: needs gh CLI, network, your auth).",
)
def scan(
    path: str, do_run: bool, as_json: bool, fail_under: int, check_platform_flag: bool
) -> None:
    """Scan PATH and report verification-infrastructure readiness."""
    result = run_scan(
        Path(path), mode="run" if do_run else "static",
        check_platform_enforcement=check_platform_flag,
    )
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
@click.option(
    "--platform", "check_platform_flag", is_flag=True,
    help="Also check GitHub branch protection via `gh` (opt-in: needs gh CLI, network, your auth).",
)
def dashboard(path: str, do_run: bool, output: str, check_platform_flag: bool) -> None:
    """Scan PATH and render an HTML dashboard from the same scan data the CLI uses."""
    result = run_scan(
        Path(path), mode="run" if do_run else "static",
        check_platform_enforcement=check_platform_flag,
    )
    html = render_dashboard(result.to_dict())
    Path(output).write_text(html, encoding="utf-8")
    click.echo(f"wrote {output}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--json", "as_json", is_flag=True, help="Emit structured JSON instead of the manifest text."
)
@click.option(
    "--budget-tokens", type=int, default=4000, help="Approximate token budget for the manifest."
)
@click.option("-o", "--output", type=click.Path(), help="Write the manifest text to this file.")
@click.option(
    "--inject",
    "inject_path",
    type=click.Path(),
    help="Insert/update the manifest between markers in FILE (e.g. AGENTS.md) instead of stdout.",
)
@click.option(
    "--check",
    "check_path",
    type=click.Path(),
    help="Exit nonzero if the manifest block in FILE is missing or stale; writes nothing.",
)
def index(
    path: str, as_json: bool, budget_tokens: int, output: str | None,
    inject_path: str | None, check_path: str | None,
) -> None:
    """Generate a deterministic structural index (path/language/symbols) of PATH."""
    repo_index = build_index(Path(path), budget_tokens=budget_tokens)
    manifest = render_manifest(repo_index)

    if check_path:
        stale = is_stale(Path(check_path), manifest)
        click.echo("stale" if stale else "fresh")
        sys.exit(1 if stale else 0)

    if inject_path:
        target = Path(inject_path)
        target.write_text(inject_into(target, manifest), encoding="utf-8")
        click.echo(f"updated index block in {inject_path}")
        return

    if as_json:
        text = json.dumps(repo_index.to_dict(), indent=2)
    else:
        text = manifest

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"wrote {output}")
    else:
        click.echo(text)


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
            if cat["recommendation"]:
                click.echo(f"    fix: {cat['recommendation']}")
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
    platform = data.get("platform")
    if platform is not None:
        click.echo("")
        _print_platform(platform)


def _print_platform(platform: dict) -> None:
    if not platform["available"]:
        click.echo(f"platform: not checked ({platform['reason']})")
        return
    if not platform["protected"]:
        loc = f"{platform['repo']}@{platform['default_branch']}"
        click.echo(f"platform: {loc} - no branch protection")
    else:
        click.echo(f"platform: {platform['repo']}@{platform['default_branch']} - protected")
        click.echo(f"  required reviews        {platform['required_approving_review_count']}")
        click.echo(f"  require code owners     {platform['require_code_owner_reviews']}")
        click.echo(f"  enforce for admins      {platform['enforce_admins']}")
        click.echo(f"  allow force pushes      {platform['allow_force_pushes']}")
        click.echo(f"  require signed commits  {platform['required_signatures']}")
        contexts = platform["required_status_check_contexts"]
        named = ", ".join(contexts) if contexts else "(none named)"
        click.echo(f"  required status checks  {named}")
    for rec in platform["recommendations"]:
        click.echo(f"  fix: {rec}")


if __name__ == "__main__":
    main()
