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


def _capture_kinds() -> tuple[str, ...]:
    return ("image", "handwritten", "sound", "video", "file")


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


# ---------------------------------------------------------------------------
# add + open (#293)
# ---------------------------------------------------------------------------


@notebook_group.command(
    "add",
    help="Add to today's entry: a line of text, or a file (photo, handwritten page, "
         "sound note, video, result file). Small result files stay in the vault; "
         "images, sound, video and large files go to append_only/<project>/notebook/"
         "<date>/ on the project's data host, and the entry keeps the link, a "
         "thumbnail or poster frame, and any machine-made text marked as such.")
@click.argument("what")
@click.option("--project", default="", help="Project (default: the one this folder belongs to).")
@click.option("--host", "host_name", default="",
              help="Data host for large files (default: the project's host from its record).")
@click.option("--handwritten", is_flag=True, help="The image is a handwritten page to transcribe.")
@click.option("--kind", "kind", type=click.Choice(["text", *_capture_kinds()]), default="",
              help="Force the kind instead of inferring it from the file's extension.")
@click.option("--note", default="", help="A line of text to put beside the file.")
@click.option("--sensitivity", default="",
              help="Override the project's tier (standard, restricted, protected).")
@click.option("--date", "date", default="", help="Entry date (default: today).")
@click.option("--dry-run", is_flag=True, help="Show what would happen; write and send nothing.")
def notebook_add(what: str, project: str, host_name: str, handwritten: bool, kind: str,
                 note: str, sensitivity: str, date: str, dry_run: bool) -> None:
    raise SystemExit(cmd_add(what, project=project, host_name=host_name, handwritten=handwritten,
                             kind=kind, note=note, sensitivity=sensitivity, date=date,
                             dry_run=dry_run))


def cmd_add(what: str, *, project: str = "", host_name: str = "", handwritten: bool = False,
            kind: str = "", note: str = "", sensitivity: str = "", date: str = "",
            dry_run: bool = False, transcriber=None, when: _dt.datetime | None = None) -> int:
    from ..core import notebook_capture as _cap

    try:
        paths = _nb.require_paths()
    except _nb.NotebookError as exc:
        click.echo(f"error: {exc}")
        return 1
    when = when or _dt.datetime.now()
    if date:
        try:
            d = _dt.date.fromisoformat(date)
        except ValueError:
            click.echo(f"error: --date must be YYYY-MM-DD, not {date!r}")
            return 1
        when = when.replace(year=d.year, month=d.month, day=d.day)

    src = Path(what).expanduser()
    is_file = kind != "text" and src.is_file()
    try:
        name, tier, rec_host = _cap.project_context(project)
    except _cap.CaptureError as exc:
        click.echo(f"error: {exc}")
        return 1
    if sensitivity:
        tier = sensitivity
    elif rec_host == "":
        click.echo(f"note: project {name!r} has no record on this machine; treating it as "
                   "standard (use --sensitivity to change that)")
    host_name = host_name or rec_host or "local"

    try:
        if not is_file:
            if kind and kind != "text":
                click.echo(f"error: no file at {src}")
                return 1
            cap = _cap.add_text(paths, what, project=name, sensitivity=tier, when=when,
                                dry_run=dry_run)
        else:
            k = kind or _cap.infer_kind(src, handwritten=handwritten)
            if handwritten and k == "image":
                k = "handwritten"
            cap = _cap.add_file(paths, src, kind=k, project=name, sensitivity=tier,
                                host_name=host_name, when=when, note=note, dry_run=dry_run,
                                transcriber=transcriber)
    except _cap.CaptureError as exc:
        click.echo(f"error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - an SSH failure must be read, not traced
        click.echo(f"error: {exc}")
        return 1

    head = "Would add" if dry_run else "Added"
    click.echo(f"{head} {cap.kind} to {paths.rel(cap.entry)} (project {cap.project}, {cap.sensitivity}):")
    for line in cap.block:
        click.echo(f"    {line}")
    if cap.link:
        click.echo(f"Original {'would go' if dry_run else 'sent'} to {cap.link} (append-only: never edited there).")
    for f in cap.vault_files:
        click.echo(f"In the vault: {paths.rel(f)}")
    for n in cap.notes:
        click.echo(f"Note: {n}")
    if dry_run:
        click.echo("Nothing written (--dry-run).")
    return 0


@notebook_group.command(
    "open",
    help="Fetch a copy of a file the notebook links to (a `<host>:<path>` link from an "
         "entry) into a local cache folder and open it. The copy is for looking at; "
         "the file on the host is the record.")
@click.argument("link")
@click.option("--no-open", is_flag=True, help="Fetch only; print the local path.")
def notebook_open(link: str, no_open: bool) -> None:
    raise SystemExit(cmd_open(link, no_open=no_open))


def cmd_open(link: str, *, no_open: bool = False) -> int:
    import os
    import subprocess
    import sys

    from ..core import notebook_capture as _cap

    home = Path(os.environ.get("MURMURENT_HOME", "~/.murmurent")).expanduser()
    try:
        local = _cap.fetch(link, home / "notebook_cache")
    except _cap.CaptureError as exc:
        click.echo(f"error: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: {exc}")
        return 1
    click.echo(f"Copy at {local}")
    if no_open:
        return 0
    opener = ["open"] if sys.platform == "darwin" else ["xdg-open"]
    try:
        subprocess.Popen([*opener, str(local)])  # noqa: S603
    except OSError as exc:
        click.echo(f"could not open it here ({exc}); the copy is at {local}")
    return 0


__all__ = ["notebook_group", "cmd_split", "cmd_add", "cmd_open"]
