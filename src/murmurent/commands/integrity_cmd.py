"""
Purpose: Implementation of ``murmurent integrity check`` and ``report`` (issue
         #341): the detective's deterministic half. ``check`` runs every
         registry lookup on a manuscript and prints the findings in four tiers;
         ``report`` turns a check's JSON into the manuscript's own text with the
         findings highlighted where they sit, as an HTML page, and into the PDF
         itself when PyMuPDF is installed.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: A manuscript path (``.tex``, ``.md``, ``.txt``, ``.bib`` or ``.pdf``),
       optionally ``--journal`` or ``--issn``; for ``report``, the JSON that
       ``check --json`` printed.
Output: A report on stdout; exit status 1 when any finding is PROVEN, so an
        agent or a script can stop on it. ``report`` writes the files it names.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..core import integrity_check as ic

REGISTRY = Path(__file__).resolve().parents[3] / "docs" / "journals.md"


def cmd_check(path: str, *, journal: str, issn: str, as_json: bool) -> None:
    report = ic.check_file(path, journal=journal, issn=issn, registry=REGISTRY)
    click.echo(ic.format_report(report, as_json=as_json))
    if any(f.tier in ic.FAILING for f in report.findings):
        sys.exit(1)


def cmd_report(findings_json: str, *, out: str, pdf_out: str, title: str) -> None:
    report = ic.Report.from_dict(json.loads(Path(findings_json).read_text(encoding="utf-8")))
    source = Path(report.path)
    if not source.exists():
        raise click.ClickException(f"the manuscript the findings name is not here: {source}")
    text, _ = ic.read_source(source)
    html_path = Path(out) if out else source.with_suffix(".integrity.html")
    html_path.write_text(ic.render_html(report, text, title=title), encoding="utf-8")
    click.echo(f"wrote {html_path}")
    if pdf_out:
        if source.suffix.lower() != ".pdf":
            raise click.ClickException("--pdf-out needs the manuscript itself to be a PDF")
        try:
            n = ic.annotate_pdf(report, source, Path(pdf_out))
        except RuntimeError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"wrote {pdf_out} ({n} highlight{'s' if n != 1 else ''})")
