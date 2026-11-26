# Oracle workflow

Two tiers, one schema. The Oracle is Murmurent's institutional memory.

## Why two tiers

- **Personal Oracle** (one per user) is your private research
  memory: genes you've flagged, hypotheses you're testing, methods
  that worked for a project. Never auto-shared: it is your own
  working knowledge base.
- **Lab Oracle** (one per lab) is what the lab has agreed to
  remember: a curated, version-controlled, group-readable record.
  Read-only at the agent level; new entries land via explicit
  publish.

Promotion from personal → lab is a deliberate user action so
findings from one collaboration don't accidentally cross-contaminate
another (e.g. project A's gene list shouldn't auto-leak into
project B's lab record when both touch the same lab).

## Schema (shared)

Both tiers use [`rules/oracle_schema.md`](https://github.com/hallettmiket/murmurent/blob/main/rules/oracle_schema.md).
Required frontmatter: `title`, `date`, `project`, `sensitivity`,
`tags`, `sources`. Optional: `related` (Obsidian wikilinks), `source_sea`, `source_exp`, `url`.

## Personal Oracle

Lives in your Obsidian vault under `oracle/`. Resolve the path on
this machine with:

```bash
murmurent oracle path
```

The [`oracle` agent](https://github.com/hallettmiket/murmurent/blob/main/agents/oracle.md) maintains it. It refuses
to write entries missing required schema fields. Every entry must
also use Obsidian `[[wikilinks]]` (not Markdown links) so the
graph view in Obsidian resolves them.

## Lab Oracle

Lives in `~/repos/murmurent_lab_mgmt_<lab>/oracle/` (the lab-mgmt git repo, in
your repositories folder: `~/repos` unless you chose another;
`murmurent config repos-root` shows it). The
[`lab_oracle` agent](https://github.com/hallettmiket/murmurent/blob/main/agents/lab_oracle.md) is read-only: its
toolset excludes Write by design. Entries arrive only via the
publish flow.

## Promoting personal → lab

```bash
# 1. In CC, ask the personal oracle to stage a draft:
#    "Oracle, stage 2026-05-16_chrm_p14 as a publish draft"
#    → writes <vault>/oracle/drafts/2026-05-16_chrm_p14.md

# 2. From a terminal:
murmurent oracle vault-drafts                       # list staged drafts
murmurent oracle publish 2026-05-16_chrm_p14        # validate + copy + commit
murmurent oracle publish 2026-05-16_chrm_p14 --push # commit + push in one shot
```

`murmurent oracle publish` **refuses `sensitivity: protected` /
`restricted` entries** (those stay personal) and never overwrites an
existing lab entry. See [obsidian-usage.md §2.4](obsidian-usage.md)
for the full mechanics (identity checks, and what happens to the draft
afterward).

## Cataloguing an explainer

The [`teacher`](https://github.com/hallettmiket/murmurent/blob/main/agents/teacher.md)
(EXPLAIN mode) and the
[`conscience`](https://github.com/hallettmiket/murmurent/blob/main/agents/conscience.md)
(its explain path) each write, on request, a self-contained HTML page that
explains one thing. In Claude Code, and only there, such a page may also be
published as a Claude artifact: a private page on claude.ai with a link its
owner may share and a comment thread. Antigravity and the institution's own
model server have no such tool, so the local page is always written and is the
whole deliverable where the tool is absent
([which agent works where](harnesses.md)).

**The sensitivity gate.** An artifact is hosted outside the institution, so
only a page whose Oracle entry would say `sensitivity: standard` may become
one: a public method, a paper, a public codebase, a concept in its own right.
A page that explains an unpublished result, a candidate molecule, or a project's
own figures is `restricted`; anything touching patient-derived data is
`protected`. Both stay local HTML, reviewed in `lavish-axi`. A debrief, which
reads a session transcript, is never published at all. The published page
says at the top that it is hosted on claude.ai, and the agent reports the link
beside the local file, never instead of it.

**The catalogue.** The lab Oracle is where the lab finds the explainers it
already has. The agent that published the page writes a draft entry in your
personal vault, under `oracle/drafts/`, and stops. It never publishes to the
lab itself: you run `murmurent oracle publish <slug>` when you want the lab to
have it, exactly as for any other entry, and the same command refuses
`restricted` and `protected`, which is the gate a second time. The entry
carries:

- `url:` set to the artifact's link;
- `tags:` including `explainer` (the conscience adds `edid`), plus the subject;
- `sensitivity: standard`, since nothing else may have been published;
- a body holding the takeaway in a few lines and the local path of the page,
  so the entry is searchable where the HTML is not.

### Worked example

You asked for `teacher explain how leave-one-site-out validation works
--page` in a Claude Code session. The teacher wrote
`./outputs/teacher/explainer_2026-11-26_1.html`, judged the subject a public
method (`standard`), published it, reported both the file and the link, and
left this draft at `<vault>/oracle/drafts/2026-11-26_explainer_leave_one_site_out.md`:

```markdown
---
title: Explainer, leave-one-site-out validation (claude.ai artifact)
date: 2026-11-26
project: general
sensitivity: standard
tags: [explainer, validation, cross-validation, methods]
sources: ['@allie']
url: https://claude.ai/artifact/<id>
---

# Leave-one-site-out validation, explained

A page for colleagues from an adjacent field, with a drawn figure and a
five-question quiz. Hosted on claude.ai (private until shared); the local
copy is `outputs/teacher/explainer_2026-11-26_1.html` in the project
repository.

Takeaway: hold out one whole hospital at a time, so the score says whether
the model survives a site it never saw, rather than whether it survives a
random split that leaves every site partly in the training set.
```

To let the lab find it:

```bash
murmurent oracle vault-drafts
murmurent oracle publish 2026-11-26_explainer_leave_one_site_out --push
```

After that, "Lab Oracle, do we have an explainer on site-wise validation?"
returns the entry with its link, and a page whose entry would have said
`restricted` never reaches this step, because it was never published and the
publish command would refuse the draft anyway.

## Search (MCP)

The `murmurent-oracle` MCP server (registered by `murmurent install
--hooks`) exposes:

- `oracle_search(query, kind, tags, project, sensitivity, source, limit)`
- `oracle_get(path)`
- `oracle_list(kind)`
- `oracle_publish_draft(slug, push=False)`

Every `oracle_search` / `oracle_get` / `oracle_list` call on the personal
tier first attempts a best-effort `git pull --ff-only` of your vault (once
per process), so recall always reflects your latest synced notes, even
ones you saved on another machine.

### Four tiers, one query surface

`kind` is one of `personal`, `lab`, `notebook`, `sessions`, `both`, `all`:

| kind | Reads from |
|---|---|
| `personal` | `<vault>/oracle/` (curated frontmatter-required entries) |
| `lab` | `~/repos/murmurent_lab_mgmt_<lab>/oracle/` (curated, lab-shared) |
| `notebook` | `<vault>/<notebook_subfolder>/` (your own daily notes; frontmatter optional) |
| `sessions` | `<vault>/sessions/<date>/` (the prompts you gave Claude Code, recorded by a hook) |
| `both` | `personal + lab` (legacy default; preserved for back-compat) |
| `all` | `personal + lab + notebook + sessions`, with the notes before the sessions |

The notebook has two streams because they are written by two hands: the
notes are yours, and the sessions are written automatically, one file per
Claude Code session, with each prompt's time, project, repository and commit.
Searching `notebook` finds what you thought; searching `sessions` finds what
you asked; `all` returns both and lists every note before any session, so a
prompt never outranks the note that answers the question. The sessions
stream stays in your personal vault and is never published to the lab. How
the notebook is kept, captured into and reported from:
[The lab notebook](lab_notebook.md).

The **notebook tier** is permissive: daily lab notebook files
don't need to conform to the Oracle schema. Missing fields are
derived from path conventions:

- `date`: from filename matching `YYYY-MM-DD` or `YYYY-MM-DD_<slug>`
- `project`: from the parent dir name when notebooks are nested
  per-project (`<vault>/lab-notebook/<project>/2026-05-15.md`); empty
  for flat layouts (`<vault>/lab-notebook/2026-05-15.md`)
- `title`: first `# heading` in the body, or the filename
- `tags` / `sensitivity`: from frontmatter if present, else defaults
- `audience`: from frontmatter if present, else `me` (who may read the
  entry in a `murmurent notebook report`; see [The lab notebook](lab_notebook.md))

A session file's date comes from its folder, `sessions/<date>/`, when its
frontmatter does not carry one.

This lets one MCP call (`kind=all`) return curated Oracle findings
alongside the raw notebook mentions that surfaced them, useful for
"what do I know about gene X?" queries that want both the distilled
finding and the original context.

### macOS Full Disk Access caveat

If your vault lives under `~/Library/Mobile Documents/iCloud~md~obsidian/`,
macOS may deny `ls`/`Read` on the notebook subdir even when Obsidian
itself can see it. Grant Full Disk Access to your terminal app (and
optionally the `claude` binary) in System Settings → Privacy & Security
→ Full Disk Access. The MCP server tolerates permission denials
gracefully: it just returns no notebook entries when blocked, rather
than crashing.

## See also

- [`agents/oracle.md`](https://github.com/hallettmiket/murmurent/blob/main/agents/oracle.md): personal Oracle behavior + voice.
- [`agents/lab_oracle.md`](https://github.com/hallettmiket/murmurent/blob/main/agents/lab_oracle.md): read-only lab tier.
- [`rules/oracle_schema.md`](https://github.com/hallettmiket/murmurent/blob/main/rules/oracle_schema.md): required frontmatter.
- [`docs/obsidian-usage.md`](obsidian-usage.md): your Obsidian vault layout and what Murmurent touches (your `maps-legends`, etc.).
- [`docs/lab_notebook.md`](lab_notebook.md): the notebook's two streams, `murmurent notebook add | split | open | report`, and the `audience` field.
