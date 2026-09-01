# CLAUDE.md in the public release: what breaks, and the fix

Answers DECIDE-2. Written 2026-09-01 against `CLAUDE.md` at 186 lines.

## The short version

`CLAUDE.md` must ship. It is how a Claude Code session learns what murmurent
is, and a public release without one gives a new user a repo whose agents have
no context. But it cannot ship as written.

**The problem is not confined to CLAUDE.md.** `scripts/setup.sh` symlinks
`rules/` into `~/.claude/rules/`, so every rule file is auto-loaded into every
session on every machine that installs murmurent. Two of the six rules are
about this lab specifically. Shipping them tells a stranger's Claude Code to
pull a private repo and post to a Slack channel they cannot reach.

## The eight problems

| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | `CLAUDE.md:1` | Title reads *"agentic AI village for Western's Bioconvergence Centre"*, defining the software as one institution's | Retitle generically. Keep the Western attribution as an acknowledgement in `README.md`, which is where crediting where it was built belongs |
| 2 | `CLAUDE.md:7` | *"Full vision"* links `assets/chair_renewal_1.3.pdf`, a grant document that is withheld | Point at the docs site overview, and at the paper's DOI once minted. Not at the private manuscript |
| 3 | `CLAUDE.md:74` | Names `#claude-test`, this lab's dev channel | Describe the behaviour ("post to the project's own channel"), not the channel |
| 4 | `CLAUDE.md:75-76` | Summarises `rules/manuscript.md` and names `~/repos/murmurent_manuscript` | Drop the bullet. Per the PI, the release carries no reference to the manuscript repo |
| 5 | `CLAUDE.md:89` | The `/murmurent-admin` row says it *"reloads murmurent's purpose from the manuscript"* and *"enforces the manuscript pull-first rule"* | Reword to the code-and-docs half, which is all a public user has |
| 6 | `CLAUDE.md:172-177` | All four rows of the related-repos table are `hallettmiket/...`, and one is the private manuscript | Express as roles with a placeholder owner (`<owner>/murmurent_lab_mgmt_<lab>`). Keep exactly one concrete URL, the public repo people clone. Delete the manuscript row |
| 7 | `rules/manuscript.md` (whole file) | Auto-loaded into every session. Entirely about a private Overleaf-synced repo: working clone path, `git@github.com:` remote, pull-first rule | Do not ship the file |
| 8 | `rules/slack.md` | Auto-loaded. Hardcodes channel `#claude-test` and ID `C0B3D9DS6SE`, workspace `comp-bio-westernu`, bot `@murmurent2` and user `U0BHESELBAL`, and lab `mh` | Ship a generalised version: resolve the token and channel from config, name no IDs |

Three smaller ones, all docstring or comment text rather than behaviour:

- `skills/murmurent-admin/SKILL.md` names `murmurent_manuscript` five times, including a `git@github.com:` remote. Either the manuscript step is dropped from the released skill, or the skill does not ship.
- `src/murmurent/core/cert_projects.py:64` and `core/repo_inventory.py:215` use `murmurent_manuscript` as an example in docstrings. Change the example.
- `skills/murmurent-reset/reset.sh:236` lists it in a protected-paths `case`. Harmless, but the name appears.

## Note that CLAUDE.md contradicts itself today

Line 169 tells the reader:

> keep every deployment institution-agnostic (drive names off a centre's
> `unique_name`, never a hardcoded university)

while line 1 hardcodes a university. The rule is right; the file does not
follow it. Fixing #1 and #6 makes the document obey its own instruction.

## How to fix it: one file, not two

The obvious approach is to keep a second, sanitised `CLAUDE.md` for the
release. **Do not.** Two hand-maintained copies of the same document drift,
and neither can announce that it has: that is the pinned-default defect this
project catalogues, applied to the one file that tells every agent what is
true.

Factor the tied content out instead, so one file ships unchanged:

1. `CLAUDE.md` keeps only what is true for any centre.
2. A withheld `CLAUDE.local.md` holds this deployment's specifics: the Western
   title, the chair-renewal link, the manuscript repo and its rule, the Slack
   IDs, the `hallettmiket` owner. `CLAUDE.md` loads it if present.
3. `rules/manuscript.md` and the lab-specific half of `rules/slack.md` move to
   `rules/local/`, which is withheld. `scripts/setup.sh` symlinks `rules/*.md`
   plus `rules/local/*.md` when that directory exists.
4. The allowlist withholds `CLAUDE.local.md` and `rules/local/`.

The dev repo behaves exactly as it does now, because the local files are still
there. The release simply has no local layer. Nothing is maintained twice, and
the gate catches it if someone later puts a lab specific back in the shared
file.

## What I would need to do

Steps 1 to 4 are a contained change to `CLAUDE.md`, `rules/`, `scripts/setup.sh`
and the allowlist, plus a test asserting no shipped file names the manuscript
repo or a Slack ID. Say the word and I will make it.
