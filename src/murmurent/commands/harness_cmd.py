"""
Purpose: ``murmurent harness``: the harnesses murmurent knows (the programs
         that can run its agents), each with its place, its models, whether
         its hooks can refuse a call, how it runs headless, and whether the
         commons are installed into it on this machine. Read-only.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   The profiles in :mod:`murmurent.core.harness_policy`, the lab's
         ``policy/harnesses.yaml``, the files on this machine.
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


def _rows(home: Path) -> tuple[list[dict[str, Any]], _hp.HarnessPolicy]:
    policy = _hp.load_harnesses()
    profiles = _hp.profiles()
    rows: list[dict[str, Any]] = []
    for name, facts in policy.harnesses.items():
        profile = profiles[name]
        state = profile.installed(home)
        row = facts.to_dict()
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


@harness_group.command("list")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the rows as JSON.")
def harness_list(as_json: bool) -> None:
    """One row per harness: place, hooks can refuse, headless command, installed here."""
    rows, policy = _rows(Path.home())
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)
    if as_json:
        click.echo(json.dumps({"harnesses": rows, "problems": policy.problems}, indent=2))
        return
    table = [
        [
            r["name"],
            r["place"],
            "yes" if r["hooks_can_deny"] else "no",
            r["headless"] or "-",
            "yes" if r["installed"] else f"no: {r['installed_detail']}",
        ]
        for r in rows
    ]
    click.echo(_table(table, ["harness", "place", "hooks can refuse", "headless", "installed here"]))
