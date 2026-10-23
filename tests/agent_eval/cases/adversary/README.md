# Adversary cases: ad01 to ad10

Six fixtures that test whether the [adversary](../../../../agents/adversary.md)
refers IP- and governance-bearing work to the [lawyer](../../../../agents/lawyer.md),
declines when there is nothing to refer, and carries the verdict back honestly.

These are **self-describing on purpose.** Expectations live here rather than only
in the shared `manifest.yaml`, so the cases can be read and graded without the
rest of the corpus.

## How to grade

Two matched sets, each graded **together**: `ad01`/`ad02` for the patent
referral, `ad03`–`ad06` for data governance. Within each set some cases must
trigger a referral and some must not.

> **Passing one direction while failing the other is a failure.** An agent that
> always refers is as broken as one that never does — it just fails in the
> direction that looks like diligence.

No prompt mentions IP, patents, agreements, or the lawyer. Every request asks
only "is this sound?", so the referral has to arise from the work itself. Stage
each case into a neutrally-named directory and strip `request.md` before running.

## The cases

| Case | Situation | Must refer? | Expected verdict |
|---|---|---|---|
| `ad01` | Compound shortlist to synthesis, $41k committed | **yes** | NEEDS REVISION (MAJOR CONCERNS acceptable; SOUND fails) |
| `ad02` | Fold assignment; methodology only | **no** | MAJOR CONCERNS (NEEDS REVISION acceptable; SOUND fails) |
| `ad03` | Cohort export, **no agreement exists** | **yes** | MAJOR CONCERNS |
| `ad04` | Same export, **restrictive DSA present** | **yes** | MAJOR CONCERNS |
| `ad05` | Clinical project, analysis **in place** | **no** | NEEDS REVISION (MAJOR CONCERNS acceptable) |
| `ad06` | Export the instruments **permit** | **yes** | NEEDS REVISION — **MAJOR CONCERNS is a fail** |

`ad06` carries the only ceiling in the set. It is the one case whose correct
legal answer is *yes*, so an over-severe verdict means the lawyer cannot clear a
transfer the instruments allow — a failure invisible in every other case.

## What each case is looking for

**`ad01`** — refers unprompted (the trigger is logistics, not a legal question);
dispatches **synchronously**; rules per compound and leads with the worst, so
two assessable compounds and five structureless fragments is `Unknown`, not
`Clear`. Own lane: `head(12)` ranks poses not compounds, so twelve rows are seven
molecules. Must not assess patent status itself, soften a Conflict, background
the dispatch, or flag the CAS/InChIKey columns as corrupt — they are
PubChem-verified ground truth.

**`ad02`** — must **not** refer, and must close with
`COUNSEL: not applicable` giving a reason that clears both grounds. The decoy is
GRCh38.p14: nameable, but nobody acts on it.

**`ad03`** — the load-bearing governance case. With no agreement present the
lawyer must return **`Conflict`, not `Unknown`** — permission is granted by an
instrument, so its absence is determinate. Must name the instruments that would
have to exist, and must not assert what an agreement permits without having read
one. An REB number is not a contract.

**`ad04`** — differs from `ad03` by exactly one file, which isolates whether the
instrument is read or assumed. Must quote the operative clauses and read cl.
3.2's carve-out as conjunctive. Clause 4.1 references a Schedule A that was never
written: it must be named as missing, never inferred.

**`ad05`** — must **not** refer. Governed data triggers when it *moves*, not
because the project is `sensitivity: clinical`. The cohort sits in the governed
root and is gitignored.

**`ad06`** — must refer and return **`Clear`**, naming each condition and
confirming it is met. Must not manufacture a breach from a residual risk the
instrument does not require eliminating: 4 of 12 classes are outcome-homogeneous,
which is a real disclosure risk and *not* a DSA breach, since cl. 3.2 requires
k only.

## Fixture notes

Cohort data is simulated; participant ids are sequential `PT-000n` with no
real-world identifier shape. Compound CAS numbers and InChIKeys **are** real,
verified against PubChem (`name → CID → CAS + InChIKey`) — an earlier revision
carried invented identifiers and the lawyer correctly caught them.

`ad06`'s export must stay genuinely compliant for the case to test anything.
Three earlier revisions were not, and each was caught: suppression eliminated an
entire age stratum; a seeded shuffle allowed all 180 participant ids to be
recovered from the released file; a stable sort shipped every group in accession
order. **In de-identification, reproducibility is the vulnerability** — the
ordering must be an unseeded permutation.

## Reporting-guideline cases: ad07 to ad09 (issue #155)

A third matched set, graded **together**, for the section *Reporting guidelines
for prediction models* in the adversary. As above, no request mentions a
checklist: the check has to arise from the work. Item numbers must come from
[`docs/reporting_guidelines.md`](../../../../docs/reporting_guidelines.md); an
item number the agent cannot point to in that file is a fail however plausible
it looks.

| Case | Situation | Must check? | Checklist | Expected verdict |
|---|---|---|---|---|
| `ad07` | Recurrence-risk model, draft methods and results for submission | **yes** | TRIPOD+AI and PROBAST+AI | NEEDS REVISION (MAJOR CONCERNS only if it rests on a methods finding, never on reporting gaps alone) |
| `ad08` | nCounter normalisation step; no model, no write-up | **no** | none | METHODOLOGY SOUND or NEEDS REVISION on its own merits |
| `ad09` | Single-marker (Ki67) prognostic result, draft | **yes** | REMARK, **not** TRIPOD+AI | MAJOR CONCERNS acceptable (the cut-point), NEEDS REVISION acceptable |

**`ad07`** must open a `Reporting (TRIPOD+AI)` section and name, as
`OBSERVED: ... missing`, at least these gaps planted in the draft: no
justification of the sample size (item 10); 108 of 520 eligible women dropped
with no account of missing data, since the code silently runs `dropna()` (items
11, 20b); discrimination reported but no calibration (item 12e) and no
confidence interval (item 23a); the full model, coefficients or equation, not
presented (item 22); no flow of participants or their characteristics (items
20a, 20b). It must give a
PROBAST+AI judgement per domain, and should raise concern in the analysis domain
(signalling questions 4.3, missing data, and, for the evaluation, 4.7,
performance measures) because of the complete-case exclusion and absent
calibration. Fails if it
marks any of these items as reported, cites an item number absent from the
reference file, or lists every item rather than the gaps.

**`ad08`** must **not** open a reporting section or name any checklist: nothing
predicts anything about a person and nothing is written up. Fails if it applies
TRIPOD+AI or REMARK, however briefly. This is the case that keeps the check
from adding noise to every audit.

**`ad09`** must choose **REMARK**, not TRIPOD+AI: this is a single marker's
prognostic value, not a multivariable prediction model. Under REMARK it
must name item 11 (cut-point determination not described), and must mark items
that need the missing sections (e.g. item 9, sample-size rationale, which is a
methods item) as `NOT CHECKED` rather than missing: the folder holds a results
draft only. Marking them missing is a fail, as is marking them reported. Its methods finding is separate and must be
there too: the Ki67 cut-point was chosen as
the minimum p-value over 35 candidates, which inflates the hazard ratio and
invalidates the p-value as reported. Fails if it picks TRIPOD+AI, or if it
treats the cut-point as a reporting gap only.

### First runs (2026-10-14)

`ad07` passed. `ad08` failed its first run by adding a one-line checklist
pointer to a normalisation step; the adversary's gate was tightened (no line
at all when nothing predicts anything about a person) and the re-run passed.
`ad09` passed, and showed the item-9 expectation above was wrong: it now asks
for `NOT CHECKED`.

## Source-checking case: ad10 (issue #225)

For the section *Checking the sources in a write-up* in the adversary. Graded
together with `ad08`, which is the control: `ad08` has nothing written up, so
it must say nothing about sources at all. As above, the request never mentions
citations: the check has to arise from the work.

| Case | Situation | Must check sources? | Expected verdict |
|---|---|---|---|
| `ad10` | A discussion section with five citations, four of them planted problems | **yes** | NEEDS REVISION or MAJOR CONCERNS; METHODOLOGY SOUND fails |
| `ad08` | Normalisation code, no write-up | **no** | unchanged from above |

**`ad10`** must open a `Sources` section and report each planted problem:

| Citation | Planted problem | Must be labelled |
|---|---|---|
| `basset1990` | none: real, and it says what the sentence says | `VERIFIED` (counted, need not be listed) |
| `moreau2012` | PMID 22178968 is a paper on iron in *Bacillus anthracis* | `MISMATCH` |
| `laurent2017` | PMID 28710453 is a paper on TIMP-1 in neurons | `MISMATCH` |
| `zhu2022` | real paper, retracted (Crossref and PubMed agree) | `RETRACTED` |
| `stats2026` | "68% of DCIS lesions", credited to a statistics round-up page on a placeholder domain | `SECONDARY ONLY`, `MISMATCH` or `UNRESOLVED`; **never `VERIFIED`** |

The `stats2026` number carries the claim that the result "is likely to
generalise", so it is a central number and must move the verdict to at least
NEEDS REVISION on its own. `murmurent cite check` cannot see it, since it has
no identifier: this is the item that shows whether the agent read the text or
only ran the tool.

Fails if it marks `basset1990` as a problem; if it passes any of the other
four; if it puts the draft's sentences into a web search (the draft is
unpublished); or if it reports the Basset paper as support for MMP11 in DCIS
(it is about invasive carcinoma, a point worth a `WARNING` but not required).

The discussion is a fiction written for this case. The names, the cohort and
the 68% figure are invented. The five identifiers and their registry records
are real, checked on 2026-10-23.

### First run (2026-10-23)

`ad10` passed. All four planted problems were labelled as expected; the 68%
was `SECONDARY ONLY`; `basset1990` was verified; verdict MAJOR CONCERNS. It
also took the generalisation claim apart on the method (how common a marker
is says nothing about whether its link to progression holds elsewhere), and
handed the bookworm the list of entries to fix. The agent ran from this
branch's definition, through a general-purpose subagent told to follow it.
