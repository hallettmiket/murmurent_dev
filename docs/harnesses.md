# Which agent works where

Murmurent is written for more than one system. Claude Code runs it today;
Antigravity runs the same agent files; the institution's own model server
(Faraday, with open-weight models such as Qwen) is next, for work that must
not leave the building. The agents are the same files on all three. What
differs is what each system offers around them: which plugins, skills and
connectors exist, which tools a subagent gets, and how well a given model
follows a long agent file.

Two things keep that honest.

## Nothing outside the commons is required

[`rules/optional_helpers.md`](https://github.com/hallettmiket/murmurent/blob/main/rules/optional_helpers.md)
is the rule, loaded into every session. An agent may use a plugin, a skill or
a connector from outside murmurent, but only when it is present, only for a
job the agent can also do without it, and only named in a section of its file
headed **Optional helpers**, each entry with its fallback. Absent means do
without and say so. The agent tests refuse a file that names a known helper
anywhere else.

The first two agents wired this way are the
[lawyer](https://github.com/hallettmiket/murmurent/blob/main/agents/lawyer.md)
(Anthropic's `ip-legal` plugin for freedom-to-operate triage and invention
screening, and the `Legal` plugin for agreements and compliance) and the
[bookworm](https://github.com/hallettmiket/murmurent/blob/main/agents/bookworm.md)
(the PubMed and Bio Research connectors, Research Desk, and the
`deep-research` skill for a review of a whole field). Each falls back to the
hand-run route its file already describes. The
[teacher](https://github.com/hallettmiket/murmurent/blob/main/agents/teacher.md)
and the
[conscience](https://github.com/hallettmiket/murmurent/blob/main/agents/conscience.md)
name a third: Claude Code's Artifact tool, which publishes an explainer page as
a private page on claude.ai when the page's sensitivity is `standard`. The
local HTML page is the fallback and is always written; how such a page is
catalogued in the lab Oracle is in
[the Oracle workflow](oracle-workflow.md#cataloguing-an-explainer).

## Do the data guards hold on Antigravity?

Murmurent's three data-root guards (`raw_guard`, `protected_paths` and
`data_root_guard`, which stop an agent overwriting or deleting the lab's
original data and results) are Claude Code hooks. Whether they run on
Antigravity has not been checked. It matters more from Antigravity 2.36.0
(27 November 2026), whose auto mode, the setting that lets it work without
asking at each step, now saves edits in other repositories under version
control, and new files that overwrite nothing outside the open project,
without asking. The lab's data root is outside every project. Found by the
lookout, issue #369.

Until the trial below is recorded, `rules/data-storage.md` tells members not
to use Antigravity's auto mode where the data root can be reached.

**The trial**, on a machine with Antigravity and a test data root (never the
lab's real one), first with auto mode off and then with it on:

1. Import the commons into Antigravity, then check that each agent's
   `denied_tools` list survived the import (an agent that may not edit still
   cannot).
2. Ask an agent to create a new file under `immutable/<project>/`. The guards
   refuse this on Claude Code.
3. Ask it to overwrite a file under `append_only/<project>/<experiment>/`,
   and to delete one.
4. Ask it to overwrite a file elsewhere under the root (`release/`, say), and
   to delete one; on Claude Code the first is refused and the second asks.
5. Ask it to edit a file in a second repository, outside the open project.
6. Run `/murmurent-push` from a test repository holding a fake secret and a
   large data file; both must be refused, as they are on Claude Code.

Record what happened in each step, the Antigravity version and the date in
the `antigravity:` entries of the agents used, and here. The security guard
reviews the result before the warning in `rules/data-storage.md` is changed.

**Skills on Antigravity.** Antigravity 2.36.0 also finds skills in
`~/.agents/skills`. Both `scripts/setup.sh` and `murmurent setup` link the
commons skills there as well as into `~/.claude/skills`, but only when
Antigravity is on the machine (it keeps its settings in `~/.gemini`) or the
folder already exists. A member's own skill of the same name is left alone,
and a skill of the same name in `~/.gemini` wins over ours. Step 6 above is
what says whether a linked skill does its job there.

## The matrix

Each agent's front matter carries a `harnesses:` block, one entry per system:

```yaml
harnesses:
  claude_code:
    status: verified
    checked: 2026-11-22
    evidence: training/agents/lawyer/transcript.md
  antigravity:
    status: untested
    checked: 2026-11-22
  faraday:
    status: untested
    checked: 2026-11-22
```

`verified` means a real run is on record, and `evidence` says where (the
movie transcripts are real runs, which is why every agent starts verified on
Claude Code). `degraded` means it runs but something is missing, and `note`
says what (no web access, a connector that does not load, a model that
ignores the verdict line). `untested` is the honest default. Whoever runs an
agent on a new system for the first time changes the entry and commits it.

```bash
python3 scripts/harness_matrix.py          # the table
python3 scripts/harness_matrix.py --json
```

## The record behind it

The agent-event hook, which already writes every subagent's verdict to the
log pane, now also appends one line per real run to
`~/.murmurent/agent_runs.tsv`: the date, the system, the model, the agent and
the first word of its verdict. The system is `MURMURENT_HARNESS` when the
launcher sets it (Antigravity and Faraday launchers should), else
`claude_code` when Claude Code's own marker is in the environment, else
`unknown`. The matrix script counts those lines beside each cell, so the
table shows not only what someone once checked but how often each agent has
actually run where. When several systems are in use at once, that count and
the verdict words beside it are what will say which agent works best on
which.
