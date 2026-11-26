# The lookout: keeping murmurent current

New tools, methods and conventions for agentic AI appear every week, from
Anthropic, from the other harnesses murmurent runs on, from the research
literature and from the people who use these systems. Nobody in a research
centre has the hours to read it all, and a system that is not kept current
quietly falls behind the one its members would have built this year. The
[lookout](https://github.com/hallettmiket/murmurent/blob/main/agents/lookout.md)
does the reading, on a schedule, and reports the few items that would make
murmurent better at its one job.

**What it does.** It reads murmurent's own files first, then its own earlier
reports, then every page on the [watch list](watch.md), then a fixed set of
searches, and reports at most ten items, best first. Each item carries the
link, the date read, what it is in one sentence, the murmurent file or agent
it would touch, why, a size, and one of three labels: `ADOPT` (a clear gain,
the PI decides, the blacksmith builds), `CONSIDER` (needs a trial or a
scope decision first) or `WATCH` (worth knowing, not ready). An empty run
still lists what it read, so silence is never ambiguous.

**What it does not do.** It installs nothing, enables nothing and edits
nothing: the PI decides, the [blacksmith](agents.md#blacksmith) builds, the
[bookworm](agents.md#bookworm) keeps the watch list. It reports nothing it
did not read today on its own page, and nothing murmurent already has under
another name. A query carries public terms only, never the centre's name, a
person's, a project's, a server's or a file path.

## The report, as an issue

When run as the routine, each report is one GitHub issue in the murmurent
repository, labelled `lookout` and titled `Lookout: <date>: <one line>`,
with the table and the two closing sections as its body, and a one-line
Slack note through `murmurent project note` naming it. The issues are the
lookout's memory: it reads the last few before it searches, so nothing is
reported twice. Close an issue when its items are decided; the lookout reads
closed issues too.

Create the label once, in the repository:

```bash
gh label create lookout --color 1D76DB --description "The lookout's reports: new techniques worth a look"
```

## The schedule

The routine runs twice a week as a Claude Code **cloud scheduled task**,
the mechanism the [reconcile routine](reconcile.md) uses. Claude Code called
these routines until November 2026 and `/routines` still works; `/schedule`
is the current name. Set it up once:

```
/routine create murmurent-lookout
  prompt: |
    Dispatch the lookout agent for its scheduled run. It reads murmurent's
    own files, its earlier issues labelled lookout, every page on
    docs/watch.md and the fixed searches, and files one GitHub issue
    labelled lookout with at most ten items, then posts a one-line note
    with `murmurent project note "<repo> · lookout: <issue title and
    link>"` from the murmurent repository. It installs nothing and edits
    nothing. If it could read nothing, it files no issue and posts the
    verdict instead.
  schedule: Monday and Thursday at 07:00 America/Toronto
```

Twice a week is enough: a changelog gains a handful of entries in three
days, and a report that arrives more often is a report nobody reads. A
centre that wants another cadence changes the schedule line.

**Check it is still scheduled.** Claude Code 2.1.330 (20 November 2026)
changed how saved scheduled tasks are stored: most saved by earlier versions
need scheduling again, and a recurring task made before that release still
ends after seven days where a new one runs thirty. The lookout's first run
found this, which is why it is written here. When a report has not arrived
for a week, `/tasks` shows whether the task exists; if not, create it again.
The same applies to the reconcile routine.

## By hand

Ask it a question in any session:

```
lookout, anything new on agent memory since October?
lookout, has Claude Code changed how subagents are defined?
lookout, is there a maintained MCP server for UniProt?
```

It answers in chat in the same shape, and files an issue only if asked.

## Where the findings go next

An `ADOPT` the PI accepts is a task for the blacksmith, or for a session,
with the issue as its brief. One that touches a hook, a secret, patient data
or what leaves the machine names the security guard as its first reviewer.
One that changes how an agent file is written must leave the agent tests
passing. The decision and its reason go on the issue before it is closed, so
the next report, and the next PI, can read why.

## What to tune

- **The watch list** ([watch.md](watch.md)): the pages. A centre on another
  harness adds its changelog; one with a field the searches miss adds a
  query. The bookworm edits; the lookout proposes.
- **The cap**: ten items, in the agent file's `items_max`. Fewer is better.
- **The cadence**: the schedule line of the routine.
