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
searches, and reports at most ten items, best first. Each item leads with
**why it is suggested, in plain words** a researcher can follow, then one of
three labels: `ADOPT` (a clear gain, the PI decides, the blacksmith builds),
`CONSIDER` (needs a trial or a scope decision first) or `WATCH` (worth
knowing, not ready), then the **effort to build it** (`small`, `medium` or
`large`: the blacksmith's work, not the item's importance). The technical
part follows: what the thing is, the murmurent file or agent it would touch,
the link and the date read. A **Source** column, in two or three words, says
where each item was found, so a reader sees at a glance which sources earn
their place.

**Video.** People who publish near-daily videos on Claude Code techniques
are on the watch list as named channels. The lookout reads what each one
uploaded since the last report from the channel's own feed and reads the
relevant uploads by their transcripts, with `scripts/lookout_videos.py`;
never the title alone, never as watched. Each report says, per channel, how
many uploads were read and what came of them, and the bookworm keeps that
as the channel's yield, so which channels are worth following is learned
over the months rather than guessed now. An empty run
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
with a short index table (item, label, effort, source), one block per item
giving the why, what it is, where in murmurent and the link, and the two
closing sections as its body, and a one-line
Slack note through `murmurent project note` naming it. The issues are the
lookout's memory: it reads the last few before it searches, so nothing is
reported twice. Close an issue when its items are decided; the lookout reads
closed issues too.

Create the label once, in the repository:

```bash
gh label create lookout --color 1D76DB --description "The lookout's reports: new techniques worth a look"
```

## The schedule

The routine is a Claude Code **cloud scheduled task** (Claude Code called
these routines until November 2026; `/routines` still works and `/schedule`
is the current name). It runs on Anthropic's machines, in a fresh clone of
the repository's default branch, on a schedule kept on your claude.ai
account, not in any file. Two consequences shape the prompt below: the
clone has none of your machine's files, so the agent is read from the
repository rather than from `~/.claude/agents/`; and the `murmurent` command
is not installed there, so the report is the GitHub issue alone and no
Slack note is posted (GitHub's own notifications carry it).

Set it up once, from any Claude Code session:

1. Type `/schedule the lookout, twice a week` and answer the questions it
   asks. Repository: this one. Cadence: Monday and Thursday, a few minutes
   past seven, Toronto time, which as a cron line is
   `CRON_TZ=America/Toronto 7 7 * * 1,4` (a run exactly on the hour can start
   late, so the docs suggest a minute past).
2. Give it this prompt:

   ```
   You are the lookout. Read agents/lookout.md in this repository and follow
   it exactly as your instructions: read CLAUDE.md, docs/agents.md,
   docs/harnesses.md and the Unreleased section of CHANGELOG.md first, then
   the earlier issues labelled lookout, then every page on docs/watch.md,
   then its fixed searches. File one GitHub issue in this repository,
   labelled lookout, titled "Lookout: <date>: <the verdict's one line>", with
   at most ten items in the report table and the two closing sections. Install
   nothing, enable nothing, edit nothing, commit nothing. If you could read
   nothing, file no issue.
   ```

3. Run it once by hand with `/schedule run` and read the issue it files.
   `/schedule list` shows it; claude.ai/code/routines pauses or deletes it.

### The network setting

The scheduled run reaches only the sites its **cloud environment** allows
(a cloud environment is the sandbox the run works in, with its own list of
permitted sites). The default, called **Limited**, allows package
registries, GitHub and a few cloud services, which leaves out about half
the watch list: the video channels, arXiv, and the Antigravity, MCP and
Codex pages. The first scheduled run found this (issue 360). The setting
lives on your claude.ai account, so it is changed in the browser, once:

1. Go to claude.ai/code/routines, click the lookout's task, open the menu
   beside its name and choose **Edit**.
2. Find the **Cloud environment** row, below **Trigger** or under
   **Advanced settings > General**. Hover over the environment in the list
   and click the settings icon on its right.
3. Under **Network access**, keep **Limited** and leave **Allow package
   managers** ticked: the run needs it to install the transcript package.
4. Enter these in **Allowed domains**, one per line (a leading `*.` covers
   every subdomain):

   ```
   youtube.com
   *.youtube.com
   arxiv.org
   *.arxiv.org
   antigravity.google
   modelcontextprotocol.io
   developers.openai.com
   ```

5. Click **Save changes**. The next run uses the new setting.

**Full** access would also work and allows every site. **Limited** with
this list is the safer choice: the lookout reads pages written by
strangers, and a short list limits where a run could send anything. An
environment that opens read-only is shared by your organization; an Owner
changes it under **Cloud environments** in the admin settings.

**GitHub is the exception.** A cloud run reaches `github.com` through a
gateway that serves only the repositories attached to the task, so no
entry in the list opens another repository's releases page or commits
feed. The lookout reads those sources from their files on
`raw.githubusercontent.com`, which the default list already allows; the
[watch list](watch.md#reading-from-the-scheduled-run) names the file for
each.

After changing the setting, run the task once by hand and read the issue it
files: its `UNRESOLVED` line names whatever is still out of reach. YouTube
refuses transcript requests from cloud machines even when the site itself
is allowed, so the video channels are read from your own computer instead
(next section).

Twice a week is enough: a changelog gains a handful of entries in three
days, and a report that arrives more often is a report nobody reads. A
centre that wants another cadence changes the schedule line.

**Check it is still scheduled.** Claude Code 2.1.329 (19 November 2026)
changed how saved scheduled tasks are stored: most saved by earlier versions
need scheduling again. The lookout's first run found this, which is why it
is written here. When a report has not arrived for a week, `/schedule list`
or claude.ai/code/routines shows whether the task still exists; if not,
create it again. The same applies to the reconcile routine.

## Video from your own computer

YouTube answers the scheduled run's request for a channel's list of uploads
but refuses its request for a transcript (seen on 2026-11-26: every one was
sent to a bot check). The scheduled run therefore lists the uploads and
leaves the transcripts to `/murmurent-lookout-videos`, a skill you run on
your own computer. It finds the newest lookout issue, lists what each
channel uploaded since that issue, reads the relevant uploads by their
transcripts, has the lookout judge them here, and adds what it found to the
issue as a comment. `/murmurent-lookout-videos dry-run` shows the comment
without posting it.

**When YouTube refuses your computer too.** A home connection is often
refused as well. Name a server of yours that YouTube does answer, once, in
the `env` block of `~/.claude/settings.json`:

```json
"MURMURENT_LOOKOUT_VIA": "<ssh host>"
```

The video script then sends itself over ssh to that server for the
transcripts this computer could not get, and the server sends back the text.
The server needs only `uv`; nothing is installed there and nothing of
murmurent is read. Only an 11-character video id is ever sent. The judging
stays on your computer, which is why this is safe for a server that holds
lab data, where letting the cloud run log in to it would not be.

**On a timer.** In the Claude desktop app, a local scheduled task runs the
skill for you, on this computer, while it is awake and the app is open:

1. Open **Scheduled** in the sidebar and choose **New task** (or ask a
   session to create one).
2. Folder: your murmurent repository. Prompt: `/murmurent-lookout-videos`.
3. Schedule: Monday and Thursday mornings, an hour or two after the
   scheduled lookout, so its issue exists. If it does not yet, the comment
   goes on the newest lookout issue and says which.
4. Run it once by hand and read the comment it adds. Nobody is there to
   approve a prompt on a timed run, so check it ran through.

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
- **The cadence**: edit the task with `/schedule update` or on claude.ai/code/routines.
