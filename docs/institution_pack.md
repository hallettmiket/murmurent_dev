# The Clerk and the institution pack

Ask the [Clerk](agents.md#clerk) anything about your institution: who runs
an office and how to reach them, when the final exams for a course must be
printed, which holidays fall in a count of working days, what a procedure
requires next and by when, which colours and fonts a letter must use. It reads
the answer off the **institution's own web pages** (a web search limited to
the institution's domains, then the page itself), tells you which page and
when it read it, and says `Unknown` when the institution's pages do not say.
Never from memory: a language model "knows" a great deal about any
university, and some of it is years old.

The **institution pack** (`institution/<unique_name>/`) is the Clerk's
**memory**, not a reference it was loaded with. Nobody precomputes it. When
the Clerk looks something up, it records the question, the answer, the page
and the date in `facts.yaml`, and an office holder it confirmed in
`directory.yaml`, so the next person who asks gets the answer at once, and so
the lab can see what the Clerk has been relying on. A centre may also keep a
few things there on purpose, because they change rarely and are relied on
often: the thesis procedure with its forms and deadlines, the holidays and
term dates, the letterhead.

**How it stays current.** People and office holders change; a pack that
never changed would be worse than none. Three mechanisms:

| When | What happens |
|---|---|
| Every answer | carries the page and the date it was read |
| A remembered fact is older than `verify_after_days` (30 by default) | the Clerk re-reads its page before relying on it (`murmurent institution verify`): the page still says so, and the fact is restamped; or it no longer does, and the Clerk says the page changed and looks again |
| Weekly, on the lab server | `murmurent institution refresh --apply` re-reads every remembered fact from its page and reports what changed; a changed fact is left for a person to settle |
| A fact is older than `max_fact_age_days` (180) | it is answered with its age stated |

## How the Clerk answers a question

1. **Recall**: `murmurent institution recall "<question>"` lists what the
   pack remembers on it, with dates, and says which entries need verifying.
2. **Search the institution's own site**: `WebSearch` with `allowed_domains`
   set to the pack's domains, then `WebFetch` the page. A question that
   combines a rule and a date (the printing deadline for a course's exam)
   is answered from the rule page and the schedule page together, with
   `murmurent institution date` for the arithmetic, and the answer says
   which part was read and which computed.
3. **Learn**: `murmurent institution learn "<question>" --answer "..."
   --source <url> --evidence "<a phrase on the page>"` (or `--office` for an
   office holder). The command fetches the page and refuses a fact the page
   does not state, so nothing enters the memory from recollection.
4. **Answer**, with the page and the date.

On a machine without a web search tool, `murmurent institution lookup
"<question>"` crawls two links deep from the pack's hub pages (a websites
A-Z, listed under `lookup.pages` in `institution.yaml`) and lists the pages
that mention the question.

## The three jobs on top

| Ask it | It runs | Verdict |
|---|---|---|
| "Is this letter to the Dean right?" (a document) | `murmurent institution check <file>` | `Correct / Fix / Unknown` per office holder, email, postal code, colour and font named in the document; an office the pack lacks is looked up first |
| "25 working days before the defence" (a date) | `murmurent institution date 2027-04-16 --days -25` | the date, the weekday, and the holidays it skipped; never a holiday |
| "What is next for the thesis, and by when?" (a procedure) | `murmurent institution walk thesis_examination --anchor 2027-04-16 --variant doctoral` | the steps with their forms and dates |

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

## Keeping it: the refresh, on a schedule

On the lab server, under the lab service account that runs the other timers
([`docs/service_account.md`](service_account.md)), a weekly user timer runs
the refresh and keeps its report:

```ini
# ~/.config/systemd/user/murmurent-institution-refresh.service
[Unit]
Description=murmurent: re-read the institution pack from its sources
[Service]
Type=oneshot
WorkingDirectory=%h/repos/murmurent
ExecStart=/bin/sh -lc 'murmurent institution refresh --apply > %h/.murmurent/institution_refresh.log 2>&1'

# ~/.config/systemd/user/murmurent-institution-refresh.timer
[Unit]
Description=murmurent: weekly institution refresh
[Timer]
OnCalendar=Mon 06:30
Persistent=true
[Install]
WantedBy=timers.target
```

`systemctl --user enable --now murmurent-institution-refresh.timer`. The
report lists every fact the page no longer confirms; those are for a person
(the bookworm, on the PI's say) to settle, and the Clerk says "the page
changed" until they do. Between refreshes, the verify-on-read rule above
catches a change the moment someone relies on the fact.

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

Read pages on the pack's domains and on no other host; search only with the
results limited to those domains; put into a query the public words of the
question (a course code, an office, a term) and never a sentence from a
document, a project's data, or a person's details beyond their public office.
What it reads goes into the pack through the commands, never into the YAML by
hand (it has no Write tool), and never into an answer as an unsourced fact.

## Sources for the Western pack

The Western pack (`institution/western/`, not in the public release) was
filled on 2026-11-07 from pages on `uwo.ca` and `westernu.ca`: the HR holiday
schedule, the Academic Calendar's sessional dates, the Provost's leadership
team page, the Western Research leadership pages, the Schulich, Science and
Health Sciences dean pages, the University Secretariat directory, the
Biochemistry staff and contacts pages, the brand site's colour, typography and
letterhead pages, and one query of the master timetable. Its `README.md` lists
what those pages did not give and so is not in the pack.
