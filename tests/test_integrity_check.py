"""
Purpose: Pin ``murmurent integrity check`` and ``report`` (issue #341) on a
         planted manuscript: a citation that does not exist, a GEO accession
         GEO cannot find, a public one, data "on request", a leftover phrase
         from a language model, and a journal DOAJ does not list. Every
         registry answer is canned, so nothing here touches the network, and
         each finding must land in the tier the evidence supports: PROVEN only
         where a registry's own answer is the proof.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: ``tmp_path`` files, a fake ``get_json`` and a fake ``get_text``.
Output: pytest cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.core import cite_check as cc
from murmurent.core import integrity_check as ic

BASSET = {
    "title": ["A novel metalloproteinase gene specifically expressed in stromal cells of breast carcinomas"],
    "author": [{"family": "Basset", "given": "P."}],
    "issued": {"date-parts": [[1990, 12]]},
}

MANUSCRIPT = """# Stromal signatures in ductal carcinoma in situ

We build on Basset et al. (doi:10.1038/348699a0) and on the method of
Nobody et al. (doi:10.9999/does.not.exist).

## Data availability

Expression profiles are deposited in GEO under GSE2034. The imaging cohort
is deposited under GSE99999999. Clinical covariates are available from the
corresponding author upon reasonable request.

As an AI language model, I cannot access patient records directly.
"""

GEO_PUBLIC = "^SERIES = GSE2034\n!Series_title = Breast cancer relapse free survival\n!Series_status = Public on Feb 23 2005\n"
GEO_MISSING = "Could not find a public or private accession GSE99999999 in GEO."


def fake_get_json(url: str, params: dict):
    if url.startswith(cc.CROSSREF):
        doi = url[len(cc.CROSSREF):]
        if doi == "10.1038/348699a0":
            return {"message": BASSET}
        return None
    if url.startswith(cc.DATACITE) or url.startswith(cc.HANDLE):
        return None
    if url.startswith(ic.DOAJ):
        return {"results": []}
    raise AssertionError(f"unexpected JSON request {url}")


def fake_get_text(url: str, params: dict):
    assert url == ic.GEO
    return {"GSE2034": GEO_PUBLIC, "GSE99999999": GEO_MISSING}[params["acc"]]


@pytest.fixture
def report(tmp_path: Path) -> ic.Report:
    path = tmp_path / "paper.md"
    path.write_text(MANUSCRIPT, encoding="utf-8")
    resolver = cc.Resolver(get_json=fake_get_json, sleep=lambda s: None)
    archives = ic.Archives(get_json=fake_get_json, get_text=fake_get_text, sleep=lambda s: None)
    return ic.check_file(path, journal="Journal of Imaginary Results", resolver=resolver, archives=archives,
                         registry=tmp_path / "no_registry.md", today="2026-11-21")


def by(report: ic.Report, check: str, ident: str) -> ic.Finding:
    hits = [f for f in report.findings if f.check == check and ident in f.ident]
    assert len(hits) == 1, [(f.check, f.ident) for f in report.findings]
    return hits[0]


def test_a_missing_citation_is_proven_with_the_registry_answer(report):
    f = by(report, "citation", "10.9999/does.not.exist")
    assert f.tier == ic.PROVEN
    assert f.line == 4 and f.snippet == "10.9999/does.not.exist"
    assert "no registry" in f.detail.lower() or "not found" in f.detail.lower() or "does not exist" in f.detail.lower()


def test_a_real_citation_is_clean(report):
    f = by(report, "citation", "10.1038/348699a0")
    assert f.tier == ic.CLEAN
    assert "metalloproteinase" in f.detail


def test_a_geo_accession_geo_cannot_find_is_proven(report):
    f = by(report, "data", "GSE99999999")
    assert f.tier == ic.PROVEN
    assert f.line == 9 and "could not be found" in f.detail
    assert f.link.endswith("acc=GSE99999999")


def test_a_public_geo_accession_is_clean(report):
    f = by(report, "data", "GSE2034")
    assert f.tier == ic.CLEAN and "Public on Feb 23 2005" in f.detail


def test_on_request_wording_is_noted_not_a_violation(report):
    f = by(report, "availability", "on request")
    assert f.tier == ic.NOTED
    assert f.line == 9, "anchored to the line the wrapped phrase starts on"
    assert f.snippet == "available from the corresponding author upon reasonable request"
    assert "journal's policy" in f.detail


def test_leftover_model_phrase_is_noted_and_scores_nothing(report):
    f = by(report, "ai_residue", "As an AI language model")
    assert f.tier == ic.NOTED
    assert "no detector score" in f.detail


def test_a_journal_doaj_does_not_list_is_noted_with_the_caveat(report):
    f = [x for x in report.findings if x.check == "journal" and x.source == "DOAJ"][0]
    assert f.tier == ic.NOTED
    assert "absence alone proves nothing" in f.detail


def test_image_checks_are_declared_not_done(report):
    assert any("figure panels" in x for x in report.not_checked)


def test_findings_come_worst_first(report):
    tiers = [f.tier for f in report.findings]
    assert tiers == sorted(tiers, key=ic.TIER_ORDER.index)


def test_html_highlights_the_snippet_on_its_line(report):
    page = ic.render_html(report, MANUSCRIPT)
    assert "<span id='L9'>" in page
    assert "<mark class='PROVEN'>GSE99999999</mark>" in page
    # The phrase wraps across lines 9 and 10, so the whole line it starts on is marked.
    assert "<mark class='NOTED'>is deposited under <mark class='PROVEN'>GSE99999999</mark>" in page
    assert "confidential" in page


def test_no_accession_and_no_statement_is_noted(tmp_path: Path):
    path = tmp_path / "note.md"
    path.write_text("A short note with no data at all.\n", encoding="utf-8")
    archives = ic.Archives(get_json=fake_get_json, get_text=fake_get_text, sleep=lambda s: None)
    r = ic.check_file(path, resolver=cc.Resolver(get_json=fake_get_json, sleep=lambda s: None), archives=archives)
    f = by(r, "availability", "no data statement")
    assert f.tier == ic.NOTED


def test_registry_row_matches_by_issn_and_by_title(tmp_path: Path):
    reg = tmp_path / "journals.md"
    reg.write_text(
        "# Journals\n\n| Journal | ISSN | Publisher | Indexed | Flags | Checked |\n|---|---|---|---|---|---|\n"
        "| [Example Letters](https://example.org) | 1234-5678 | Example Press | DOAJ, Scopus | | 2026-11-21 |\n",
        encoding="utf-8",
    )
    assert ic.registry_row(reg, issn="12345678")["publisher"] == "Example Press"
    assert ic.registry_row(reg, journal="example letters")["issn"] == "1234-5678"
    assert ic.registry_row(reg, journal="other") is None


def test_the_shipped_registry_parses(tmp_path: Path):
    reg = Path(__file__).resolve().parent.parent / "docs" / "journals.md"
    assert reg.exists()
    row = ic.registry_row(reg, issn="2046-1402")
    assert row and "f1000" in row["journal"].lower()


def test_cli_check_exits_one_on_a_proven_finding_and_report_writes_html(tmp_path: Path, monkeypatch):
    from murmurent.cli import cli

    path = tmp_path / "paper.md"
    path.write_text(MANUSCRIPT, encoding="utf-8")
    monkeypatch.setattr(cc, "http_get_json", fake_get_json)
    monkeypatch.setattr(ic, "http_get_text", fake_get_text)
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    monkeypatch.setattr(ic.time, "sleep", lambda s: None)
    monkeypatch.setattr(cc.Resolver.__init__, "__defaults__", (fake_get_json, lambda s: None, None))
    monkeypatch.setattr(ic.Archives.__init__, "__defaults__", (fake_get_json, fake_get_text, lambda s: None))
    runner = CliRunner()
    res = runner.invoke(cli, ["integrity", "check", str(path), "--json"])
    assert res.exit_code == 1, res.output
    data = json.loads(res.output)
    assert any(f["tier"] == "PROVEN" for f in data["findings"])
    findings = tmp_path / "findings.json"
    findings.write_text(res.output, encoding="utf-8")
    res = runner.invoke(cli, ["integrity", "report", str(findings), "--out", str(tmp_path / "paper.html")])
    assert res.exit_code == 0, res.output
    assert "<mark class='PROVEN'>" in (tmp_path / "paper.html").read_text(encoding="utf-8")
