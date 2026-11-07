"""
Purpose: ``murmurent notebook``: the personal lab notebook's verbs (issues
         #292, #293, #294). ``split`` moves pasted prompts out of old entries;
         ``add`` drops text, images, handwriting, sound, video and result
         files into today's entry; ``open`` fetches a file the entry links
         to on the server; ``report`` assembles what one audience may read.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   The personal vault, the project registry, the hosts file.
Output:  Files in the vault and, for large things, under append_only/ on the
         project's data host. Each command prints what it did.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import click

from ..core import lab_notebook as _nb


@click.group("notebook", help="Your lab notebook: notes, captured media, and reports.")
def notebook_group() -> None:
    """The notes stream is ``<vault>/lab-notebook/<date>.md``; the prompts you
    give Claude Code are recorded separately under ``<vault>/sessions/``."""


# ---------------------------------------------------------------------------
# split (#292)
# ---------------------------------------------------------------------------


@notebook_group.command(
    "split",
    help="Move prompt-shaped blocks (long paragraphs addressed to Claude) out of "
         "existing entries into sessions/<date>/pasted.md, keeping each original "
         "under obsolete/. Prints what it moves; deletes nothing.")
@click.option("--dry-run", is_flag=True, help="Show the plan; write nothing.")
def notebook_split(dry_run: bool) -> None:
    raise SystemExit(cmd_split(dry_run=dry_run))


def cmd_split(*, dry_run: bool = False) -> int:
    try:
        paths = _nb.require_paths()
    except _nb.NotebookError as exc:
        click.echo(f"error: {exc}")
        return 1
    moves = _nb.plan_split(paths)
    if not moves:
        click.echo(f"Nothing to move: no prompt-shaped blocks in {paths.notebook}.")
        return 0
    if dry_run:
        click.echo(f"Would move pasted prompts from {len(moves)} entr{'y' if len(moves) == 1 else 'ies'}:")
        for mv in moves:
            assert mv.target is not None and mv.obsolete_copy is not None
            click.echo(f"  {paths.rel(mv.entry)}: {len(mv.blocks)} block(s), {mv.chars} characters "
                       f"-> {paths.rel(mv.target)} (original kept at {paths.rel(mv.obsolete_copy)})")
            for b in mv.blocks:
                first = b.strip().splitlines()[0] if b.strip() else ""
                click.echo(f"      \"{first[:90]}{'...' if len(first) > 90 else ''}\"")
        click.echo("Nothing written (--dry-run).")
        return 0
    for line in _nb.apply_split(paths, moves):
        click.echo(line)
    click.echo(f"Moved pasted prompts out of {len(moves)} entr{'y' if len(moves) == 1 else 'ies'}. "
               f"Originals are under {paths.rel(paths.obsolete)}/; nothing was deleted. "
               "Read the moved blocks before trusting the split.")
    return 0


def _today() -> str:
    return _dt.date.today().isoformat()


__all__ = ["notebook_group", "cmd_split"]
