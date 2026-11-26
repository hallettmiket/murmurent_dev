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
