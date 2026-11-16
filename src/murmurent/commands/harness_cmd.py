"""
Purpose: ``murmurent harness``: the harnesses murmurent knows (the programs
         that can run its agents), each with its place, its models, whether
         its hooks can refuse a call, how it runs headless, whether the lab
         allows it, whether this machine has chosen it, and whether the
         commons are installed into it here. ``enable`` and ``disable``
         record this machine's choice; everything else is read-only.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   The profiles in :mod:`murmurent.core.harness_policy`, the lab's
         ``policy/harnesses.yaml``, ``~/.murmurent/machine.yaml``, the files
         on this machine.
Output:  A table, or ``--json``. Exit 0 always; a problem in the lab's file is
         printed as ``problem: ...`` on stderr and the profile's value kept.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from ..core import harness_policy as _hp


def _table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(str(c).ljust(w) for c, w in zip(header, widths)).rstrip()]
    for row in rows:
        lines.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())
    return "\n".join(lines)


def rows_for(home: Path) -> tuple[list[dict[str, Any]], _hp.HarnessPolicy]:
    policy = _hp.load_harnesses()
    profiles = _hp.profiles()
    chosen = _hp.machine_harnesses()
    rows: list[dict[str, Any]] = []
    for name, facts in policy.harnesses.items():
        profile = profiles[name]
        state = profile.installed(home)
        row = facts.to_dict()
        row["allowed"] = policy.allowed(name)
        row["chosen"] = name in chosen
        row["present"] = profile.present(home)
        row["installed"] = state.yes
        row["installed_detail"] = state.detail
        row["paths"] = profile.install_paths(home).as_dict()
        rows.append(row)
    return rows, policy


@click.group("harness", invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
@click.pass_context
def harness_group(ctx: click.Context, as_json: bool) -> None:
    """The harnesses murmurent knows, and whether each is installed here."""
    if ctx.invoked_subcommand is not None:
        return
    ctx.invoke(harness_list, as_json=as_json)


def _here_cell(r: dict[str, Any]) -> str:
    if not r["allowed"]:
        return "not allowed by the lab"
    if not r["present"]:
        return "not on this machine"
    if r["installed"]:
        return "installed" + ("" if r["chosen"] else ", not chosen")
    return "not installed: " + r["installed_detail"]


@harness_group.command("list")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
def harness_list(as_json: bool) -> None:
    """One row per harness: place, hooks can refuse, headless command, chosen, state here."""
    rows, policy = rows_for(Path.home())
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)
    if as_json:
        click.echo(json.dumps({"harnesses": rows, "enabled": policy.enabled,
                               "chosen": _hp.machine_harnesses(), "problems": policy.problems}, indent=2))
        return
    table = [
        [
            r["name"],
            r["place"],
            "yes" if r["hooks_can_deny"] else "no",
            r["headless"] or "-",
            "yes" if r["chosen"] else "-",
            _here_cell(r),
        ]
        for r in rows
    ]
    click.echo(_table(table, ["harness", "place", "hooks can refuse", "headless", "chosen", "on this machine"]))
    if not _hp.machine_harnesses():
        found = [r["name"] for r in rows if r["allowed"] and r["present"]]
        click.echo("\nNo harness chosen on this machine yet"
                   + (f"; murmurent would use what it finds: {', '.join(found)}." if found else ".")
                   + " Choose with: murmurent harness enable <name>")


def _change(name: str, add: bool) -> None:
    policy = _hp.load_harnesses()
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)
    if name not in policy.harnesses:
        raise click.ClickException(f"{name!r} is not a harness murmurent knows: {', '.join(policy.names())}")
    if add and not policy.allowed(name):
        raise click.ClickException(f"{name} is not allowed by the lab (enabled: in policy/harnesses.yaml "
                                   f"lists {', '.join(policy.enabled or ())})")
    chosen = set(_hp.machine_harnesses())
    if add:
        chosen.add(name)
    else:
        chosen.discard(name)
    stored = _hp.set_machine_harnesses(sorted(chosen))
    click.echo(f"this machine's harnesses: {', '.join(stored) or '(none)'}")
    if add and not _hp.profiles()[name].present(Path.home()):
        click.echo(f"  ! {name} is not on this machine yet; murmurent install --harness {name} will say so")


@harness_group.command("enable")
@click.argument("name")
def harness_enable(name: str) -> None:
    """Record that this machine uses NAME (in ~/.murmurent/machine.yaml)."""
    _change(name, True)


@harness_group.command("disable")
@click.argument("name")
def harness_disable(name: str) -> None:
    """Record that this machine no longer uses NAME. Nothing is uninstalled."""
    _change(name, False)


# ---------------------------------------------------------------------------
# What `murmurent install` calls
# ---------------------------------------------------------------------------


def install_targets(asked: list[str], *, hooks_only: bool = False) -> list[str]:
    """The harnesses an install acts on. Named ones are recorded as this
    machine's choice; with none named, the machine's choice; with no choice,
    every allowed harness that is on the machine. ``--hooks`` alone keeps
    its old meaning: Claude Code only."""
    policy = _hp.load_harnesses()
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)
    if hooks_only and not asked:
        return ["claude_code"]
    if asked:
        for name in asked:
            if name not in policy.harnesses:
                raise click.ClickException(f"{name!r} is not a harness murmurent knows: {', '.join(policy.names())}")
            if not policy.allowed(name):
                raise click.ClickException(f"{name} is not allowed by the lab (enabled: in policy/harnesses.yaml)")
        _hp.set_machine_harnesses(sorted(set(_hp.machine_harnesses()) | set(asked)))
        return list(dict.fromkeys(asked))
    chosen = _hp.chosen_harnesses(policy)
    if not chosen:
        raise click.ClickException(
            "no harness to install into: none chosen on this machine and none of "
            f"{', '.join(policy.allowed_names())} found here. Choose one with: murmurent harness enable <name>")
    if not _hp.machine_harnesses():
        click.echo(f"No harness chosen on this machine; installing into what is here: {', '.join(chosen)}")
    return chosen


def install_into(name: str, *, dry_run: bool = False, all_skills: bool = False) -> None:
    """Render the commons into one harness and print the report."""
    from ..core.commons import commons_root

    profile = _hp.profiles()[name]
    home = Path.home()
    rules = profile.install_paths(home).rules
    where = rules.parent if rules is not None else home
    click.echo(f"{name}: " + ("would write" if dry_run else "writing") + f" the commons into {where}")
    if not profile.present(home):
        click.echo(f"  ! {name} is not on this machine; the files are written anyway and wait for it")
    report = profile.install(home, commons_root(), dry_run=dry_run, all_skills=all_skills)
    for line in report.lines():
        click.echo(line)
