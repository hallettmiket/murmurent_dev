"""
Purpose: ``murmurent prospect``: the deterministic half of the prospector
         (#313). Profiles, the funder registry, a check that its pages still
         load, the institution's internal deadline, the feed poll a timer
         runs, and the report files from rows the agent wrote.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-12
Input: CLI arguments; ``docs/funders.md``; the institution pack's
       ``funding.yaml``; ``~/.murmurent/prospect/``.
Output: Reports on stdout; files under ``./outputs/prospector/`` on request.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import click

from ..core import institution as _inst
from ..core import prospect as _p


def _pack_or_none(name: str | None) -> _inst.Pack | None:
    root = _inst.find_pack(name)
    if root is None:
        return None
    try:
        return _inst.load_pack(root)
    except _inst.PackError:
        return None


def _date(text: str) -> date:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise click.ClickException(f"dates are YYYY-MM-DD; got {text!r}") from exc


@click.group("prospect", help="Funding search support for the prospector: profiles, the funder registry, "
                              "the internal deadline, the feed poll, the report files.")
def prospect_group() -> None:
    pass


# -- profiles ---------------------------------------------------------------


@prospect_group.group("profile", help="Who is asking: the profile a search starts from.")
def profile_group() -> None:
    pass


@profile_group.command("new")
@click.argument("name")
@click.option("--who", required=True, type=click.Choice(list(_p.WHO)),
              help="student, postdoc, early_pi (within the funders' early-career windows) or pi.")
@click.option("--field", "field_", required=True, help="What the research is about, in public words.")
@click.option("--terms", default="", help="Comma-separated public terms a search may carry.")
@click.option("--citizenship", default="", help="Citizen, permanent resident, or international; many programs turn on it.")
@click.option("--horizon-months", default=12, show_default=True, type=int)
@click.option("--notes", default="")
def profile_new(name: str, who: str, field_: str, terms: str, citizenship: str, horizon_months: int, notes: str) -> None:
    """Record a profile. Nothing here leaves the machine."""
    profile = _p.Profile(name=name, who=who, field=field_,
                         terms=[t.strip() for t in terms.split(",") if t.strip()],
                         citizenship=citizenship, horizon_months=horizon_months, notes=notes)
    try:
        path = _p.save_profile(profile)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Saved profile {name}: {path}")


@profile_group.command("show")
@click.argument("name")
def profile_show(name: str) -> None:
    try:
        prof = _p.load_profile(name)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    for k, v in prof.to_dict().items():
        click.echo(f"{k}: {', '.join(v) if isinstance(v, list) else v}")


@profile_group.command("list")
def profile_list() -> None:
    names = _p.list_profiles()
    click.echo("\n".join(names) if names else "No profiles yet: murmurent prospect profile new <name> --who ... --field ...")


# -- the registry -----------------------------------------------------------


@prospect_group.command("registry")
@click.option("--tier", default="", help="Only the tier whose heading contains this text (Canada, Ontario, Disease, United States, Europe).")
@click.option("--feeds", "feeds_only", is_flag=True, help="Only entries with a feed the poller can read.")
@click.option("--pack", "pack_name", default=None, help="The institution pack to read the institution's tier from.")
def registry(tier: str, feeds_only: bool, pack_name: str | None) -> None:
    """List the funder registry (docs/funders.md) as the prospector reads it."""
    try:
        entries = _p.load_registry()
    except OSError as exc:
        raise click.ClickException(f"cannot read the registry: {exc}") from exc
    if tier:
        entries = [e for e in entries if tier.lower() in e.tier.lower()]
    if feeds_only:
        with_feed = {id(e) for e, _ in _p.feed_sources(entries)}
        entries = [e for e in entries if id(e) in with_feed]
    pack = _pack_or_none(pack_name)
    funding = _p.institution_funding(pack)
    if funding:
        click.echo(f"Institution tier ({pack.unique_name}): {len(funding.get('internal_competitions') or [])} internal "
                   f"competitions, {len(funding.get('screened_lists') or [])} screened lists"
                   + (", internal deadline rule present" if funding.get("internal_deadline") else ", no internal deadline rule"))
    else:
        click.echo("Institution tier: Unknown (no funding.yaml in the institution pack on this machine)")
    current = ""
    for e in entries:
        if e.tier != current:
            current = e.tier
            click.echo(f"\n{current}")
        feeds = f"; feed: {len(e.feeds)}" if e.feeds else ""
        click.echo(f"  {e.agency}: {e.loads.split(',')[0].split(';')[0].strip()}{feeds}; checked {e.checked}")
        click.echo(f"    {e.listing}")
    click.echo(f"\n{len(entries)} entries from {_p.registry_path()}")


@prospect_group.command("check")
@click.option("--tier", default="")
def check(tier: str) -> None:
    """Fetch every registry listing page once and say whether it loads the
    way the registry claims. Public pages, one honest GET each, no retries."""
    entries = _p.load_registry()
    if tier:
        entries = [e for e in entries if tier.lower() in e.tier.lower()]
    results = _p.check_registry(entries)
    bad = 0
    for r in results:
        line = r.line()
        if "<-" in line:
            bad += 1
        click.echo(line)
    click.echo(f"\n{len(results)} pages; {bad} where the registry's Loads column needs updating.")
    sys.exit(1 if bad else 0)


# -- the internal deadline --------------------------------------------------


@prospect_group.command("internal-deadline")
@click.argument("sponsor_date")
@click.option("--kind", default="", help="A variant of the rule, when the pack has one: tri_agency, us_federal, partner_contributions.")
@click.option("--pack", "pack_name", default=None)
def internal_deadline(sponsor_date: str, kind: str, pack_name: str | None) -> None:
    """The institution's internal deadline for a sponsor deadline, from the
    research office's rule in the institution pack, over the pack's holidays."""
    pack = _pack_or_none(pack_name)
    result = _p.internal_deadline(pack, _date(sponsor_date), kind)
    click.echo(result.explanation)
    if result.rule:
        click.echo(f"Rule: {result.rule}")
        click.echo(f"Source: {result.source} (read {result.date_read})")


# -- the feed poll ----------------------------------------------------------


@prospect_group.command("feeds")
@click.option("--post", is_flag=True, help="Post what is new to this repository's Slack channel, routed as murmurent project note is.")
@click.option("--dry-run", is_flag=True, help="Do not remember what was seen.")
def feeds(post: bool, dry_run: bool) -> None:
    """Read every feed the registry names (and CIHR's ResearchNet table), report
    what is new since the last run, and remember what was seen. No model."""
    entries = _p.load_registry()
    report = _p.poll_feeds(entries, remember=not dry_run)
    note = _p.format_poll_note(report, entries)
    click.echo(note)
    for what, why in report.failed:
        click.echo(f"  could not read {what}: {why}")
    if post and not report.first_run and report.new:
        from ..core.slack_routing import post_note
        ok, _route, detail = post_note(note)
        click.echo(f"Slack: {detail}")
        if not ok:
            sys.exit(1)


# -- the report -------------------------------------------------------------


@prospect_group.command("report")
@click.argument("rows_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", default="./outputs/prospector", show_default=True)
@click.option("--slug", default="funding", show_default=True)
def report(rows_file: str, out: str, slug: str) -> None:
    """Render rows the prospector wrote (rows.yaml) as a self-contained HTML
    page and a calendar file of the deadlines."""
    try:
        head, rows = _p.load_rows(Path(rows_file))
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"cannot read {rows_file}: {exc}") from exc
    html_path, ics_path = _p.write_report(head, rows, Path(out), slug)
    dated = sum(1 for r in rows for k in ("registration", "full_deadline", "internal_deadline") if _p._date_only(r.get(k, "")))
    click.echo(f"Wrote {html_path} ({len(rows)} rows) and {ics_path} ({dated} deadlines).")
