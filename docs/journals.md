# The journal registry: what the detective knows about a journal

The [detective](https://github.com/hallettmiket/murmurent/blob/main/agents/detective.md)
reports facts about the journal a manuscript was submitted to or published in,
never the word *predatory*: whether it is listed in the Directory of Open
Access Journals (DOAJ), whether its publisher is a member of the Committee on
Publication Ethics (COPE), where it is indexed, what its own pages say about
peer review and fees, and the date each of those was read. This file is where
those facts accumulate. The [bookworm](https://github.com/hallettmiket/murmurent/blob/main/agents/bookworm.md)
keeps it, as it keeps the funder registry and the reporting checklists; the
detective proposes rows and never edits the file.

**Why facts and not a list.** Beall's list, the one list people remember, was
taken down by its author in 2017 and was contested while it stood; the lists
that replaced it are paid (Cabells) or partial. A journal is also not one
thing forever: a title is bought, a publisher reforms. So a row here says what
was read on a given day, with the page it was read from, and the reader draws
the conclusion. A row with nothing in **Flags** is a journal nobody has found
anything against on the pages read; it is not an endorsement.

**What `murmurent integrity check --journal` does with this.** It looks the
journal up in DOAJ by ISSN or title on the day it runs, and reads this file
for a row with that ISSN or title. The DOAJ answer is reported as a fact with
its caveat (DOAJ lists open-access journals that meet its criteria; a
subscription journal is not expected there). The row is reported as the
registry's own. Both are `NOTED` or `CLEAN`, never `PROVEN`: the registry
cannot prove intent on anyone's part.

## Where the facts come from

| Source | What it says | How it loads |
|---|---|---|
| [DOAJ](https://doaj.org) | open-access journals that meet DOAJ's criteria; ISSN, publisher, APC, review process | plain; a documented API at `doaj.org/api/search/journals/issn:<issn>` |
| [COPE members](https://publicationethics.org/members) | publishers and journals that are members | script: the member search is drawn by a script; open it in a browser |
| [Retraction Watch database](https://retractionwatch.com/retraction-watch-database-user-guide/) | retractions by journal, now carried by Crossref | through `murmurent cite check`, per DOI |
| [PubPeer](https://pubpeer.com) | post-publication comments on a paper, by DOI: `pubpeer.com/search?q=<doi>` | script: the search page is drawn by a script; open it in a browser; a DOI with no comments proves nothing, since indexing has gaps |
| [NLM Catalog](https://www.ncbi.nlm.nih.gov/nlmcatalog) | whether a journal is indexed in MEDLINE or PubMed | plain |
| [Scopus sources](https://www.scopus.com/sources) | whether a journal is indexed in Scopus, and discontinued titles | login |
| the journal's own pages | editorial board, fees, review process, data policy, the publisher's address | varies; read on the day |

## Journals

One row per journal read. **Indexed** names the indexes the pages confirmed
on the date checked. **Flags** holds what was found against the journal, in
one short factual line each, with the page it was read from, or is empty.
**Checked** is the date the row's pages were read.

| Journal | ISSN | Publisher | Indexed | Flags | Checked |
|---|---|---|---|---|---|
| [F1000Research](https://f1000research.com) | 2046-1402 | F1000 Research Ltd (Taylor & Francis) | DOAJ | | 2026-11-21 |
| [Nature](https://www.nature.com) | 0028-0836, 1476-4687 | Springer Nature | MEDLINE | | 2026-11-21 |

## Proposing a row

The detective ends its report with **For the bookworm** when the journal it
was asked about has no row: the journal's name, ISSN, the pages it read and
what they showed. The bookworm reads the pages again and adds the row. A
flag goes in only with the page it was read from; "looks predatory" is not a
flag.
