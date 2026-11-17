"""
Purpose: ``murmurent sessions``: yesterday's and today's sessions across
         every harness on this machine, one row each: when, harness, model,
         place, project, tool calls, refusals. Read-only.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   :mod:`murmurent.core.sessions`.
Output:  A table, or ``--json``. A harness whose transcripts could not be
         read has its own row saying so. Exit 0 always.
"""

from __future__ import annotations

import datetime as _dt
import json

import click

from ..core import sessions as _sessions


def _table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(header, widths)).rstrip()]
    for row in rows:
        lines.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def _when(iso: str) -> str:
    moment = _sessions._parse_time(iso)
    if moment is None:
        return iso or "-"
    local = moment.astimezone()
    today = _dt.datetime.now().astimezone().date()
    if local.date() == today:
        return local.strftime("%H:%M")
    return local.strftime("%Y-%m-%d %H:%M")


@click.command("sessions")
@click.option("--since", default=None, metavar="DATE",
              help="Only sessions touched on or after this date (YYYY-MM-DD). Default: yesterday.")
@click.option("--all", "everything", is_flag=True, default=False, help="Every session on this machine.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
def sessions_command(since: str | None, everything: bool, as_json: bool) -> None:
    """One row per session across every harness on this machine."""
    if everything:
        since_date = None
    elif since:
        try:
            since_date = _dt.date.fromisoformat(since)
        except ValueError:
            raise click.ClickException(f"--since takes a date like 2026-11-16, not {since!r}")
    else:
        since_date = _dt.date.today() - _dt.timedelta(days=1)
    rows = _sessions.sessions(since_date)
    if as_json:
        click.echo(json.dumps({"since": since_date.isoformat() if since_date else None,
                               "sessions": [r.to_dict() for r in rows]}, indent=2))
        return
    table = []
    notes = []
    for r in rows:
        if r.note:
            notes.append(f"{r.harness}: {r.note}")
            continue
        table.append([
            _when(r.start), _when(r.end), r.harness, r.model or "-", r.place,
            r.project or r.repo or "-", str(r.calls), str(r.refusals), _sessions.short_id(r.session),
        ])
    if table:
        click.echo(_table(table, ["start", "end", "harness", "model", "place", "project", "calls", "refusals", "session"]))
    else:
        click.echo("no sessions" + (f" since {since_date}" if since_date else ""))
    for n in notes:
        click.echo(f"  {n}")
