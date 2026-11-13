"""
Purpose: ``murmurent machines``: the machines a person can reach, how busy
         each one is, and how full its storage is, in one table or as JSON.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-13
Input:   The command line; the lab's ``policy/machines.yaml``; the person's
         ``hosts.yaml``.
Output:  Text in the terminal, or JSON with ``--json`` for the millwright and
         the dashboard. The logic is in ``core/machine_policy.py``.

Guide: ``docs/machines.md``.
"""

from __future__ import annotations

import json
from typing import Any

import click

from ..core import machine_policy as _mp
from ..core.run_cards import format_size

#: How many people the load table names per machine; --json carries them all.
WHO_SHOWN = 8


def _table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(header, widths)).rstrip()]
    for row in rows:
        lines.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def _when(iso: str) -> str:
    """A time of day for today, else the date."""
    import datetime as _dt

    try:
        moment = _dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or "never"
    now = _dt.datetime.now().astimezone()
    if moment.date() == now.date():
        return moment.strftime("%H:%M")
    return moment.strftime("%Y-%m-%d %H:%M")


def _emit_json(payload: Any) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))


def _problems(policy: _mp.MachinePolicy) -> None:
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)


def _members() -> tuple[_mp.MachinePolicy, list[_mp.Member]]:
    policy = _mp.load_machines()
    return policy, _mp.person_set(policy)


@click.group("machines", invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
@click.option("--no-check", is_flag=True, default=False,
              help="Do not reach out now; show what the last check found.")
@click.pass_context
def machines_group(ctx: click.Context, as_json: bool, no_check: bool) -> None:
    """The machines you can reach: this computer, the lab's servers, its clusters.

    With no further word, one row per declared machine: its kind, whether your
    login is recorded, whether it answers, and when that was last checked.
    """
    if ctx.invoked_subcommand is not None:
        return
    policy, members = _members()
    if no_check:
        remembered = _mp.read_state()
        reports = []
        for m in members:
            if not m.set_up:
                reports.append(_mp.Status(name=m.name, profile=m.machine.profile, set_up=False,
                                          problem=_mp.setup_hint(m.machine)))
                continue
            last = remembered.get(m.name, {})
            reports.append(_mp.Status(name=m.name, profile=m.machine.profile, set_up=True,
                                      reachable=bool(last.get("reachable")),
                                      checked_at=str(last.get("checked_at") or ""),
                                      detail=str(last.get("detail") or ""),
                                      problem=str(last.get("problem") or "")))
    else:
        reports = _mp.ask_all(members, "status")
        _mp.remember(reports)
    if as_json:
        _emit_json({"machines": [
            {**r.to_dict(), "description": m.machine.description, "login": m.login}
            for r, m in zip(reports, members)
        ], "problems": policy.problems})
        return
    rows = []
    for r, m in zip(reports, members):
        if not r.set_up:
            state, checked = r.problem, "never"
        elif r.reachable:
            state, checked = "reachable" + (f" ({r.detail})" if r.detail else ""), _when(r.checked_at)
        else:
            state, checked = r.problem or "unreachable", _when(r.checked_at)
        kind = m.machine.profile + (", this computer" if m.machine.here else "")
        rows.append([m.name, kind, m.login or "-", state, checked])
    click.echo(_table(rows, ["machine", "kind", "login", "state", "checked"]))
    for m in members:
        if m.machine.description and not m.machine.is_local():
            click.echo(f"  {m.name}: {m.machine.description}")
    _problems(policy)


@machines_group.command("add")
@click.argument("name")
@click.option("--ssh-host", required=True, help="login@address, or an alias from ~/.ssh/config.")
@click.option("--user", default="", help="Your login on the machine, when the address does not say.")
def machines_add(name: str, ssh_host: str, user: str) -> None:
    """Record your own login for a machine the lab declares."""
    policy = _mp.load_machines()
    machine = policy.get(name)
    if machine is None:
        known = ", ".join(n for n in policy.names() if n != _mp.LAPTOP_NAME) or "none"
        raise click.ClickException(
            f"no machine named {name!r} in the lab's policy (known: {known}). The PI adds one in "
            "policy/machines.yaml of the lab records repository; templates/machines.yaml is an example."
        )
    if machine.runs_here():
        raise click.ClickException("this computer needs no login; it is always in your set")
    path = _mp.register_login(machine, ssh_host, user)
    click.echo(f"Recorded {ssh_host} as your login for {name} in {path}.")
    if machine.profile == "alliance":
        click.echo(f"Check it: murmurent cluster test --cluster {machine.cluster or name}")
    else:
        click.echo("Check it: murmurent machines")


def _count(busy: int | None, total: int | None) -> str:
    if total is None:
        return "-"
    if busy is None:
        return f"? of {total}"
    return f"{busy} of {total}"


@machines_group.command("load")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
def machines_load(as_json: bool) -> None:
    """Cores and GPUs busy, jobs or sessions, and who, on every machine you have set up."""
    policy, members = _members()
    reports = _mp.ask_all(members, "load")
    _mp.remember(reports)
    if as_json:
        _emit_json({"machines": [r.to_dict() for r in reports], "problems": policy.problems})
        return
    rows = []
    for r in reports:
        if not r.set_up or not r.reachable:
            rows.append([r.name, r.profile, r.problem or "unreachable", "", "", ""])
            continue
        if r.profile == "alliance":
            work = f"{r.jobs or 0} running, {r.sessions or 0} waiting"
        else:
            n = r.sessions
            work = f"{n if n is not None else '?'} {'person' if n == 1 else 'people'} logged in"
        who = r.who[:WHO_SHOWN] + ([f"and {len(r.who) - WHO_SHOWN} more"] if len(r.who) > WHO_SHOWN else [])
        rows.append([r.name, r.profile, _count(r.cores_busy, r.cores_total),
                     _count(r.gpus_busy, r.gpus_total) if r.gpus_total else "none",
                     work, ", ".join(who) or "-"])
    click.echo(_table(rows, ["machine", "kind", "cores busy", "GPUs busy", "jobs or sessions", "who"]))
    for r in reports:
        for p in r.problems:
            click.echo(f"  {r.name}: {p}")
    _problems(policy)


def _tier_cell(t: _mp.TierUse) -> str:
    if t.used is None:
        return t.note or "no figure"
    text = format_size(t.used)
    if t.quota:
        text += f" of {format_size(t.quota)} ({t.percent:.0f}%)"
    return text


def _files_cell(t: _mp.TierUse) -> str:
    if t.files is None:
        return "-"
    if t.files_quota:
        return f"{t.files:,} of {t.files_quota:,} ({t.files_percent:.0f}%)"
    return f"{t.files:,}"


@machines_group.command("usage")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
def machines_usage(as_json: bool) -> None:
    """Each storage tier on every machine you have set up: space and files used of quota."""
    policy, members = _members()
    reports = _mp.ask_all(members, "usage")
    _mp.remember(reports)
    if as_json:
        _emit_json({"machines": [r.to_dict() for r in reports], "problems": policy.problems})
        return
    rows = []
    for r in reports:
        if not r.set_up or not r.reachable:
            rows.append([r.name, "", "", r.problem or "unreachable", "", ""])
            continue
        nearest = r.nearest_limit()
        for t in r.tiers:
            flag = "nearest its limit" if nearest is not None and t is nearest and len(r.tiers) > 1 else ""
            note = t.note if t.used is not None else ""
            rows.append([r.name, t.name, t.path, _tier_cell(t), _files_cell(t),
                         "; ".join(x for x in (flag, note) if x)])
        if not r.tiers:
            rows.append([r.name, "", "", r.problem or "no tiers declared", "", ""])
    click.echo(_table(rows, ["machine", "tier", "path", "space used", "files", "note"]))
    for r in reports:
        for p in r.problems:
            click.echo(f"  {r.name}: {p}")
    _problems(policy)
