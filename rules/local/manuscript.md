# Manuscript pull-first rule

The murmurent manuscript lives in its own repo, synchronised with
**Overleaf via GitHub**:

- Working clone: `~/repos/murmurent_manuscript`
- Remote: `git@github.com:hallettmiket/murmurent_manuscript.git`
- Single source file: `main-article.tex` (Springer Nature class).
- Bibliography: **`mm_bib.bib` is the current one**, and new references go
  there. `wigamig_bib.bib` is still cited for older entries, so both are
  loaded by `\bibliography{mm_bib,wigamig_bib}`. Both are exported from
  Zotero, so do not hand-edit them: ask Mike to add a missing reference.

Mike edits the manuscript **both** locally (through Claude Code) and on
Overleaf (in a browser). Overleaf pushes to GitHub, so the GitHub `main`
can be ahead of your local clone at any moment.

## The rule

**Before modifying the manuscript, `git -C ~/repos/murmurent_manuscript
pull` first.** Skipping this risks clobbering edits Mike made in
Overleaf, and produces merge conflicts that are painful to resolve
(Overleaf has no branches — everything is on `main`).

After a coherent block of edits: **commit and push promptly** so
Overleaf can fetch them. Do not sit on uncommitted manuscript changes.

## Guardrails (from the manuscript's own `CLAUDE.md`)

- **Overleaf edits are authoritative** on conflict — if a `git pull`
  produces conflict markers in a `.tex` file, stop and ask before
  resolving.
- **No feature branches** — Overleaf only tracks `main`.
- **No bulk reformatting** (rewrapping, reordering preamble) — Overleaf
  reads whitespace churn as content changes and it buries real edits.
- **Do not edit auto-generated artefacts** (`*.aux`, `*.bbl`, `*.blg`,
  `*.log`, `*.out`, `*.synctex.gz`) — Overleaf regenerates them on
  compile. **Do not compile locally**; Overleaf compiles.

The manuscript is the authoritative description of murmurent's purpose and
architecture. When doing admin-level or design work, read it (and the
code) before acting: see the `/murmurent-admin` skill.

## Voice

Read the manuscript's writing voice before drafting any of it. It is in
`~/repos/murmurent_manuscript/CLAUDE.md`, under "Writing voice", and it is
stricter than the general voice in
[`output_styles/plain_english.md`](../../output_styles/plain_english.md). It is
a scientific paper for a peer-reviewing biomedical audience: factual and
cited, concise, serious and understated, every term defined on first use,
British and Canadian spelling. When in doubt, flag rather than invent.

## Which murmurent repository

Both exist and both are live. They are not copies of each other.

- `~/repos/murmurent_dev` is where development happens. Change code, agents,
  rules and documentation here.
- `~/repos/murmurent` is the released version. Read it to see what members
  actually have installed. Do not develop in it.

The manuscript describes the system, so read `murmurent_dev` when writing
about how something works now, and `murmurent` when writing about what has
shipped.
