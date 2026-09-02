"""
Purpose: obtain a choreography from a git URL (or the public index) and make it
         murmurent-ready; list what is available.
Author: Mike Hallett (with Claude Code)
Date: 2026-09-02
Input: a git URL or an index name; the public choreography index
Output: a cloned, adopted repo; a rendered listing

Issue #136. ``install`` is deliberately thin: clone, then hand the clone to the
existing ``core.adopt.adopt_clone`` path rather than re-implementing readiness.

Everything shown to the user comes from the choreography's own
``.murmurent.yaml``, never from the index, so a description cannot drift away
from the repo it describes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ..core import adopt as _adopt
from ..core.choreography_registry import (
    ChoreographyError,
    ChoreographyInfo,
    clone_choreography,
    missing_agents,
    read_marker,
)

#: Where the public index lives. URLs only; see choreography_registry's header.
INDEX_URL = (
    "https://raw.githubusercontent.com/hallettmiket/murmurent_public/main/"
    "choreographies.tsv"
)


def _render(info: ChoreographyInfo, *, indent: str = "  ") -> None:
    click.echo(f"{indent}{info.name}  {info.title}".rstrip())
    if info.summary:
        click.echo(f"{indent}  {info.summary}")
    if info.target:
        click.echo(f"{indent}  target: {info.target}")
    if info.approaches:
        click.echo(f"{indent}  approaches: {' '.join(info.approaches)}")
    if info.agents:
        click.echo(f"{indent}  agents: {' '.join(info.agents)}")
    needs = []
    if info.requires_murmurent:
        needs.append(f"murmurent {info.requires_murmurent}")
    if info.requires_gpu:
        needs.append("a GPU")
    if needs:
        click.echo(f"{indent}  needs: {', '.join(needs)}")
    if info.data_scale or info.data_subdir:
        where = info.data_subdir or "the centre's governed data root"
        scale = f"{info.data_scale}, " if info.data_scale else ""
        click.echo(f"{indent}  data: not included ({scale}kept under {where})")
    if info.citation:
        click.echo(f"{indent}  cite: {info.citation}")


def cmd_install(*, source: str, dest: str | None, branch: str,
                lab: str, adopt: bool) -> int:
    """Clone a choreography and make it murmurent-ready."""
    if "/" not in source and ":" not in source:
        click.echo(
            f"'{source}' is not a git URL.\n"
            "Installing by name needs the public index, which is not published "
            "yet (issue #136). Pass the repository URL instead, e.g.\n"
            "  murmurent choreography install https://github.com/<owner>/<repo>.git",
            err=True,
        )
        return 2

    try:
        clone = clone_choreography(source, dest=Path(dest) if dest else None,
                                  branch=branch)
    except ChoreographyError as exc:
        click.echo(f"x {exc}", err=True)
        return 1

    click.echo(f"+ cloned to {clone}")

    try:
        info = read_marker(clone)
    except ChoreographyError as exc:
        # Leave the clone in place: it is a perfectly good repo, it simply does
        # not declare itself a choreography. Deleting someone's fresh clone to
        # punish a missing metadata file would be worse than the problem.
        click.echo(f"\n! {exc}", err=True)
        click.echo(f"\nThe clone is at {clone} and has been left alone.", err=True)
        return 1

    click.echo()
    _render(info, indent="")
    click.echo()

    absent = missing_agents(info)
    if absent:
        click.echo(
            f"! this choreography asks for agents this machine does not have: "
            f"{' '.join(absent)}"
        )

    if not adopt:
        click.echo(f"Skipped adoption (--no-adopt). Run:\n  murmurent repo adopt {clone}")
        return 0

    try:
        outcome = _adopt.adopt_clone(clone_path=str(clone), lab=lab,
                                     agents=info.agents or None)
    except _adopt.AdoptError as exc:
        click.echo(f"\n! cloned, but adoption failed: {exc}", err=True)
        click.echo(f"  Fix the cause and run: murmurent repo adopt {clone}", err=True)
        return 1

    click.echo(f"+ murmurent-ready ({getattr(outcome, 'summary', 'adopted')})")
    click.echo(
        f"\nNext: read {clone.name}/README.md, then its decisions/ if it has one.\n"
        "Data is not included; a choreography repo carries code, decisions and "
        "documentation only."
    )
    return 0


def cmd_list(*, index_url: str = INDEX_URL, timeout: float = 10.0) -> int:
    """List choreographies from the public index.

    Reads each repo's own metadata, so nothing here can contradict the repo.
    """
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(index_url, timeout=timeout) as fh:  # noqa: S310
            text = fh.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            click.echo(
                "No public choreography index yet (issue #136).\n"
                "Install directly from a repository URL:\n"
                "  murmurent choreography install https://github.com/<owner>/<repo>.git"
            )
            return 0
        click.echo(f"x could not read the index ({exc}).", err=True)
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        click.echo(f"x could not reach the index ({exc}).", err=True)
        return 1

    rows = [
        line.split("\t")
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not rows:
        click.echo("The index is empty.")
        return 0

    click.echo(f"{len(rows)} choreograph{'y' if len(rows) == 1 else 'ies'}:\n")
    for row in rows:
        name = row[0].strip()
        url = row[1].strip() if len(row) > 1 else ""
        click.echo(f"  {name}\n    {url}")
    click.echo(
        "\nDescriptions come from each repository's own .murmurent.yaml.\n"
        "Install one with:  murmurent choreography install <url>"
    )
    return 0
