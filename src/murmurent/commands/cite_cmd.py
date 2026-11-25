"""
Purpose: Implementation of ``murmurent cite check``: look up every DOI, PMID
         and arXiv ID in a file and report any that do not exist, name a
         different paper, or have been retracted (issue #225).
Author: Mike Hallett (with Claude Code)
Date: 2026-10-23
Input: A ``.bib``, ``.tex``, ``.md`` or text file path, forwarded from
       :mod:`murmurent.cli`.
Output: A report on stdout; exit status 1 when any identifier is NOT FOUND,
        MISMATCH or RETRACTED, so a script or an agent can stop on it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from ..core import cite_check, cite_fetch


def cmd_check(path: str, *, as_json: bool) -> None:
    """Check the file at ``path`` and exit non-zero on a failing identifier."""
    results = cite_check.check_file(Path(path))
    click.echo(cite_check.format_report(results, as_json=as_json))
    if any(r.status in cite_check.FAILING for r in results):
        sys.exit(1)


def _library_resolver(given: str | None) -> tuple[str, str]:
    """The template and a note on its origin, in the order the docs promise."""
    if given:
        return given, "from --resolver"
    env = os.environ.get("MURMURENT_LIBRARY_RESOLVER", "").strip()
    if env:
        return env, "from MURMURENT_LIBRARY_RESOLVER"
    try:
        from ..core import institution as _inst
        root = _inst.find_pack()
    except Exception:  # noqa: BLE001  (no centre, no pack: no resolver)
        root = None
    template, note = cite_fetch.pack_library_resolver(root)
    if template:
        return template, note
    return "", ("none set: record one in the institution pack's library.yaml, or set "
                "MURMURENT_LIBRARY_RESOLVER")


def cmd_fetch(path: str, *, out: str | None, as_json: bool, email: str | None,
              resolver: str | None) -> None:
    """Write the reading ledger for the file at ``path``. Exit status is always 0:
    the ledger is information, not a verdict. The library link comes from
    ``--resolver``, else ``MURMURENT_LIBRARY_RESOLVER``, else the institution
    pack's ``library.yaml``; the ledger says which."""
    resolver, note = _library_resolver(resolver)
    fetcher = cite_fetch.Fetcher(unpaywall_email=email, library_resolver=resolver)
    results = cite_fetch.fetch_file(Path(path), fetcher)
    text = cite_fetch.format_ledger(results, as_json=as_json, source=Path(path).name,
                                    library_note=note)
    if out is None:
        click.echo(text, nl=False)
        return
    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    counts = {s: sum(1 for r in results if r.status == s) for s in cite_fetch.STATUSES}
    summary = ", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n) or "nothing to fetch"
    click.echo(f"{len(results)} identifiers: {summary}. Ledger: {dest}")
