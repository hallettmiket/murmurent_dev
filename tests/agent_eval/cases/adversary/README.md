# Adversary referral cases — ad01–ad06

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
