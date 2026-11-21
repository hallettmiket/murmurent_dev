"""
Purpose: The deterministic half of the detective (issue #341): the checks on a
         manuscript that need no judgement and whose answer is the same every
         time. Every citation is looked up through ``murmurent cite check``;
         every data accession (GEO, SRA, BioProject, ENA, EGA, PRIDE,
         ArrayExpress, dbGaP) is resolved at its archive and its public status
         read; the data-availability wording is read for deferrals ("on
         request", "will be deposited"); leftover text from a language model
         is looked for; the journal is looked up in DOAJ and in the journal
         registry. No AI is involved.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: A ``.tex``, ``.md``, ``.txt`` or ``.bib`` file, or a PDF (read through
       ``pdftotext`` when it is installed); optionally the journal's name or
       ISSN. Lookups go to Crossref, PubMed, DataCite, NCBI E-utilities, GEO,
       the EGA metadata service, PRIDE, BioStudies and DOAJ. The manuscript's
       own sentences never leave the machine: only identifiers and the journal
       name are sent.
Output: One :class:`Finding` per thing checked, in four tiers, worst first:
        ``PROVEN`` (the registry's answer is the proof, quoted), ``SUSPECTED``
        (the facts point at a problem but do not settle it; what would settle
        it is named), ``NOTED`` (a fact with no verdict, such as a leftover
        phrase or a deferral), ``CLEAN`` (checked, nothing found). Each
        finding carries the line it anchors to, so :func:`render_html` can
        highlight it in the manuscript's own text, and :func:`annotate_pdf`
        can write it into the PDF when PyMuPDF is installed.

What it cannot tell you: whether a figure panel is duplicated or spliced
(that needs an image tool; the detective names them), whether a sentence is
true (the adversary), or who meant what (nobody).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import cite_check

# ── tiers, worst first ──────────────────────────────────────────────────────
PROVEN = "PROVEN"
SUSPECTED = "SUSPECTED"
NOTED = "NOTED"
CLEAN = "CLEAN"
TIER_ORDER = (PROVEN, SUSPECTED, NOTED, CLEAN)

#: Tiers that make ``murmurent integrity check`` exit non-zero.
FAILING = frozenset({PROVEN})

USER_AGENT = "murmurent-integrity-check (+https://github.com/hallettmiket/murmurent)"
REQUEST_SPACING = 0.34

# ── services ────────────────────────────────────────────────────────────────
GEO = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EGA = "https://metadata.ega-archive.org/"
PRIDE = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects/"
BIOSTUDIES = "https://www.ebi.ac.uk/biostudies/api/v1/studies/"
DOAJ = "https://doaj.org/api/search/journals/"
PUBPEER = "https://pubpeer.com/search?q="

# ── accession patterns ──────────────────────────────────────────────────────
# (kind, archive name, pattern, controlled access by design)
ACCESSIONS: list[tuple[str, str, re.Pattern, bool]] = [
    ("geo", "GEO", re.compile(r"\b(G(?:SE|SM|DS|PL)\d{3,8})\b"), False),
    ("bioproject", "BioProject", re.compile(r"\b(PRJ(?:NA|EB|DB)\d{3,9})\b"), False),
    ("sra", "SRA", re.compile(r"\b([SED]R[PRXSAZ]\d{5,9})\b"), False),
    ("ega", "EGA", re.compile(r"\b(EGA[SDCFN]\d{11})\b"), True),
    ("pride", "PRIDE", re.compile(r"\b(PXD\d{6})\b"), False),
    ("biostudies", "ArrayExpress / BioStudies", re.compile(r"\b(E-[A-Z]{4}-\d{2,6})\b"), False),
    ("dbgap", "dbGaP", re.compile(r"\b(phs\d{6})(?:\.v\d+(?:\.p\d+)?)?\b"), True),
]

#: Wording that defers rather than provides the data. Each is a fact to note,
#: not a violation: many journals allow some of these and forbid others.
DEFERRALS: list[tuple[str, re.Pattern]] = [
    ("data available on request", re.compile(r"\b(?:available|provided|obtained)\s+(?:from\s+the\s+\w+\s+authors?\s+)?(?:up)?on\s+(?:reasonable\s+)?request\b", re.I)),
    ("deposit promised, not done", re.compile(r"\bwill\s+be\s+(?:deposited|made\s+(?:publicly\s+)?available|released|uploaded|shared)\b", re.I)),
    ("deposit promised, not done", re.compile(r"\b(?:upon|on|after)\s+(?:acceptance|publication)\b.{0,60}\b(?:deposit|availab|release)", re.I)),
    ("data said to be unavailable", re.compile(r"\b(?:data|code)\s+(?:are|is)\s+not\s+(?:publicly\s+)?available\b", re.I)),
    ("accession pending", re.compile(r"\baccession\s+(?:number|code|id)s?\s+(?:is|are|will\s+be)\s+(?:pending|forthcoming|to\s+be\s+(?:assigned|provided))\b", re.I)),
    ("accession placeholder", re.compile(r"\b(?:GSE|PRJNA|PXD|EGAS)\s*X{3,}\b|\[(?:accession|GEO|ACCESSION)[^\]]*\]", re.I)),
]

#: Phrases a language model writes to a person and a person does not leave in
#: a manuscript. Their presence is a fact worth noting; it is not a verdict on
#: the paper, and nothing here scores "how AI" the prose sounds.
AI_RESIDUE: list[re.Pattern] = [
    re.compile(r"\bas an AI (?:language )?model\b", re.I),
    re.compile(r"\bas a large language model\b", re.I),
    re.compile(r"\bregenerate response\b", re.I),
    re.compile(r"\bas of my (?:last |latest )?(?:knowledge|training) (?:cutoff|update)\b", re.I),
    re.compile(r"\bI hope this helps\b", re.I),
    re.compile(r"\bCertainly[!,] (?:here|below) (?:is|are)\b", re.I),
    re.compile(r"\bI (?:cannot|can't|am unable to) (?:browse|access) the internet\b", re.I),
    re.compile(r"\bI don't have access to real-time\b", re.I),
    re.compile(r"\b(?:here is|here's) (?:a|an|the) (?:revised|rewritten|improved|polished) (?:version|draft|paragraph|abstract)\b", re.I),
]

#: Lines of a LaTeX source that are not prose.
_TEX_COMMENT = re.compile(r"(?<!\\)%.*$")


# ── results ─────────────────────────────────────────────────────────────────


@dataclass
class Finding:
    """One thing checked, and what the check showed."""

    tier: str
    check: str  # "citation" | "data" | "availability" | "ai_residue" | "journal"
    ident: str  # the identifier, phrase or journal
    where: str  # "paper.tex:120" or "refs.bib: smith2020"
    line: int  # 0 when the finding has no line in the source
    snippet: str  # the exact text in the source the finding anchors to
    detail: str  # what the registry said, quoted, or what would settle it
    source: str = ""  # which service answered
    link: str = ""  # where a person can look

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    path: str
    findings: list[Finding]
    not_checked: list[str] = field(default_factory=list)
    journal: str = ""
    checked_on: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "journal": self.journal,
            "checked_on": self.checked_on,
            "findings": [f.to_dict() for f in self.findings],
            "not_checked": list(self.not_checked),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Report":
        return cls(
            path=d.get("path", ""),
            findings=[Finding(**f) for f in d.get("findings", [])],
            not_checked=list(d.get("not_checked", [])),
            journal=d.get("journal", ""),
            checked_on=d.get("checked_on", ""),
        )


# ── reading the source ──────────────────────────────────────────────────────


def read_source(path: Path) -> tuple[str, list[str]]:
    """The manuscript's text and the list of what could not be read from it.

    A PDF goes through ``pdftotext`` when it is installed; a page break becomes
    a form feed, which :func:`line_of` keeps as a line so numbers stay stable.
    """
    not_checked: list[str] = []
    if path.suffix.lower() == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe:
            not_checked.append("the PDF: pdftotext is not installed, so nothing in it was read")
            return "", not_checked
        out = subprocess.run([exe, "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True)
        if out.returncode != 0:
            not_checked.append(f"the PDF: pdftotext failed ({out.stderr.strip()[:120]})")
            return "", not_checked
        return out.stdout, not_checked
    return path.read_text(encoding="utf-8", errors="replace"), not_checked


def prose_lines(text: str, path: Path) -> list[tuple[int, str]]:
    """(line number, text) for every line, with LaTeX comments blanked."""
    tex = path.suffix.lower() == ".tex"
    out = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = _TEX_COMMENT.sub("", raw) if tex else raw
        out.append((i, line))
    return out


# ── the checks ──────────────────────────────────────────────────────────────

JsonGetter = Callable[[str, dict], "dict | None"]
TextGetter = Callable[[str, dict], "str | None"]


def http_get_text(url: str, params: dict) -> str | None:
    """GET ``url`` as text; ``None`` on 404, :class:`cite_check.LookupFailed` otherwise."""
    import httpx

    try:
        r = httpx.get(url, params=params, timeout=20.0, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        raise cite_check.LookupFailed(f"could not reach {httpx.URL(url).host} ({type(exc).__name__})") from exc
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise cite_check.LookupFailed(f"{httpx.URL(url).host} answered HTTP {r.status_code}")
    return r.text


class Archives:
    """Resolves data accessions and journals. Both getters are injectable for tests."""

    def __init__(
        self,
        get_json: JsonGetter = cite_check.http_get_json,
        get_text: TextGetter = http_get_text,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.get_json = get_json
        self.get_text = get_text
        self.sleep = sleep
        self._last: dict[str, float] = {}

    def _space(self, service: str) -> None:
        wait = self._last.get(service, 0.0) + REQUEST_SPACING - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self._last[service] = time.monotonic()

    def geo(self, acc: str) -> tuple[str, str, str]:
        """(tier, detail, link) for a GEO accession, read off GEO's own text record."""
        link = f"{GEO}?acc={acc}"
        self._space("ncbi")
        text = self.get_text(GEO, {"acc": acc, "targ": "self", "form": "text", "view": "brief"}) or ""
        if not text.strip() or "Could not find" in text or "is not a valid" in text:
            return PROVEN, f"GEO has no record of {acc}: its own page answers that the accession could not be found", link
        m = re.search(r"!\w+_status\s*=\s*(.+)", text)
        status = (m.group(1).strip() if m else "").strip()
        if status.lower().startswith("public"):
            return CLEAN, f"GEO lists {acc} as \"{status}\"", link
        if status:
            return SUSPECTED, f"GEO holds {acc} but its status is \"{status}\", not public; a reader cannot get the data today. Settled by: the archive making it public, or the journal's embargo rule", link
        return SUSPECTED, f"GEO answered for {acc} but gave no status line; open the page", link

    def ncbi_count(self, db: str, term: str) -> int | None:
        self._space("ncbi")
        data = self.get_json(ESEARCH, {"db": db, "term": term, "retmode": "json"}) or {}
        try:
            return int(data["esearchresult"]["count"])
        except (KeyError, TypeError, ValueError):
            raise cite_check.LookupFailed("NCBI sent an answer that could not be read")

    def ncbi(self, db: str, acc: str, archive: str, link: str) -> tuple[str, str, str]:
        n = self.ncbi_count(db, f"{acc}[Accession]" if db != "gap" else acc)
        if n == 0:
            return PROVEN, f"NCBI's {archive} search returns no record for {acc}", link
        return CLEAN, f"NCBI's {archive} search lists {acc} ({n} record{'s' if n != 1 else ''})", link

    def ega(self, acc: str) -> tuple[str, str, str]:
        kind = {"S": "studies", "D": "datasets", "C": "dacs", "F": "files", "N": "samples"}.get(acc[3], "studies")
        link = f"https://ega-archive.org/{kind}/{acc}"
        self._space("ega")
        data = self.get_json(EGA + f"{kind}/{acc}", {})
        if data is None:
            return PROVEN, f"the EGA metadata service has no record of {acc}", link
        return CLEAN, f"EGA lists {acc}; access is through its data access committee by design, which is not a deferral", link

    def pride(self, acc: str) -> tuple[str, str, str]:
        link = f"https://www.ebi.ac.uk/pride/archive/projects/{acc}"
        self._space("ebi")
        data = self.get_json(PRIDE + acc, {})
        if data is None:
            return PROVEN, f"PRIDE has no record of {acc}", link
        status = str(data.get("publicationDate") or data.get("submissionDate") or "")
        return CLEAN, f"PRIDE lists {acc}" + (f" (public since {status[:10]})" if status else ""), link

    def biostudies(self, acc: str) -> tuple[str, str, str]:
        link = f"https://www.ebi.ac.uk/biostudies/studies/{acc}"
        self._space("ebi")
        data = self.get_json(BIOSTUDIES + acc, {})
        if data is None:
            return PROVEN, f"BioStudies (which holds ArrayExpress) has no record of {acc}", link
        return CLEAN, f"BioStudies lists {acc}", link

    def doaj(self, *, issn: str = "", title: str = "") -> tuple[bool, str]:
        """(listed, what DOAJ said) for a journal, by ISSN when given."""
        q = f"issn:{issn}" if issn else "title:" + json.dumps(title)
        self._space("doaj")
        data = self.get_json(DOAJ + q, {"pageSize": 3}) or {}
        hits = data.get("results") or []
        if not hits:
            return False, f"DOAJ has no journal matching {q}"
        bib = (hits[0].get("bibjson") or {})
        name = bib.get("title", "")
        pub = (bib.get("publisher") or {}).get("name", "")
        return True, f"DOAJ lists \"{name}\"" + (f", published by {pub}" if pub else "")


def _finding_for_citation(r: cite_check.CheckResult, lines: dict[str, int]) -> Finding:
    c = r.claim
    line = lines.get(c.where, 0)
    base = dict(check="citation", ident=f"{c.kind.upper()} {c.ident}", where=c.where, line=line,
                snippet=c.ident, source=r.found_title and "registry" or "", link=_cite_link(c))
    actual = f" The registry's record is \"{r.found_title}\"" + (f" ({r.found_author}, {r.found_year})" if r.found_author or r.found_year else "") + "." if r.found_title else ""
    if r.status == cite_check.NOT_FOUND:
        return Finding(PROVEN, detail=f"{r.detail}. A reader cannot reach a paper that no registry has issued this identifier to.", **base)
    if r.status == cite_check.MISMATCH:
        return Finding(PROVEN, detail=f"{r.detail}.{actual} The bibliography claims \"{c.claimed_title}\".", **base)
    if r.status == cite_check.RETRACTED:
        return Finding(PROVEN, detail=f"{r.detail}.{actual} Citing a retracted paper is a fact to report, not in itself a violation: the text must say it is retracted and why it is cited.", **base)
    if r.status == cite_check.CONCERN:
        return Finding(SUSPECTED, detail=f"{r.detail}.{actual} Settled by: reading the expression of concern and whether the cited claim is the one it concerns.", **base)
    if r.status == cite_check.UNRESOLVED:
        return Finding(NOTED, detail=f"Could not be checked: {r.detail}.", **base)
    return Finding(CLEAN, detail=f"{r.status}: {r.detail}.{actual}", **base)


def _cite_link(c: cite_check.Claim) -> str:
    if c.kind == "doi":
        return f"https://doi.org/{c.ident}"
    if c.kind == "pmid":
        return f"https://pubmed.ncbi.nlm.nih.gov/{c.ident}/"
    return f"https://arxiv.org/abs/{c.ident}"


def check_citations(path: Path, resolver: cite_check.Resolver | None, lines_by_where: dict[str, int]) -> list[Finding]:
    results = cite_check.check_file(path, resolver)
    return [_finding_for_citation(r, lines_by_where) for r in results]


def find_accessions(lines: list[tuple[int, str]]) -> list[tuple[str, str, str, bool, int, str]]:
    """(kind, archive, accession, controlled, line, matched text), first mention of each."""
    seen: set[str] = set()
    out = []
    for n, line in lines:
        for kind, archive, pat, controlled in ACCESSIONS:
            for m in pat.finditer(line):
                acc = m.group(1)
                if acc in seen:
                    continue
                seen.add(acc)
                out.append((kind, archive, acc, controlled, n, m.group(0)))
    return out


def check_data(lines: list[tuple[int, str]], archives: Archives, where: str) -> list[Finding]:
    out = []
    for kind, archive, acc, controlled, n, text in find_accessions(lines):
        try:
            if kind == "geo":
                tier, detail, link = archives.geo(acc)
            elif kind == "bioproject":
                tier, detail, link = archives.ncbi("bioproject", acc, archive, f"https://www.ncbi.nlm.nih.gov/bioproject/{acc}")
            elif kind == "sra":
                tier, detail, link = archives.ncbi("sra", acc, archive, f"https://www.ncbi.nlm.nih.gov/sra/{acc}")
            elif kind == "dbgap":
                tier, detail, link = archives.ncbi("gap", acc, archive, f"https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={acc}")
                if tier == CLEAN:
                    detail += "; access is controlled by design, through its data access committee"
            elif kind == "ega":
                tier, detail, link = archives.ega(acc)
            elif kind == "pride":
                tier, detail, link = archives.pride(acc)
            else:
                tier, detail, link = archives.biostudies(acc)
            source = archive
        except cite_check.LookupFailed as exc:
            tier, detail, link, source = NOTED, f"Could not be checked: {exc}.", "", ""
        out.append(Finding(tier, "data", acc, f"{where}:{n}", n, text, detail, source=source, link=link))
    return out


def _flat(lines: list[tuple[int, str]]) -> tuple[str, list[tuple[int, int]]]:
    """The lines joined by spaces, and (start offset, line number) for each, so a
    phrase that wraps across a line break is still found and anchored to the
    line it starts on."""
    parts, starts, pos = [], [], 0
    for n, line in lines:
        starts.append((pos, n))
        parts.append(line)
        pos += len(line) + 1
    return " ".join(parts), starts


def _line_at(starts: list[tuple[int, int]], pos: int) -> int:
    n = 0
    for start, line in starts:
        if start > pos:
            break
        n = line
    return n


def _phrases(lines: list[tuple[int, str]], patterns: list[tuple[str, re.Pattern]], check: str, where: str, detail: str) -> list[Finding]:
    text, starts = _flat(lines)
    out, taken = [], set()
    for label, pat in patterns:
        for m in pat.finditer(text):
            n = _line_at(starts, m.start())
            if n in taken:
                continue
            taken.add(n)
            out.append(Finding(NOTED, check, label or m.group(0), f"{where}:{n}", n, m.group(0), detail))
    return sorted(out, key=lambda f: f.line)


def check_availability(lines: list[tuple[int, str]], where: str, has_accessions: bool) -> list[Finding]:
    out = _phrases(lines, DEFERRALS, "availability", where,
                   "The wording defers the data rather than providing it. Whether that is allowed is the journal's policy, read from the journal's own page; the detective reports which.")
    if not out and not has_accessions:
        out.append(Finding(NOTED, "availability", "no data statement found", where, 0, "",
                           "No data accession and no availability wording was found in the text. Either the work has no data to share, or the statement is missing: the journal's policy says which is required."))
    return out


def check_ai_residue(lines: list[tuple[int, str]], where: str) -> list[Finding]:
    return _phrases(lines, [("", p) for p in AI_RESIDUE], "ai_residue", where,
                    "A phrase a language model writes to its user, left in the text. It says the passage was generated and not read back; it says nothing about the paper's honesty, and no detector score is used here.")


def check_journal(archives: Archives, registry: Path | None, *, journal: str = "", issn: str = "") -> list[Finding]:
    """What DOAJ and the journal registry say about the journal. Facts, not the word predatory."""
    if not journal and not issn:
        return []
    ident = issn or journal
    out = []
    try:
        listed, said = archives.doaj(issn=issn, title=journal)
        tier = CLEAN if listed else NOTED
        extra = "" if listed else " DOAJ lists open-access journals that meet its criteria; a subscription journal is not expected there, so absence alone proves nothing."
        out.append(Finding(tier, "journal", ident, "journal", 0, "", said + "." + extra, source="DOAJ",
                           link=f"https://doaj.org/search/journals?source=%7B%22query%22%3A%7B%22query_string%22%3A%7B%22query%22%3A%22{issn or journal}%22%7D%7D%7D"))
    except cite_check.LookupFailed as exc:
        out.append(Finding(NOTED, "journal", ident, "journal", 0, "", f"DOAJ could not be checked: {exc}.", source="DOAJ"))
    row = registry_row(registry, journal=journal, issn=issn) if registry else None
    if row:
        out.append(Finding(NOTED if row.get("flags", "").strip("-— ") else CLEAN, "journal", ident, "registry", 0, "",
                           "The journal registry's row: " + "; ".join(f"{k}: {v}" for k, v in row.items() if v and k != "journal"),
                           source="docs/journals.md"))
    elif registry:
        out.append(Finding(NOTED, "journal", ident, "registry", 0, "",
                           "Not in the journal registry (docs/journals.md). The detective reads the journal's own pages and may propose a row to the bookworm.", source="docs/journals.md"))
    return out


def registry_row(registry: Path, *, journal: str = "", issn: str = "") -> dict[str, str] | None:
    """The first table row of the journal registry whose ISSN or title matches."""
    if not registry.exists():
        return None
    header: list[str] = []
    want_issn = issn.replace("-", "").lower()
    want_title = cite_check.normalise(journal) if journal else ""
    for line in registry.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            header = []
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not header:
            header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        row_issn = row.get("issn", "").replace("-", "").lower()
        row_title = cite_check.normalise(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", row.get("journal", "")))
        if (want_issn and want_issn in row_issn) or (want_title and want_title == row_title):
            return row
    return None


# ── the whole check ─────────────────────────────────────────────────────────


def check_file(
    path: str | Path,
    *,
    journal: str = "",
    issn: str = "",
    resolver: cite_check.Resolver | None = None,
    archives: Archives | None = None,
    registry: Path | None = None,
    today: str = "",
) -> Report:
    """Run every deterministic check on the file at ``path``."""
    path = Path(path)
    archives = archives or Archives()
    text, not_checked = read_source(path)
    lines = prose_lines(text, path)
    where = path.name
    findings: list[Finding] = []

    # Citations: on the source itself, so .tex follows its .bib files; on the
    # extracted text for a PDF.
    cite_path = path
    tmp: Path | None = None
    if path.suffix.lower() == ".pdf" and text:
        tmp = path.with_suffix(".integrity.txt")
        tmp.write_text(text, encoding="utf-8")
        cite_path = tmp
    try:
        claims = cite_check.extract_claims(cite_path)
        lines_by_where = {c.where: int(c.where.rsplit(":", 1)[1]) for c in claims if re.search(r":\d+$", c.where)}
        if tmp is not None:
            lines_by_where = {k.replace(tmp.name, where): v for k, v in lines_by_where.items()}
        results = cite_check.check_claims(claims, resolver)
        for r in results:
            f = _finding_for_citation(r, lines_by_where)
            if tmp is not None:
                f.where = f.where.replace(tmp.name, where)
            findings.append(f)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()

    data = check_data(lines, archives, where)
    findings += data
    findings += check_availability(lines, where, bool(data))
    findings += check_ai_residue(lines, where)
    findings += check_journal(archives, registry, journal=journal, issn=issn)
    if not journal and not issn:
        not_checked.append("the journal: none was named (give --journal or --issn)")
    not_checked.append("figure panels for duplication or splicing: needs an image tool (the detective names them)")
    not_checked.append("whether any cited paper supports the sentence that cites it: a reader's job (the detective, then the adversary)")
    findings.sort(key=lambda f: (TIER_ORDER.index(f.tier), f.line or 10**9))
    return Report(str(path), findings, not_checked, journal=journal or issn,
                  checked_on=today or time.strftime("%Y-%m-%d"))


# ── reporting ───────────────────────────────────────────────────────────────


def format_report(report: Report, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), indent=2)
    counts = {t: sum(f.tier == t for f in report.findings) for t in TIER_ORDER}
    lines = [", ".join(f"{n} {t}" for t, n in counts.items() if n) or "nothing to check", ""]
    for f in report.findings:
        lines.append(f"{f.tier:<10} {f.check:<13} {f.ident}  ({f.where})")
        lines.append(f"           {f.detail}")
        if f.link:
            lines.append(f"           {f.link}")
    if report.not_checked:
        lines += ["", "Not checked:"] + [f"  - {x}" for x in report.not_checked]
    return "\n".join(lines)


_CSS = """
body{margin:0;font-family:system-ui,sans-serif;background:Canvas;color:CanvasText;color-scheme:light dark}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2em}
table{border-collapse:collapse;width:100%;font-size:.92rem}td,th{border-bottom:1px solid color-mix(in srgb,CanvasText 20%,transparent);padding:6px 8px;text-align:left;vertical-align:top}
.tier{font-weight:700;white-space:nowrap}
.PROVEN{color:#b3261e}.SUSPECTED{color:#c77700}.NOTED{color:#1565c0}.CLEAN{color:#2e7d32}
pre.src{font-family:ui-monospace,monospace;font-size:.82rem;line-height:1.5;white-space:pre-wrap;word-break:break-word;border:1px solid color-mix(in srgb,CanvasText 20%,transparent);padding:12px;border-radius:8px}
pre.src .n{display:inline-block;width:4ch;text-align:right;margin-right:1ch;opacity:.5;user-select:none}
mark{padding:0 2px;border-radius:3px;color:inherit}
mark.PROVEN{background:#f8c6c2}mark.SUSPECTED{background:#ffe0a3}mark.NOTED{background:#cfe0f7}mark.CLEAN{background:#cfe9d2}
@media(prefers-color-scheme:dark){mark.PROVEN{background:#7a1c16}mark.SUSPECTED{background:#7a4a00}mark.NOTED{background:#0d3a73}mark.CLEAN{background:#1b4d22}}
.note{display:block;font-family:system-ui,sans-serif;font-size:.8rem;margin:2px 0 6px 5ch;padding:4px 8px;border-left:3px solid currentColor;opacity:.95}
.warn{border:1px solid #c77700;border-radius:8px;padding:10px 14px;margin:12px 0}
"""


def render_html(report: Report, source_text: str, *, title: str = "") -> str:
    """The manuscript's text with every finding highlighted where it sits, and the findings table above it."""
    by_line: dict[int, list[Finding]] = {}
    for f in report.findings:
        if f.line:
            by_line.setdefault(f.line, []).append(f)
    rows = []
    for f in report.findings:
        anchor = f"#L{f.line}" if f.line else ""
        rows.append(
            f"<tr><td class='tier {f.tier}'>{f.tier}</td><td>{html.escape(f.check)}</td>"
            f"<td>{'<a href=' + chr(34) + anchor + chr(34) + '>' if anchor else ''}{html.escape(f.ident)}{'</a>' if anchor else ''}<br><small>{html.escape(f.where)}</small></td>"
            f"<td>{html.escape(f.detail)}{' <a href=' + chr(34) + html.escape(f.link) + chr(34) + '>look</a>' if f.link else ''}</td></tr>"
        )
    src = []
    for n, raw in enumerate(source_text.splitlines(), start=1):
        line = html.escape(raw)
        fs = by_line.get(n, [])
        for f in fs:
            if f.snippet:
                esc = html.escape(f.snippet)
                if esc in line:
                    line = line.replace(esc, f"<mark class='{f.tier}'>{esc}</mark>", 1)
                    continue
            line = f"<mark class='{f.tier}'>{line}</mark>"
        src.append(f"<span id='L{n}'><span class='n'>{n}</span>{line}</span>")
        for f in fs:
            src.append(f"<span class='note {f.tier}'><b>{f.tier}</b> {html.escape(f.ident)}: {html.escape(f.detail)}</span>")
    counts = {t: sum(f.tier == t for f in report.findings) for t in TIER_ORDER}
    summary = ", ".join(f"{n} {t.lower()}" for t, n in counts.items() if n) or "nothing to check"
    not_checked = "".join(f"<li>{html.escape(x)}</li>" for x in report.not_checked)
    title = title or f"Integrity check: {Path(report.path).name}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{_CSS}</style></head>
<body><main>
<h1>{html.escape(title)}</h1>
<p>{html.escape(summary)}. Checked on {html.escape(report.checked_on)}{', journal ' + html.escape(report.journal) if report.journal else ''}.
Four tiers: <b class="PROVEN">PROVEN</b> (the registry's answer is the proof, quoted), <b class="SUSPECTED">SUSPECTED</b> (what would settle it is named),
<b class="NOTED">NOTED</b> (a fact, no verdict), <b class="CLEAN">CLEAN</b> (checked, nothing found).
Nothing here is a finding about a person: a wrong identifier is a wrong identifier.</p>
<div class="warn">A manuscript under review is confidential. This page was made on this machine from the file named; only identifiers and the journal name were sent to the registries. Do not send this page outside the review.</div>
<h2>Findings</h2>
<table><tr><th>Tier</th><th>Check</th><th>What</th><th>What the check showed</th></tr>{''.join(rows)}</table>
<h2>Not checked</h2><ul>{not_checked}</ul>
<h2>The text, marked</h2>
<pre class="src">{chr(10).join(src)}</pre>
</main></body></html>
"""


def annotate_pdf(report: Report, pdf_in: Path, pdf_out: Path) -> int:
    """Write each finding into the PDF as a highlight with a note. Needs PyMuPDF; returns the count written."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is not installed (pip install pymupdf); the HTML report needs nothing") from exc
    colours = {PROVEN: (0.95, 0.6, 0.6), SUSPECTED: (1.0, 0.85, 0.5), NOTED: (0.7, 0.82, 1.0), CLEAN: (0.75, 0.9, 0.78)}
    doc = fitz.open(str(pdf_in))
    written = 0
    for f in report.findings:
        if not f.snippet:
            continue
        for page in doc:
            hits = page.search_for(f.snippet)
            if not hits:
                continue
            ann = page.add_highlight_annot(hits[0])
            ann.set_colors(stroke=colours[f.tier])
            ann.set_info(title=f"detective: {f.tier}", content=f"{f.ident}: {f.detail}")
            ann.update()
            written += 1
            break
    doc.save(str(pdf_out))
    return written
