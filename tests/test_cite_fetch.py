"""
Purpose: Pin ``murmurent cite fetch`` (core.cite_fetch) with canned registry and
         page answers: each route's reading, the five statuses, the ledger's
         shape, and the command's exit status.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-23
Input: synthetic notes files; no network.
Output: pytest cases.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cite_check, cite_fetch

OA = "10.1000/open"          # Unpaywall has a repository copy
PRE = "10.1000/preprinted"   # only a bioRxiv preprint
WALL = "10.1000/paywalled"   # publisher page, abstract only
BLOCK = "10.1000/blocked"    # Cloudflare challenge
GONE = "10.1000/missing"     # nobody has it
PMID_PMC = "11111111"        # PMID with a PMC copy
PMID_OLD = "1701851"         # real PMID the PMC converter does not know
PMID_NONE = "99999999"       # no such PMID


def canned_json(url: str, params: dict):
    if url.startswith(cite_fetch.UNPAYWALL):
        doi = url[len(cite_fetch.UNPAYWALL):]
        if doi == OA:
            return {"is_oa": True, "best_oa_location": {
                "url_for_pdf": "https://repo.example.edu/oa.pdf", "host_type": "repository",
                "version": "acceptedVersion"}}
        if doi == GONE:
            return None
        return {"is_oa": False, "best_oa_location": None}
    if url == cite_fetch.EUROPEPMC:
        q = params["query"]
        if OA in q or PRE in q or WALL in q or BLOCK in q:
            return {"resultList": {"result": [{"title": "A paper", "inEPMC": "N"}]}}
        if "EXT_ID:" + PMID_PMC in q:
            return {"resultList": {"result": [{"title": "A PMC paper", "pmcid": "PMC1", "inEPMC": "Y",
                                               "doi": WALL}]}}
        if "EXT_ID:" + PMID_OLD in q:
            return {"resultList": {"result": [{"title": "An old paper", "doi": WALL}]}}
        if "EXT_ID:" + PMID_NONE in q:
            return {"resultList": {"result": []}}
        return {"resultList": {"result": []}}
    if url.startswith(cite_fetch.BIORXIV_PUBS):
        if url.endswith(PRE) and "/biorxiv/" in url:
            return {"collection": [{"preprint_doi": "10.1101/2024.01.01.111111"}]}
        return {"collection": [], "messages": [{"status": "no posts found"}]}
    if url == cite_fetch.IDCONV:
        if params["ids"] == PMID_PMC:
            return {"records": [{"pmid": PMID_PMC, "pmcid": "PMC1", "doi": WALL}]}
        return {"records": [{"pmid": params["ids"], "status": "error", "errmsg": "invalid article id"}]}
    raise AssertionError(f"unexpected call {url} {params}")


def canned_page(url: str) -> cite_fetch.Page:
    doi = url[len(cite_fetch.DOI_ORG):]
    if doi == BLOCK:
        return cite_fetch.Page(403, "text/html", "https://pub.example.com/x",
                               "<title>Just a moment...</title>")
    if doi == GONE:
        return cite_fetch.Page(404, "text/html", "https://doi.org/" + doi, "DOI not found")
    return cite_fetch.Page(200, "text/html", "https://pub.example.com/article", "<h1>Abstract</h1>")


def fetcher(**kw) -> cite_fetch.Fetcher:
    return cite_fetch.Fetcher(get_json=canned_json, get_page=canned_page, sleep=lambda s: None,
                              unpaywall_email="tests@example.org", **kw)


def claim(kind: str, ident: str) -> cite_check.Claim:
    return cite_check.Claim(kind=kind, ident=ident, where="notes.md:1")


def test_open_copy_from_unpaywall() -> None:
    r = fetcher().fetch(claim("doi", OA))
    assert r.status == "OPEN COPY" and r.copy_kind == "repository"
    assert r.copy_url.endswith("oa.pdf")


def test_preprint_counts_as_open_copy() -> None:
    r = fetcher().fetch(claim("doi", PRE))
    assert r.status == "OPEN COPY" and r.copy_kind == "preprint"
    assert "10.1101/" in r.copy_url


def test_abstract_only_with_library_link() -> None:
    r = fetcher(library_resolver="https://lib.example.edu/resolve?doi={doi}").fetch(claim("doi", WALL))
    assert r.status == "ABSTRACT ONLY"
    assert r.library_url == "https://lib.example.edu/resolve?doi=10.1000%2Fpaywalled"
    assert r.next_step.startswith("the library's link first")
    names = [x.name for x in r.routes]
    assert names == ["Unpaywall", "Europe PMC", "bioRxiv/medRxiv", "publisher"]


def test_cloudflare_is_blocked_not_paywalled() -> None:
    r = fetcher().fetch(claim("doi", BLOCK))
    assert r.status == "BLOCKED"
    assert "browser" in r.next_step


def test_missing_doi_is_not_found() -> None:
    r = fetcher().fetch(claim("doi", GONE))
    assert r.status == "NOT FOUND"


def test_pmid_with_pmc_copy() -> None:
    r = fetcher().fetch(claim("pmid", PMID_PMC))
    assert r.status == "OPEN COPY" and r.copy_kind == "PubMed Central"
    assert "PMC1" in r.copy_url


def test_arxiv_is_always_open() -> None:
    r = fetcher().fetch(claim("arxiv", "2401.00001"))
    assert r.status == "OPEN COPY" and r.copy_url.endswith("2401.00001")


def test_without_email_unpaywall_is_not_asked() -> None:
    f = cite_fetch.Fetcher(get_json=canned_json, get_page=canned_page, sleep=lambda s: None,
                           unpaywall_email="", library_resolver="")
    r = f.fetch(claim("doi", OA))
    assert r.routes[0].answer.startswith("not asked")
    assert r.status == "ABSTRACT ONLY"


def test_classify_page_marks() -> None:
    assert cite_fetch.classify_page(cite_fetch.Page(200, "application/pdf", "u")) == "pdf"
    assert cite_fetch.classify_page(cite_fetch.Page(200, "text/html", "u", "Checking your browser")) == "blocked"
    assert cite_fetch.classify_page(cite_fetch.Page(0, error="could not reach")) == "error"


def test_ledger_lists_every_paper_and_every_route(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(f"doi:{OA}\ndoi:{WALL}\ndoi:{BLOCK}\ndoi:{OA}\n", encoding="utf-8")
    results = cite_fetch.fetch_file(notes, fetcher())
    assert len(results) == 3  # the duplicate is fetched once
    text = cite_fetch.format_ledger(results, source="notes.md")
    assert "## BLOCKED (1)" in text and "## ABSTRACT ONLY (1)" in text and "## OPEN COPY (1)" in text
    assert "- Unpaywall:" in text and "- publisher:" in text and "- next:" in text
    assert "sci-hub" not in text.lower() and "libgen" not in text.lower()


def test_cli_writes_ledger_and_exits_zero(tmp_path: Path, monkeypatch) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(f"doi:{WALL}\n", encoding="utf-8")
    monkeypatch.setattr(cite_fetch, "http_get_page", canned_page)
    monkeypatch.setattr(cite_check, "http_get_json", canned_json)
    monkeypatch.setattr(cite_fetch.Fetcher.__init__, "__defaults__",
                        (canned_json, canned_page, lambda s: None, None, None))
    out = tmp_path / "ledger.md"
    res = CliRunner().invoke(cli, ["cite", "fetch", str(notes), "--out", str(out), "--email", "t@example.org"])
    assert res.exit_code == 0, res.output
    assert "1 abstract only" in res.output and out.exists()
    assert "ABSTRACT ONLY" in out.read_text(encoding="utf-8")


def test_old_pmid_unknown_to_pmc_is_still_followed() -> None:
    r = fetcher().fetch(claim("pmid", PMID_OLD))
    assert r.status == "ABSTRACT ONLY"
    names = [x.name for x in r.routes]
    assert names == ["PubMed id converter", "Europe PMC", "Unpaywall", "bioRxiv/medRxiv", "publisher"]


def test_pmid_nobody_has_is_not_found() -> None:
    r = fetcher().fetch(claim("pmid", PMID_NONE))
    assert r.status == "NOT FOUND"
