"""
Purpose: ``murmurent route <kind>``: the row of the lab's routing table for a
         kind of task (which harness, model and place take it), refused when
         the project's sensitivity is not allowed at that place. Prints and
         nothing more; ``--command`` also prints the headless command line
         the harness would run, built, never run.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   ``policy/models.yaml`` through :mod:`murmurent.core.route_policy`;
         a project name, or the project of the current folder.
Output:  One row, or why not. Exit 0 always, as ``machines`` does; a problem
         in the lab's file is printed as ``problem: ...`` on stderr.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..core import route_policy as _rp


def _problems(policy: _rp.RoutePolicy) -> None:
    for problem in policy.problems:
        click.echo(f"problem: {problem}", err=True)


@click.command("route")
@click.argument("kind", required=False)
@click.option("--project", default=None, help="The project whose sensitivity decides; default: the project here.")
@click.option("--command", "prompt", default=None, metavar="PROMPT",
              help="Also print the headless command line the route's harness would run for PROMPT. Not run.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the answer as JSON.")
def route_command(kind: str | None, project: str | None, prompt: str | None, as_json: bool) -> None:
    """Which harness, model and place take KIND of task, by the lab's routing table.

    Without KIND, every route the lab has declared.
    """
    policy = _rp.load_routes()
    _problems(policy)
    if kind is None:
        rows = [r.to_dict() for r in policy.routes.values()]
        if as_json:
            click.echo(json.dumps({"routes": rows, "problems": policy.problems}, indent=2))
            return
        if not rows:
            click.echo("no routes declared: copy templates/models.yaml to policy/models.yaml in the lab records")
            return
        width = max(len(r["kind"]) for r in rows)
        for r in rows:
            click.echo(f"{r['kind'].ljust(width)}  {r['harness']}  {r['model']}  {r['place']}  "
                       f"data: {', '.join(r['data'])}" + (f"  agent: {r['agent']}" if r["agent"] else ""))
        return
    answer = _rp.route_for(kind, project=project, policy=policy)
    cmd = _rp.headless_command(answer.route, prompt, Path.cwd()) if (answer.ok and prompt) else None
    if as_json:
        click.echo(json.dumps({
            "kind": kind, "route": answer.route.to_dict() if answer.route else None,
            "ok": answer.ok, "refused": answer.refused, "missing": answer.missing,
            "command": cmd, "problems": policy.problems,
        }, indent=2))
        return
    if answer.missing:
        click.echo(answer.missing)
        return
    assert answer.route is not None
    r = answer.route
    if answer.refused:
        click.echo(f"refused: {answer.refused}")
        return
    click.echo(f"{kind}: {r.harness} ({r.model}) at {r.place}" + (f", agent {r.agent}" if r.agent else "")
               + f"; data: {', '.join(r.data)}" + (f"\n  why: {r.why}" if r.why else ""))
    if cmd:
        click.echo("  command (not run): " + " ".join(_quote(c) for c in cmd))


def _quote(part: str) -> str:
    import shlex

    return shlex.quote(part)
