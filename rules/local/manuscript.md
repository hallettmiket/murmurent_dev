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

Read the house writing guide before drafting any of it:
[`docs/scientific_writing.md`](../../docs/scientific_writing.md), built from
Mike's own hand edits to Claude-written text. For a passage of any length, use
the **Scribe** agent, which follows it and returns text for you to apply. The
manuscript's own `CLAUDE.md`, under "Writing voice", adds what is specific to
this paper. Both are stricter than
[`output_styles/plain_english.md`](../../output_styles/plain_english.md), which
is for documentation, not papers. When in doubt, flag rather than invent.

## Which murmurent repository

- `~/repos/murmurent_dev` (GitHub `hallettmiket/murmurent_dev`) is where
  development happens. Change code, agents, rules and documentation here.
- The released version is the GitHub repo **`hallettmiket/murmurent`**, built
  from murmurent_dev by `release/make_release.sh`. Read it on GitHub to see
  what members actually have. A local `~/repos/murmurent` folder, if there is
  one, may be far behind, since Mike works in murmurent_dev; do not treat it as
  the release, and do not develop in it.

Read `murmurent_dev` when writing about how something works now, and the
GitHub `hallettmiket/murmurent` repo when writing about what has shipped.
