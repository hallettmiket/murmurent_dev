# The institution pack and the Clerk

An **institution pack** is a folder of facts about one institution, each fact
with the page it was read from and the date it was read: who holds an office,
the holidays and term dates, which sections a course has, the steps of a
procedure with their forms and deadlines, and the letterhead colours and
fonts. The [Clerk](agents.md#clerk) answers from a pack and from nothing else.

The agent is small; the knowledge is the pack. A language model already
"knows" a great deal about any university, and some of it is years old. The
Clerk's value is that it answers only from the pack and says `Unknown`, with
the nearest fact it does hold, when the pack is silent. Relax that and it is a
chatbot with the university's logo. Everything below exists to keep the pack
right: every fact dated, every fact sourced, and a command that re-reads them.

## What the Clerk does

Three jobs, inferred from what it is given, and a fourth small one:

| Ask it | It runs | Verdict |
|---|---|---|
| "Is this letter to the Dean right?" (a document) | `murmurent institution check <file>` | `Correct / Fix / Unknown` per office holder, email, postal code, colour and font named in the document |
| "25 working days before the defence" (a date) | `murmurent institution date 2027-04-16 --days -25` | the date, the weekday, and the holidays it skipped; never a holiday |
| "What is next for the thesis, and by when?" (a procedure) | `murmurent institution walk thesis_examination --anchor 2027-04-16 --variant doctoral` | the steps with their forms and dates |
| "Who is the Graduate Chair?" (a fact) | `murmurent institution show office "Graduate Program Chair"` | the entry with its source, date and age note |

Every answer carries the source page and the date read. A fact older than the
pack's `max_fact_age_days` (180 by default) is answered with its age stated,
so a reader knows to confirm it.

## Where a pack lives and which one is used

```
institution/
  README.md
  example/             ships with murmurent: invented facts on example.edu, a starting point and the tests' fixture
  <unique_name>/       your centre's pack, named after the centre's unique_name
```

A centre's own pack is deployment content, like `rules/local/`: it holds the
names and emails of real office holders and does not go in the public release
(`release/allowlist.yaml` withholds `institution/western/`; add yours beside
it). The commands choose the pack in this order: `--pack <name or folder>`,
then `$MURMURENT_INSTITUTION_PACK` (a pack folder), then the centre's
`unique_name` from `centre.md` under `institution/`. `$MURMURENT_INSTITUTION_ROOT`
moves the whole folder. The example pack is never chosen by default.

## The schema

```
institution/<unique_name>/
  institution.yaml        name, unique_name, domains, keeper, max_fact_age_days
  directory.yaml          offices: office, person, title, email, address, room, phone, note, source, date_read
  calendar.yaml           holidays (name, date), terms (name, start, end, evidence), deadlines (name, date, evidence)
  courses.yaml            fetch: a rule (url, method, fields, parser, limits); cache: one entry per course
  procedures/<name>.yaml  title, read_on, confirm_with, constants, steps, sources
  templates/letterhead.yaml  colours (name, role, hex, ...), fonts (name, role, weights), colour_rules, letterhead_templates
```

Rules that `murmurent institution validate` enforces:

- **Every fact carries `source:` and `date_read:`.** The source is a page on
  one of the pack's `domains` (`uwo.ca` admits `grad.uwo.ca`; nothing else is
  admitted). The date is `YYYY-MM-DD`.
- **The directory holds only what the institution publishes**: office,
  person, title, public email, campus address, room, phone, a note. Any other
  field is an error. Nothing from LinkedIn, nothing inferred. The
  [Lawyer](agents.md#lawyer) reads this schema once before a centre's first
  pack is filled, because the directory holds people.
- **A fact that cannot be read from such a page is left out**, with a `note:`
  on the nearest entry saying so if it matters. An absent fact makes the Clerk
  say `Unknown`; a guessed fact makes it wrong.

A procedure's steps are ordered. Each has a `title`, an optional `form`, an
optional `owner`, and an optional `deadline:` mapping with `working_days`
(negative means before the anchor), `relative_to` (the anchor's name, such as
`defence`), `rule` (the sentence to show) and, when the lead differs by case,
`by:` with per-variant values (`by: {doctoral: -25, masters: -15}`). The
`constants:` block holds limits the code reads (word counts, board
composition); `sources:` lists the pages with their dates.

`courses.yaml` is a **fetch rule plus a cache**, not a hand-typed list, because
timetables change every term. The rule names the page, the method, the form
fields with `{subject}` and `{number}` placeholders, and a `limits:` paragraph
stating what the page does and does not show. The parser reads a page shaped
like Western's master timetable: a heading per course, then a table with a
header row. For Western, read on 2026-11-07, the public page gives each
section's number, component, class number, requisites, status, campus and
delivery type, and **not** the days, times or rooms; so the Clerk can say which
sections a course has and whether they are full, and answers `Unknown` to "when
does it meet", naming the timetable page. Another institution's rule states
its own limits.

## Making your centre's pack

```bash
murmurent institution init <unique_name> --name "Your University" --domain your.edu --seed-thesis
```

This writes the empty files and, with `--seed-thesis`, a
`procedures/thesis_examination.yaml` from the seed built into murmurent
(Western's SGPS rules as read on 2026-11-06). Rewrite that procedure for your
graduate school, or delete it if you have none: a company's pack has offices, a
calendar, procedures and templates, and no thesis. The agent does not know the
word "Western"; a different pack is a different institution.

Then fill the files one fact at a time, from your institution's own pages,
writing the page and the date on each. `murmurent institution validate` says
what is missing. `murmurent institution fetch-course SUBJ 1234 --apply` caches
a course once the fetch rule is written.

The thesis paperwork that `murmurent thesis paperwork` writes
([`paper_package.md`](paper_package.md)) reads the pack's `thesis_examination`
procedure when a pack is found: the steps, the limits and the deadlines, which
then skip the pack's holidays. With no pack, it uses the seed and skips
weekends only, and says so in the file.

## Keeping it: the refresh

Reliability is a maintenance commitment. Office holders change; timetables
change each term. Two things keep the pack honest:

1. **A visible date on every answer.** The Clerk repeats the `date_read` and,
   past the limit, the age.
2. **`murmurent institution refresh`.** It re-reads every fact from its source
   page, inside the pack's domains only, and reports what it found: confirmed
   (the person's name and email, the holiday's date, the course's sections are
   still on the page), changed (no longer there), unreachable. It is a dry run
   by default. With `--apply`, every confirmed fact gets today's `date_read`
   and every cached course is re-fetched. **A changed fact is reported, not
   rewritten**: what replaced a Dean is a person's reading of the page, not a
   parser's. The [Bookworm](agents.md#bookworm) keeps the pack the way it
   keeps `docs/reporting_guidelines.md`, and a lab runs the refresh on a
   schedule under its service account, the way the space scan runs
   ([`service_account.md`](service_account.md)); the run's report goes to the
   keeper, who edits the changed facts.

The fetch is `urllib` with a strict host rule: the page must be on one of the
pack's domains, and a redirect to another host is refused. A redirect the
institution's own site makes to plain `http` on its own host is followed.

## What the Clerk may do online

Only fetch from the pack's domains, and only for two reasons: to refresh a
fact a person is about to rely on, and to cache a course. Both write into the
pack with source and date, through the commands, so what it learns is there
for the next session. It has no search tool. It has no write tool: the
commands write the pack, and a person edits a changed fact.

## Sources for the Western pack

The Western pack (`institution/western/`, not in the public release) was
filled on 2026-11-07 from pages on `uwo.ca` and `westernu.ca`: the HR holiday
schedule, the Academic Calendar's sessional dates, the Provost's leadership
team page, the Western Research leadership pages, the Schulich, Science and
Health Sciences dean pages, the University Secretariat directory, the
Biochemistry staff and contacts pages, the brand site's colour, typography and
letterhead pages, and one query of the master timetable. Its `README.md` lists
what those pages did not give and so is not in the pack.
