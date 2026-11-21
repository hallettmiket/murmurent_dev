# The integrity command: the detective's deterministic half

`murmurent integrity check` runs, on a manuscript, every check whose answer
comes from a registry rather than from a reader, and prints the findings in
four tiers. `murmurent integrity report` turns those findings into the
manuscript's own text with each one highlighted where it sits. The
[detective](https://github.com/hallettmiket/murmurent/blob/main/agents/detective.md)
runs both and adds the reading in between; a person can run them alone. No
AI is involved in either command: the same file gives the same answer every
time, which is what makes a finding a proof. Issue #341 holds the discussion
that led here.

## `murmurent integrity check <manuscript> [--journal NAME | --issn ISSN] [--json]`

The manuscript is a `.tex` (its `\bibliography{}` files are followed and
only the cited entries checked), a `.md`, a `.txt`, a `.bib`, or a `.pdf`
(read through `pdftotext`, which Homebrew's `poppler` provides; without it
the PDF is reported as not read).

| Check | What is sent out | Where it goes | What comes back |
|---|---|---|---|
| citations | each DOI, PMID and arXiv ID | Crossref (with Retraction Watch), PubMed, DataCite, doi.org | not found; a different paper from the one the bibliography claims; retracted; an expression of concern; exists |
| data | each accession: GEO (`GSE`, `GSM`, `GDS`, `GPL`), BioProject (`PRJNA`, `PRJEB`, `PRJDB`), SRA and ENA runs and studies (`SRP`, `SRR`, `ERP`, ...), EGA (`EGAS`, `EGAD`, ...), PRIDE (`PXD`), ArrayExpress and BioStudies (`E-MTAB-`, ...), dbGaP (`phs`) | the archive's own record | not found; held but not public; public |
| availability | nothing | the text itself | "on request", "will be deposited", a placeholder where an accession should be, no statement at all |
| ai_residue | nothing | the text itself | a phrase a language model writes to its user and a person does not leave in a paper |
| journal | the ISSN or the name | DOAJ, and the journal registry [`docs/journals.md`](journals.md) | listed or not, and the registry's row |

**Nothing of the manuscript's sentences leaves the machine.** Identifiers,
the ISSN and the journal's name are the only things sent, and each goes to
the service that issued it.

### The four tiers

| Tier | Meaning | Exit |
|---|---|---|
| `PROVEN` | the registry's own answer is the proof, and it is quoted in the finding | exit status 1 |
| `SUSPECTED` | the facts point at a problem and do not settle it; the finding names what would | 0 |
| `NOTED` | a fact with no verdict: a deferral, a leftover phrase, a journal DOAJ does not list, a check that could not run | 0 |
| `CLEAN` | checked, nothing found; the row says by what | 0 |

The command does not know intent, so it never writes about a person; every
finding is about the manuscript. A retracted citation is `PROVEN` as a fact
about the record, and the finding says in the same breath that citing a
retracted paper is not in itself a violation. "Data available on request" is
`NOTED`, because whether that is allowed is the journal's policy, which the
detective reads and the command does not.

Each finding carries the line it anchors to (`where: paper.tex:212`) and the
exact text matched (`snippet`), which is what `report` highlights. A phrase
that wraps across a line break is found and anchored to the line it starts
on.

### What it does not check

The command prints these under **Not checked** every time, so the absence of
a finding is never read as a clean result:

- figure panels for duplication or splicing, which needs an image tool
  (the detective names Imagetwin, Proofig and the open research code);
- whether a cited paper supports the sentence that cites it, which needs a
  reader (the detective, then the adversary);
- the journal, when none was named.

## `murmurent integrity report <findings.json> [--out page.html] [--pdf-out copy.pdf] [--title ...]`

Reads the JSON that `check --json` printed, with any findings the detective
appended in the same shape, and writes:

- an HTML page: the findings table, worst first, each linked to its line;
  a **Not checked** list; then the manuscript's whole text, numbered, with
  every finding's snippet marked in its tier's colour and the finding's
  evidence as a note under the line. Plain HTML with no scripts, readable
  offline, and a banner that the manuscript is confidential and the page
  stays inside the review;
- with `--pdf-out`, for a PDF manuscript, a copy of the PDF with the same
  findings as highlight annotations carrying the evidence as their note, so
  any PDF viewer shows them. This needs PyMuPDF (`pip install pymupdf`);
  the HTML needs nothing.

The JSON's shape, one object per finding:

```json
{"tier": "PROVEN", "check": "data", "ident": "GSE99999999",
 "where": "paper.md:9", "line": 9, "snippet": "GSE99999999",
 "detail": "GEO has no record of GSE99999999: its own page answers that the accession could not be found",
 "source": "GEO", "link": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE99999999"}
```

The detective appends its own findings (a citation that is a real paper
about something else, a number the source does not contain, a policy the
availability statement does not meet, what the adversary found) with
`check` set to what it did, and renders once.

## Trying it

```bash
murmurent integrity check paper.tex --journal "Nature Methods" --json > findings.json
murmurent integrity report findings.json --out paper.integrity.html
```

A planted manuscript with a retracted citation, a DOI nobody issued, a GEO
series GEO cannot find and "available upon reasonable request" gives, on
2026-11-21, four `PROVEN` findings each quoting the registry, two `NOTED`
deferrals, the leftover phrase as `NOTED`, and `CLEAN` rows for the real
citation, the public series, the EGA study and the PRIDE project. The tests
in `tests/test_integrity_check.py` pin that with canned registry answers.
