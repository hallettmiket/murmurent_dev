"""
Purpose: For every DOI, PMID and arXiv ID in a file, find out whether the paper
         can be read in full and where, trying the legitimate routes in a fixed
         order, and write a reading ledger that says, paper by paper, what was
         reached, what was tried, where a copy is, and what a person can do next.
         The bookworm runs this instead of reporting "17 papers could not be
         opened" with nothing behind the number.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-23
Input: a ``.bib``, ``.tex``, ``.md`` or text file; identifiers are extracted the
       same way as ``murmurent cite check`` (``cite_check.extract_claims``).
Output: a list of :class:`FetchResult`; :func:`format_ledger` renders it as
        markdown or JSON. No model is involved: the same file gives the same
        ledger.

Routes, in order, each recorded whether it answers or not:

1. **Unpaywall** (needs a contact email, ``UNPAYWALL_EMAIL``): the best
   open-access location the publisher or an author posted, often the accepted
   manuscript in an institutional repository.
2. **Europe PMC**: full text when the paper is in PubMed Central or Europe PMC's
   open-access set.
3. **bioRxiv and medRxiv**: the preprint of a published paper, by the published
   DOI.
4. **The publisher's page** through doi.org: a PDF, a page (usually the
   abstract), or a bot-check page (Cloudflare and the like), which a person can
   open in a browser and click through.
5. **The library's link resolver**: a link, not a fetch, since the sign-in is
   the member's. The template (with ``{doi}``) comes from ``--resolver``, else
   ``MURMURENT_LIBRARY_RESOLVER``, else ``library.yaml`` in the institution
   pack, where the centre records it once for everyone.

Sites that distribute papers without the publishers' permission are not
routes and are not suggested.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from . import cite_check

USER_AGENT = "murmurent-cite-fetch (+https://github.com/hallettmiket/murmurent)"
UNPAYWALL = "https://api.unpaywall.org/v2/"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_ARTICLE = "https://europepmc.org/article/"
BIORXIV_PUBS = "https://api.biorxiv.org/pubs/"
IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
DOI_ORG = "https://doi.org/"
ARXIV_ABS = "https://arxiv.org/abs/"
REQUEST_SPACING = 0.34
LIBRARY_FILE = "library.yaml"   # in the institution pack: link_resolver.template with {doi}

#: Statuses. ``OPEN COPY``: a copy a person may read was found and its address
#: is in the row. ``BLOCKED``: the publisher's page is behind a bot check; a
#: person can open it. ``ABSTRACT ONLY``: the publisher's page was reached and
#: no open copy exists anywhere asked. ``NOT FOUND``: no registry knows the
#: identifier. ``UNRESOLVED``: a route could not be asked, so no verdict.
STATUSES = ("OPEN COPY", "BLOCKED", "ABSTRACT ONLY", "NOT FOUND", "UNRESOLVED")

_CHALLENGE_MARKS = (
    "just a moment",
    "cf-chl",
    "challenge-platform",
    "attention required",
    "checking your browser",
    "verify you are human",
    "access denied",
    "enable javascript and cookies",
)


@dataclass
class Route:
    """One thing tried for one paper, and what it said."""

    name: str
    answer: str
    url: str = ""
    copy: bool = False  # True when ``url`` is a copy a person may read


@dataclass
class Page:
    """What a GET of a publisher page came back as."""

    status: int
    content_type: str = ""
    final_url: str = ""
    text: str = ""  # the first few kilobytes, for the challenge check
    error: str = ""


@dataclass
class FetchResult:
    """The ledger row for one identifier."""

    claim: cite_check.Claim
    status: str
    title: str = ""
    routes: list[Route] = field(default_factory=list)
    copy_url: str = ""
    copy_kind: str = ""  # "repository" | "Europe PMC" | "preprint" | "publisher PDF" | "arXiv"
    library_url: str = ""
    next_step: str = ""

    def to_dict(self) -> dict:
        out = asdict(self)
        out.update(out.pop("claim"))
        return out


PageGetter = Callable[[str], Page]


def http_get_page(url: str) -> Page:
    """GET ``url`` with redirects and return enough to classify the answer."""
    import httpx

    try:
        r = httpx.get(url, timeout=25.0, follow_redirects=True,
                      headers={"User-Agent": USER_AGENT,
                               "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8"})
    except httpx.HTTPError as exc:
        return Page(status=0, error=f"could not reach {httpx.URL(url).host} ({type(exc).__name__})")
    ctype = r.headers.get("content-type", "")
    text = "" if ctype.startswith("application/pdf") else r.text[:8000]
    return Page(status=r.status_code, content_type=ctype, final_url=str(r.url), text=text)


def classify_page(page: Page) -> str:
    """``pdf`` | ``page`` | ``blocked`` | ``missing`` | ``error``."""
    if page.error:
        return "error"
    low = page.text.lower()
    if page.status in (403, 429, 503) or any(m in low for m in _CHALLENGE_MARKS):
        return "blocked"
    if page.status == 404:
        return "missing"
    if page.status >= 400:
        return "error"
    if page.content_type.startswith("application/pdf"):
        return "pdf"
    return "page"


class Fetcher:
    """Tries the routes for one identifier. Network calls are injectable."""

    def __init__(
        self,
        get_json: cite_check.JsonGetter = cite_check.http_get_json,
        get_page: PageGetter = http_get_page,
        sleep: Callable[[float], None] = time.sleep,
        unpaywall_email: str | None = None,
        library_resolver: str | None = None,
    ) -> None:
        self.get_json = get_json
        self.get_page = get_page
        self.sleep = sleep
        self.email = (unpaywall_email if unpaywall_email is not None
                      else os.environ.get("UNPAYWALL_EMAIL", ""))
        self.library = (library_resolver if library_resolver is not None
                        else os.environ.get("MURMURENT_LIBRARY_RESOLVER", ""))
        self._last: dict[str, float] = {}

    # -- plumbing -----------------------------------------------------------

    def _space(self, service: str) -> None:
        wait = self._last.get(service, 0.0) + REQUEST_SPACING - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last[service] = time.monotonic()

    def _json(self, service: str, url: str, params: dict | None = None):
        """One call, and one retry after a short wait when the service is slow or busy."""
        self._space(service)
        try:
            return self.get_json(url, params or {})
        except cite_check.LookupFailed as exc:
            if "404" in str(exc):
                raise
            self.sleep(2.0)
            self._space(service)
            return self.get_json(url, params or {})

    def _library_link(self, doi: str) -> str:
        return self.library.replace("{doi}", quote(doi, safe="")) if self.library and doi else ""

    # -- routes ---------------------------------------------------------------

    def _unpaywall(self, doi: str) -> Route:
        if not self.email:
            return Route("Unpaywall", "not asked: set UNPAYWALL_EMAIL (the service wants a contact address)")
        try:
            data = self._json("unpaywall", UNPAYWALL + quote(doi, safe="/"), {"email": self.email})
        except cite_check.LookupFailed as exc:
            return Route("Unpaywall", f"unreachable: {exc}")
        if data is None:
            return Route("Unpaywall", "no record of this DOI")
        loc = data.get("best_oa_location") or {}
        url = loc.get("url_for_pdf") or loc.get("url") or ""
        if data.get("is_oa") and url:
            what = f"{loc.get('version') or 'a copy'} at {loc.get('host_type') or 'a host'}"
            return Route("Unpaywall", f"open copy: {what}", url, copy=True)
        return Route("Unpaywall", "no open copy known")

    def _europepmc(self, doi: str = "", pmid: str = "") -> tuple[Route, str, str]:
        """The route, the title, and the DOI Europe PMC holds for the record."""
        query = f'DOI:"{doi}"' if doi else f"EXT_ID:{pmid} AND SRC:MED"
        try:
            data = self._json("europepmc", EUROPEPMC,
                              {"query": query, "format": "json", "resultType": "lite", "pageSize": 1})
        except cite_check.LookupFailed as exc:
            return Route("Europe PMC", f"unreachable: {exc}"), "", ""
        hits = ((data or {}).get("resultList") or {}).get("result") or []
        if not hits:
            return Route("Europe PMC", "no record"), "", ""
        hit = hits[0]
        title = hit.get("title") or ""
        found_doi = hit.get("doi") or ""
        pmcid = hit.get("pmcid") or ""
        in_epmc = hit.get("inEPMC") == "Y" or hit.get("isOpenAccess") == "Y"
        if pmcid and in_epmc:
            return Route("Europe PMC", f"full text in Europe PMC ({pmcid})",
                         f"{EUROPEPMC_ARTICLE}PMC/{pmcid}", copy=True), title, found_doi
        if pmcid:
            return Route("Europe PMC", f"record with {pmcid}, full text not open there"), title, found_doi
        return Route("Europe PMC", "abstract only"), title, found_doi

    def _preprint(self, doi: str) -> Route:
        for server in ("biorxiv", "medrxiv"):
            try:
                data = self._json("biorxiv", f"{BIORXIV_PUBS}{server}/{quote(doi, safe='/')}")
            except cite_check.LookupFailed as exc:
                return Route("bioRxiv/medRxiv", f"unreachable: {exc}")
            coll = (data or {}).get("collection") or []
            if coll and coll[0].get("preprint_doi"):
                pre = coll[0]["preprint_doi"]
                return Route("bioRxiv/medRxiv", f"preprint on {server}: {pre}", DOI_ORG + pre, copy=True)
        return Route("bioRxiv/medRxiv", "no preprint linked to this DOI")

    def _publisher(self, doi: str) -> Route:
        self._space("publisher")
        page = self.get_page(DOI_ORG + quote(doi, safe="/"))
        kind = classify_page(page)
        host = page.final_url.split("/")[2] if page.final_url.count("/") >= 2 else "the publisher"
        if kind == "pdf":
            return Route("publisher", f"PDF served by {host}", page.final_url, copy=True)
        if kind == "blocked":
            return Route("publisher", f"bot check or refusal at {host} (HTTP {page.status}); "
                                      "a person can open it in a browser",
                         page.final_url or DOI_ORG + doi)
        if kind == "page":
            return Route("publisher", f"page reached at {host}; read it for the abstract or a login wall",
                         page.final_url)
        if kind == "missing":
            return Route("publisher", "doi.org has no such DOI")
        return Route("publisher", page.error or f"HTTP {page.status}")

    # -- one identifier --------------------------------------------------------

    def fetch(self, claim: cite_check.Claim) -> FetchResult:
        if claim.kind == "arxiv":
            url = ARXIV_ABS + claim.ident
            return FetchResult(claim, "OPEN COPY", title=claim.claimed_title,
                               routes=[Route("arXiv", "arXiv papers are open", url, copy=True)],
                               copy_url=url, copy_kind="arXiv",
                               next_step="read it on arXiv; say which version")
        doi, pmid, title = "", "", claim.claimed_title
        routes: list[Route] = []
        if claim.kind == "pmid":
            pmid = claim.ident
            try:
                data = self._json("ncbi", IDCONV, {"ids": pmid, "format": "json"})
            except cite_check.LookupFailed as exc:
                routes.append(Route("PubMed id converter", f"unreachable: {exc}"))
                data = None
            recs = (data or {}).get("records") or []
            if recs and recs[0].get("status") != "error":
                doi = recs[0].get("doi") or ""
                pmcid = recs[0].get("pmcid") or ""
                routes.append(Route("PubMed id converter", f"DOI {doi or 'none'}, {pmcid or 'no PMCID'}"))
                if pmcid:
                    routes.append(Route("PubMed Central", f"full text ({pmcid})",
                                        f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/", copy=True))
            elif data is not None:
                routes.append(Route("PubMed id converter", "not in PubMed Central's converter "
                                                           "(it knows only papers PMC holds)"))
            r, t, d = self._europepmc(pmid=pmid)
            routes.append(r)
            title = title or t
            doi = doi or d
            if r.answer == "no record":
                routes.append(Route("PubMed", "Europe PMC mirrors PubMed and has no such PMID"))
        else:
            doi = claim.ident

        if doi:
            routes.append(self._unpaywall(doi))
            if claim.kind != "pmid":
                r, t, _d = self._europepmc(doi=doi)
                routes.append(r)
                title = title or t
            routes.append(self._preprint(doi))
            routes.append(self._publisher(doi))

        return self._verdict(claim, title, routes, doi)

    def _verdict(self, claim, title, routes, doi) -> FetchResult:
        res = FetchResult(claim, "UNRESOLVED", title=title, routes=routes,
                          library_url=self._library_link(doi))
        copies = [r for r in routes if r.copy]
        if copies:
            best = copies[0]
            res.status, res.copy_url = "OPEN COPY", best.url
            res.copy_kind = {"Unpaywall": "repository", "Europe PMC": "Europe PMC",
                             "PubMed Central": "PubMed Central", "bioRxiv/medRxiv": "preprint",
                             "publisher": "publisher PDF"}.get(best.name, best.name)
            res.next_step = "read the copy; check it is the same version before quoting a number"
            return res
        answers = {r.name: r.answer for r in routes}
        pub = answers.get("publisher", "")
        if pub.startswith("bot check"):
            res.status = "BLOCKED"
            res.next_step = "open the publisher link in a browser, pass the check, then read it there"
        elif (pub.startswith("doi.org has no such")
              or "no such PMID" in answers.get("PubMed", "")):
            res.status = "NOT FOUND"
            res.next_step = "the identifier is wrong; fix it before anything else"
        elif pub.startswith("page reached") or "abstract" in answers.get("Europe PMC", ""):
            res.status = "ABSTRACT ONLY"
            res.next_step = ("ask the library, else email the corresponding author "
                             "for the accepted manuscript")
        else:
            res.next_step = "a route could not be asked; run again, or try the library"
        if res.library_url and res.status in ("ABSTRACT ONLY", "BLOCKED"):
            res.next_step = "the library's link first; " + res.next_step
        return res


def pack_library_resolver(pack_root: str | Path | None) -> tuple[str, str]:
    """The link-resolver template recorded in the institution pack's
    ``library.yaml`` (``link_resolver: {template, name, source, date_read}``),
    and a short note saying where it came from. ``("", "")`` when the pack or
    the file is absent, the file is malformed, or the template lacks ``{doi}``:
    an absent setting is never guessed."""
    if pack_root is None:
        return "", ""
    path = Path(pack_root) / LIBRARY_FILE
    if not path.is_file():
        return "", ""
    try:
        import yaml
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  (a bad file means no resolver, not a crash)
        return "", ""
    block = doc.get("link_resolver") if isinstance(doc, dict) else None
    if not isinstance(block, dict):
        return "", ""
    template = str(block.get("template") or "").strip()
    if "{doi}" not in template:
        return "", ""
    name = str(block.get("name") or "the library's link resolver")
    return template, f"{name}, from the institution pack {Path(pack_root).name}"


def fetch_file(path: str | Path, fetcher: Fetcher | None = None) -> list[FetchResult]:
    """Every identifier in the file, once each, with its ledger row."""
    f = fetcher or Fetcher()
    seen: set[tuple[str, str]] = set()
    out: list[FetchResult] = []
    for claim in cite_check.extract_claims(Path(path)):
        key = (claim.kind, claim.ident)
        if key in seen:
            continue
        seen.add(key)
        out.append(f.fetch(claim))
    return out


def format_ledger(results: list[FetchResult], *, as_json: bool = False, source: str = "",
                  library_note: str = "") -> str:
    """The reading ledger: a summary, then one section per status, worst first.
    ``library_note`` says where the library link came from, so a reader knows
    whether one was in play."""
    if as_json:
        return json.dumps([r.to_dict() for r in results], indent=2)
    counts = {s: sum(1 for r in results if r.status == s) for s in STATUSES}
    lines = [f"# Reading ledger{': ' + source if source else ''}", "",
             f"Written {_dt.date.today().isoformat()} by `murmurent cite fetch`. "
             f"{len(results)} identifiers: "
             + ", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n) + ".",
             "", "A copy listed here is one someone was allowed to post. A blocked page is one a "
             "person can open in a browser. An abstract-only paper goes to the library or to its "
             "author.", ""]
    if library_note:
        lines += [f"Library link: {library_note}.", ""]
    for status in ("BLOCKED", "ABSTRACT ONLY", "NOT FOUND", "UNRESOLVED", "OPEN COPY"):
        rows = [r for r in results if r.status == status]
        if not rows:
            continue
        lines += [f"## {status} ({len(rows)})", ""]
        for r in rows:
            head = f"**{r.claim.kind.upper()} {r.claim.ident}**"
            if r.title:
                head += f": {r.title}"
            lines.append(f"- {head} ({r.claim.where})")
            for route in r.routes:
                link = f" <{route.url}>" if route.url else ""
                lines.append(f"  - {route.name}: {route.answer}{link}")
            if r.copy_url:
                lines.append(f"  - **copy** ({r.copy_kind}): <{r.copy_url}>")
            if r.library_url:
                lines.append(f"  - library: <{r.library_url}>")
            lines.append(f"  - next: {r.next_step}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_SLUG = re.compile(r"[^a-z0-9]+")


def default_ledger_path(source: str | Path, outdir: str | Path = "outputs/bookworm") -> Path:
    stem = _SLUG.sub("_", Path(source).stem.lower()).strip("_") or "papers"
    return Path(outdir) / f"reading_ledger_{stem}_{_dt.date.today().isoformat()}.md"
