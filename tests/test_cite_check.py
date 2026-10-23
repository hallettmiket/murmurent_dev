"""
Purpose: Pin ``murmurent cite check`` (issue #225) on planted cases: one real
         citation, the two wrong PMIDs from the bookworm's old worked example,
         a retracted paper, and an identifier that does not exist. The checker
         must catch the last three and pass the first. Registry answers are
         canned, copied from real responses on 2026-10-23, so nothing here
         touches the network.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-23
Input: ``tmp_path`` files and a fake ``get_json``.
Output: pytest cases.
"""

from __future__ import annotations

import json
from urllib.parse import unquote

import pytest
from click.testing import CliRunner

from murmurent.core import cite_check as cc

BASSET = {
    "title": [
        "A novel metalloproteinase gene specifically expressed in stromal "
        "cells of breast carcinomas"
    ],
    "author": [{"family": "Basset", "given": "P."}],
    "issued": {"date-parts": [[1990, 12]]},
}
WAKEFIELD = {
    "title": [
        "RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, "
        "and pervasive developmental disorder in children"
    ],
    "author": [{"family": "Wakefield", "given": "A.J."}],
    "issued": {"date-parts": [[1998, 2]]},
    "updated-by": [
        {"DOI": "10.1016/s0140-6736(10)60175-4", "type": "retraction", "source": "retraction-watch"}
    ],
}
CONCERNED = {
    "title": ["A paper with a concern"],
    "author": [{"family": "Doe"}],
    "issued": {"date-parts": [[2020]]},
    "updated-by": [{"type": "expression_of_concern"}],
}
PUBMED = {
    "1701851": {
        "uid": "1701851",
        "title": BASSET["title"][0] + ".",
        "authors": [{"name": "Basset P"}],
        "pubdate": "1990 Dec 20-27",
        "pubtype": ["Journal Article"],
    },
    "22178968": {
        "uid": "22178968",
        "title": "Cellular iron distribution in Bacillus anthracis.",
        "authors": [{"name": "Tu WY"}],
        "pubdate": "2012 Mar",
        "pubtype": ["Journal Article"],
    },
    "28710453": {
        "uid": "28710453",
        "title": "Intrinsic dynamics study identifies two amino acids of TIMP-1 "
        "critical for its LRP-1-mediated endocytosis in neurons.",
        "authors": [{"name": "Verzeaux L"}],
        "pubdate": "2017 Jul 14",
        "pubtype": ["Journal Article"],
    },
    "9500320": {
        "uid": "9500320",
        "title": WAKEFIELD["title"][0][len("RETRACTED: ") :] + ".",
        "authors": [{"name": "Wakefield AJ"}],
        "pubdate": "1998 Feb 28",
        "pubtype": ["Journal Article", "Retracted Publication"],
        "references": [{"reftype": "Retraction in", "pmid": 20137807}],
    },
}


class FakeRegistries:
    """Answers like Crossref, PubMed, DataCite and doi.org, and counts calls."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail or set()

    def __call__(self, url: str, params: dict) -> dict | None:
        url = unquote(url)
        self.calls.append(url)
        for host in self.fail:
            if host in url:
                raise cc.LookupFailed(f"could not reach {host}")
        if url == cc.ESUMMARY:
            ids = params["id"].split(",")
            result = {"uids": ids}
            for i in ids:
                result[i] = PUBMED.get(i, {"uid": i, "error": "cannot get document summary"})
            return {"result": result}
        if url.startswith(cc.CROSSREF):
            doi = url[len(cc.CROSSREF) :].lower()
            msg = {
                "10.1038/348699a0": BASSET,
                "10.1016/s0140-6736(97)11096-0": WAKEFIELD,
                "10.9999/concern": CONCERNED,
            }.get(doi)
            return {"message": msg} if msg else None
        if url.startswith(cc.DATACITE):
            if url.lower().endswith("10.48550/arxiv.1706.03762"):
                return {
                    "data": {
                        "attributes": {
                            "titles": [{"title": "Attention Is All You Need"}],
                            "creators": [{"familyName": "Vaswani"}],
                            "publicationYear": 2017,
                        }
                    }
                }
            return None
        if url.startswith(cc.HANDLE):
            return {"responseCode": 1} if "elsewhere" in url else None
        raise AssertionError(f"unexpected URL {url}")


def _resolver(**kw) -> tuple[cc.Resolver, FakeRegistries]:
    fake = FakeRegistries(**kw)
    return cc.Resolver(get_json=fake, sleep=lambda s: None, ncbi_api_key=""), fake


BIB = r"""
@article{basset1990,
  title = {A novel metalloproteinase gene specifically expressed in stromal cells
           of {breast} carcinomas},
  author = {Basset, P. and Bellocq, J. P.},
  doi = {https://doi.org/10.1038/348699a0}, pmid = {1701851}
}
@article{wrong_a, title = {MMP11 expression in breast-cancer stroma},
  author = {Smith, J.}, pmid = {22178968}}
@article{wrong_b, title = "Stromelysin-3 marks DCIS progression",
  author = "K. Jones", pmid = "28710453"}
@article{wakefield1998,
  title = {Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive
           developmental disorder in children},
  author = {Wakefield, A. J.}, doi = {10.1016/S0140-6736(97)11096-0}}
@article{invented, title = {Not a real paper}, author = {Nobody, A.}, doi = {10.1038/zz999}}
@string{nat = "Nature"}
"""


def _by_where(results):
    return {r.claim.where.split(": ")[-1] + ":" + r.claim.kind: r for r in results}


# ── the planted cases ───────────────────────────────────────────────────────


def test_planted_bib_catches_the_three_bad_and_passes_the_real_one(tmp_path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    resolver, _ = _resolver()
    got = _by_where(cc.check_file(bib, resolver))

    assert got["basset1990:doi"].status == cc.MATCH
    assert got["basset1990:pmid"].status == cc.MATCH
    assert got["wrong_a:pmid"].status == cc.MISMATCH
    assert "Bacillus anthracis" in got["wrong_a:pmid"].found_title
    assert got["wrong_b:pmid"].status == cc.MISMATCH
    assert got["wakefield1998:doi"].status == cc.RETRACTED
    assert got["invented:doi"].status == cc.NOT_FOUND


def test_results_come_worst_first(tmp_path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    statuses = [r.status for r in cc.check_file(bib, _resolver()[0])]
    assert statuses == sorted(statuses, key=cc.STATUS_ORDER.index)
    assert statuses[0] == cc.NOT_FOUND and statuses[-1] == cc.MATCH


def test_a_retracted_paper_is_caught_through_pubmed_too() -> None:
    claim = cc.Claim("pmid", "9500320", "x", claimed_title=PUBMED["9500320"]["title"])
    [result] = cc.check_claims([claim], _resolver()[0])
    assert result.status == cc.RETRACTED


def test_an_expression_of_concern_is_reported_but_does_not_fail() -> None:
    [result] = cc.check_claims([cc.Claim("doi", "10.9999/concern", "x")], _resolver()[0])
    assert result.status == cc.CONCERN
    assert cc.CONCERN not in cc.FAILING


# ── "not found" is not "fake" ───────────────────────────────────────────────


def test_an_unreachable_registry_is_unresolved_not_a_mismatch() -> None:
    claims = [
        cc.Claim("pmid", "1701851", "x", claimed_title="anything at all"),
        cc.Claim("doi", "10.1038/348699a0", "y", claimed_title="anything at all"),
    ]
    results = cc.check_claims(claims, _resolver(fail={"ncbi", "crossref"})[0])
    assert {r.status for r in results} == {cc.UNRESOLVED}
    assert all("could not reach" in r.detail for r in results)


def test_a_doi_registered_elsewhere_is_unresolved_with_the_reason() -> None:
    [result] = cc.check_claims([cc.Claim("doi", "10.5555/elsewhere", "x")], _resolver()[0])
    assert result.status == cc.UNRESOLVED
    assert "neither Crossref nor DataCite" in result.detail


def test_arxiv_goes_through_datacite_and_says_what_it_cannot_check() -> None:
    claim = cc.Claim("arxiv", "1706.03762", "x", claimed_title="Attention is all you need")
    [result] = cc.check_claims([claim], _resolver()[0])
    assert result.status == cc.MATCH
    assert "withdrawals are not checked" in result.detail


def test_a_different_first_author_alone_is_a_note_not_a_mismatch() -> None:
    claim = cc.Claim(
        "doi", "10.1038/348699a0", "x", claimed_title=BASSET["title"][0], claimed_author="Chambon"
    )
    [result] = cc.check_claims([claim], _resolver()[0])
    assert result.status == cc.MATCH
    assert "first author is Basset, not Chambon" in result.detail


# ── extraction ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("MMP11 (PMID 22178968, 28710453).", [("pmid", "22178968"), ("pmid", "28710453")]),
        ("PMIDs: 1701851 and 9500320", [("pmid", "1701851"), ("pmid", "9500320")]),
        ("https://pubmed.ncbi.nlm.nih.gov/1701851/", [("pmid", "1701851")]),
        ("(doi:10.1016/S0140-6736(97)11096-0).", [("doi", "10.1016/S0140-6736(97)11096-0")]),
        ("see https://doi.org/10.1038/348699a0.", [("doi", "10.1038/348699a0")]),
        ("arXiv:1706.03762v5", [("arxiv", "1706.03762")]),
        ("https://doi.org/10.48550/arXiv.1706.03762", [("arxiv", "1706.03762")]),
        ("38 per cent of labs, 2026", []),
    ],
)
def test_identifiers_are_found_in_text(text, expected) -> None:
    assert [(c.kind, c.ident) for c in cc.extract_from_text(text, "f")] == expected


def test_a_tex_file_checks_only_the_entries_it_cites(tmp_path) -> None:
    (tmp_path / "refs.bib").write_text(BIB, encoding="utf-8")
    tex = tmp_path / "main.tex"
    tex.write_text(
        "As shown~\\cite{basset1990, wrong_a}.\n"
        "% \\cite{invented} is commented out\n"
        "\\bibliography{refs}\n",
        encoding="utf-8",
    )
    keys = {c.where.split(": ")[1] for c in cc.extract_claims(tex)}
    assert keys == {"basset1990", "wrong_a"}


def test_markdown_shows_the_line_beside_the_real_title(tmp_path) -> None:
    md = tmp_path / "notes.md"
    md.write_text("MMP11 is a DCIS-stroma marker (PMID 22178968).\n", encoding="utf-8")
    results = cc.check_file(md, _resolver()[0])
    report = cc.format_report(results)
    assert results[0].status == cc.EXISTS
    assert "Bacillus anthracis" in report and "MMP11 is a DCIS-stroma marker" in report
    assert cc.RETRACTION_NOTE in report


def test_each_identifier_is_looked_up_once(tmp_path) -> None:
    md = tmp_path / "notes.md"
    md.write_text(
        "doi:10.1038/348699a0\nagain doi:10.1038/348699a0\n" "PMID 1701851 and PMID 22178968\n",
        encoding="utf-8",
    )
    resolver, fake = _resolver()
    assert len(cc.check_file(md, resolver)) == 4
    assert fake.calls.count(cc.ESUMMARY) == 1
    assert sum(u.startswith(cc.CROSSREF) for u in fake.calls) == 1


def test_titles_match_allows_markup_and_a_dropped_subtitle() -> None:
    assert cc.titles_match("The natural history of {DCIS}: a review", "The natural history of DCIS")
    assert cc.titles_match("Stromelysin-3 in <i>situ</i>", "Stromelysin 3 in situ")
    assert not cc.titles_match("MMP11 in breast stroma", "Cellular iron in Bacillus")
    assert not cc.titles_match("", "anything")


# ── the command ─────────────────────────────────────────────────────────────


def test_command_exits_1_on_a_failing_identifier(tmp_path, monkeypatch) -> None:
    from murmurent.cli import cli

    fake = FakeRegistries()
    monkeypatch.setattr(cc, "http_get_json", fake)
    monkeypatch.setattr(cc.Resolver.__init__, "__defaults__", (fake, lambda s: None, ""))
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    r = CliRunner().invoke(cli, ["cite", "check", str(bib), "--json"])
    assert r.exit_code == 1, r.output
    statuses = {x["status"] for x in json.loads(r.output)["results"]}
    assert {cc.MATCH, cc.MISMATCH, cc.RETRACTED, cc.NOT_FOUND} <= statuses

    good = tmp_path / "good.bib"
    good.write_text(BIB.split("@article{wrong_a")[0], encoding="utf-8")
    r = CliRunner().invoke(cli, ["cite", "check", str(good)])
    assert r.exit_code == 0, r.output
    assert "2 MATCH" in r.output
