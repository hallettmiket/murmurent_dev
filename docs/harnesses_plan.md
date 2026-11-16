# Plan: more than one harness

This is the implementation plan for the `harnesses` branch. It turns the
design sketch in [`harnesses.md`](harnesses.md) into ordered, testable steps.
The first harness added is Google Antigravity. The design is written so that
the third and fourth (Faraday's OpenCode and Qwen Code, running open models on
the lab server) are two more profile files, not a second design.

A **harness** is the program around a model that gives it tools, rules and
memory. Claude Code is the one murmurent has run on until now. A **model** is
what the harness talks to (Opus, Gemini, Qwen). A **place** is where the model
runs and where the conversation is stored (Anthropic's cloud, Google's cloud, a
lab server). The plan keeps these three apart throughout, because any pairing
can occur and data sensitivity depends on the place alone.

## Why a branch

Both of the PI's installs, the laptop and biodatsci, run murmurent from a
checkout of `murmurent_dev`, and members install the release built from its
`main`. Everything here lands on the long-lived branch `harnesses`, cut from
`main` at `de17fdf` on 2026-11-16. The branch is merged into `main` once, when
phase 3 below is done and a second person has used it for a week. Until then:

- `main` keeps receiving ordinary work and is merged into `harnesses` weekly
  (`git merge main`, never a rebase, so the branch's history stays readable).
- Nothing on the branch changes how Claude Code is installed. A member who
  never runs `murmurent install --harness antigravity` sees no difference,
  before or after the merge.
- Every phase ends in a state where the whole test suite passes and the
  branch could be merged, so the merge date is a choice, not a cliff.

## Goals and non-goals

Goals, in the order they are built:

1. The commons (rules, skills, agents, MCP servers, hooks) load into a second
   harness from one source, by one command, with no hand-edited copies.
2. The data-governance hooks hold in that harness: a session in Antigravity
   cannot write under `immutable/` or delete under `append_only/`.
3. A routing table in lab policy says which harness, which model and which
   place take which kind of task, and refuses a route that a project's
   sensitivity forbids.
4. Every harness's sessions are visible to murmurent in one record format, so
   the session record in the vault, the Slack notes and the future nightly
   review treat them alike.

Non-goals on this branch:

- No learned routing. The table is written by people and reviewed by the PI.
- No nightly review job. The branch delivers the record it would read.
- No Faraday profiles. They are written when Faraday is ready, against the
  profile interface this branch fixes.
- No change to what Claude Code sessions do today.

## The five design rules

Each later section follows from these. They are restated here so a reviewer
can check a change against them without reading the sketch.

1. **A harness is a profile, as a machine is.** `core/machine_policy.py` has
   three profiles that each answer the same three questions, and a new kind of
   machine is one new class. `core/harness_policy.py` does the same for
   harnesses: one class per harness, each answering the same fixed questions.
2. **Harness, model and place are three columns.** No field of any table or
   record holds two of them at once.
3. **One source, rendered, never hand-edited.** Agents, rules, skills and
   hook logic live where they live today. `murmurent install --harness` renders
   them into the harness's own paths and overwrites them on every run.
4. **The governance line sits below the harnesses.** Hooks are the first
   warning. The perimeter is the data root's own permissions and the CLI's
   own refusals, which hold whatever harness a session runs in.
5. **One event record.** Murmurent reads one normalised event, produced by a
   reader per profile. Nothing downstream knows a harness's transcript format.
6. **No harness is required, Claude Code included.** Which harnesses an
   institution runs is its own choice: one, two or all. The lab says which
   it allows; each machine says which it has. Murmurent must install, run and
   report with any one of them alone, and nothing in it may assume
   `~/.claude/` exists. Claude Code stays the first profile, not the
   required one.

## Architecture

### `core/harness_policy.py`: the profile

```python
@dataclass(frozen=True)
class Harness:
    name: str            # claude_code | antigravity | antigravity_cli | opencode | qwen_code
    description: str
    place: str           # anthropic_cloud | google_personal | google_cloud | lab_server
    models: tuple[str, ...]   # what it can run today; checked at install, never trusted
    hooks_can_deny: bool      # has a pre-tool hook that can refuse a call
    headless: str | None      # the command that runs one prompt and exits, or None

class Profile:
    """One class per harness. Every method is a pure function of paths and
    text; nothing here talks to a network."""
    def install_paths(self, home: Path) -> InstallPaths: ...   # where rules, skills, agents, MCP, hooks go
    def render_rules(self, rules: list[Rule]) -> list[RenderedFile]: ...
    def render_agents(self, agents: list[Agent]) -> list[RenderedFile]: ...
    def mcp_config(self, registrations: dict) -> RenderedFile: ...
    def hook_config(self, module: str) -> RenderedFile: ...
    def headless_command(self, prompt: str, model: str, cwd: Path) -> list[str] | None: ...
    def transcript_stores(self, home: Path) -> list[TranscriptStore]: ...
    def read_events(self, path: Path) -> Iterator[Event]: ...
```

`PROFILES: dict[str, Profile]` holds `claude_code` (what `install_cmd.py`
does today, moved behind the interface and unchanged in effect) and
`antigravity`. The lab may override a profile's facts in
`policy/harnesses.yaml` of the lab records repository, exactly as
`policy/machines.yaml` overrides a machine profile: a value the lab leaves out
comes from the profile, a wrong value is reported and the default kept.

### The neutral hook event

Today each hook reads Claude Code's payload directly. Phase 2 introduces one
shape every hook reads instead:

```python
@dataclass(frozen=True)
class ToolEvent:
    harness: str
    session: str
    cwd: str
    tool: str            # murmurent's own vocabulary: shell | write | edit | read | notebook | agent | other
    command: str         # the shell line, for tool == shell
    path: str            # the file, for write | edit | read
    content: str         # new content, for write | edit
    raw: dict            # the harness's own payload, untouched
```

A profile has `to_event(payload) -> ToolEvent` and `from_decision(decision)
-> dict`. The hook modules keep their logic and lose their parsing. The Claude
Code adapter is the identity of today's behaviour, and the existing hook tests
run through it unchanged, which is how phase 2 proves it broke nothing.

### The event record

One jsonl row per tool call or prompt, written by the `audit` hook today for
Claude Code only, generalised:

```
{"t": "2026-11-16T15:02:11Z", "harness": "antigravity", "model": "gemini-4-argon",
 "place": "google_personal", "session": "…", "project": "coin_seq", "repo": "coin_seq",
 "tool": "shell", "summary": "murmurent machines load", "decision": "allow", "hook": ""}
```

Written live by the audit hook where the harness has a post-tool hook, and
reconstructed afterwards by `read_events` from the harness's own transcript
where it does not. `murmurent sessions` (new, read-only) lists yesterday's
sessions across harnesses from this record. The session record in the vault
(`hooks/session_log.py`) and the agents log line at session start both carry
`harness` and `model` from phase 2 on.

### The routing table

`policy/models.yaml` in the lab records repository, read by
`core/route_policy.py` with the same loader pattern as machines:

```yaml
routes:
  software_build:
    harness: claude_code
    model: claude-opus-5-5
    place: anthropic_cloud
    data: [standard, restricted, protected]
    why: governance hooks installed; vendor terms accepted for the lab
  literature_scan:
    harness: antigravity_cli
    model: gemini-4-argon
    place: google_personal
    data: [standard]
    agent: bookworm
    why: cheap long-context reading of public text
```

`murmurent route <task-kind> [--project <name>]` prints the row, or `no
route: <kind>` and the kinds that exist. With `--project`, it refuses a row
whose `data` list does not include the project's sensitivity, with the reason.
`place` is the field the refusal reads. The `data` list is the one field that
is not documentation.

## Choosing harnesses

Rule 6 has two layers, like the machines file:

- **The lab's choice**, in `policy/harnesses.yaml`: an `enabled:` list of
  the harnesses this institution allows, with the overrides it makes. A
  harness not in the list is shown by `murmurent harness list` as "not
  allowed here" and refused by `murmurent install --harness` and by the
  routing table. No list means every profile is allowed.
- **The machine's choice**, in `~/.murmurent/config.yaml` under `harnesses:`,
  written by `murmurent install --harness <name>` (repeatable) and changed by
  `murmurent harness enable <name>` and `disable <name>`. A plain
  `murmurent install` with nothing chosen installs into every allowed harness
  it finds on the machine (`claude` on the path, the Antigravity app folder,
  and so on), prints what it found, and installs into none it does not find.
  It never asks for a harness that is absent.

Everything that today reaches for `~/.claude/` goes through the chosen
profiles instead. On 2026-11-16 that is 40 source files (20 in `core/`, 7 in
`commands/`, 5 in `hooks/`, 4 in the dashboard, 3 in `mcp/`, plus
`scripts/setup.sh`), and the inventory of them is the first task of
phase 1. Each falls into one of three kinds:

| Kind | Examples | What happens to it |
|---|---|---|
| Install paths: where agents, rules, skills and settings are linked | `scripts/setup.sh`, `install_cmd`, `repo adopt` and `repo upgrade` (the `.claude/agents` links in each repository), `doctor` | Replaced by `Profile.install_paths` over the chosen profiles; a repository is adopted for each chosen harness |
| Session state: where the harness keeps transcripts, the audit log, the agents log | `hooks/audit.py`, `hooks/session_log.py`, the dashboard's agent pane, `project_cc_init` | Replaced by the event record of phase 4 and `Profile.transcript_stores` |
| The harness as a program: running `claude`, reading `~/.claude.json` | the launcher, `prompt_send`, the remote install | Replaced by `Profile.headless_command` and the routing table |

Two things stay Claude Code's for now and are said so in the docs: the
training movies, which show one harness, and the `teacher` modes, which
dispatch Claude Code subagents. Both get an entry in the inventory with
"later" beside them rather than silently staying coupled.

Acceptance for rule 6 is a test added in phase 1 and kept for the life of
the branch: with `harnesses: [antigravity]` on a machine that has no
`~/.claude/` at all, `murmurent install`, `murmurent harness list`,
`murmurent doctor` and `murmurent route` all run and exit 0.

## Phases

Each phase is one or more pull requests against `harnesses`, each with its
tests, and ends with `pytest` green and `mkdocs build --strict` clean.

### Phase 0: the branch and the interface (small)

Done on 2026-11-16: the branch, and the first PR with the rest.

- [x] Branch `harnesses` from `main`, worktree, `docs/harnesses.md` merged in.
- [x] `core/harness_policy.py` with `Harness`, `Profile`, `ToolEvent`,
      `Event`, `TranscriptStore` and `PROFILES` holding only `claude_code`.
- [x] Move the body of `install_cmd.py` (hook and MCP registration into
      `~/.claude/settings.json` and `~/.claude.json`) behind
      `PROFILES["claude_code"]`. `murmurent install --hooks` keeps its name,
      output and effect. Its existing tests pass unchanged.
- [x] `murmurent harness` (new group): `murmurent harness list` prints each
      profile, whether it is installed on this machine (its config paths
      exist), its place and whether its hooks can deny. Read-only.
- [x] `docs/harnesses.md` and this plan in the mkdocs nav under "The machines
      you can reach".

Acceptance: a fresh clone on the branch installs Claude Code exactly as
`main` does, byte for byte in `settings.json`, proven by a test that renders
both and compares.

### Phase 1: the commons load into Antigravity (medium)

- [ ] The inventory of rule 6: every place the code reaches for `~/.claude/`
      or runs `claude`, listed in `docs/harnesses.md` with its kind from the
      table above and the phase that moves it behind a profile.
- [ ] `policy/harnesses.yaml` gains `enabled:`; `~/.murmurent/config.yaml`
      gains `harnesses:`; `murmurent harness enable|disable`; `murmurent
      install` installs into the chosen harnesses only, and with none chosen
      into every allowed one it finds on the machine.
- [ ] `murmurent doctor` checks each chosen harness and no other, so a
      machine without Claude Code is not told to install it.
- [ ] `AntigravityProfile`: paths under `~/.gemini/config/` (rules, skills,
      agents, `mcp_config.json`, `hooks.json`) from the sketch, each with the
      documentation page it was read from in a comment and the date.
- [ ] `render_rules`: each of `rules/*.md` and `rules/local/*.md` becomes
      `~/.gemini/config/rules/murmurent_<name>.md` with a front matter of
      `trigger: always_on`; `oracle_schema.md` gets `model_decision` and a
      one-line description. `output_styles/plain_english.md` becomes
      `murmurent_voice.md`. A size check refuses to render past Antigravity's
      per-file limit and warns past the shared budget, both read from the
      profile's constants, not hard-coded in the renderer.
- [ ] `render_agents`: each of `agents/*.md` becomes a subagent file with the
      `tools` line rewritten through a vocabulary map in the profile and
      unknown fields dropped, listed in the install output.
- [ ] Skills: links from `~/.gemini/config/skills/<name>` to `skills/<name>`.
      The installer prints which skills carry `disable-model-invocation`,
      since Antigravity ignores it, and asks the PI whether to link them.
- [ ] `mcp_config`: the four `MCP_REGISTRATIONS` merged under `mcpServers`,
      other servers left alone, a `murmurent-*` allow rule printed for the
      PI to add by hand (permissions files are never written by murmurent).
- [ ] `murmurent install --harness antigravity`: calls the profile's renderers
      in order, prints every file written, and prints the data-handling
      warning from the sketch (fact 3) at the end, every time.
- [ ] `murmurent install --harness antigravity --dry-run`: the same, writing
      nothing.
- [ ] Tests render into a temporary home and compare against fixtures;
      Antigravity itself is never run in tests.

Acceptance: on the PI's Mac, after the install, an Antigravity conversation in
a murmurent-ready repository sees the voice rules, can call `oracle_search`
through MCP, and can run `/murmurent-machines`. Checked by hand once and
recorded in `docs/harnesses.md` with the date.

### Phase 2: the governance hooks hold in Antigravity (medium, the one that matters)

- [ ] `ToolEvent` adapters: `claude_code.to_event` and `antigravity.to_event`,
      the latter mapping `run_command` to `shell` and `CommandLine` to
      `command`, `write_to_file` and the two `replace_*` tools to `write` and
      `edit`, `view_file` to `read`. Unknown tools map to `other` and are
      allowed (the hooks are permissive by design, as today).
- [ ] `raw_guard`, `protected_paths` and `phi_check` read a `ToolEvent`
      instead of the raw payload. Their tests run twice, once through each
      adapter, from the same fixtures.
- [ ] `hooks/adapter.py`: the one entry point Antigravity's `hooks.json`
      calls (`python -m murmurent.hooks.adapter --harness antigravity`),
      which reads stdin, builds the event, runs the chain, and writes the
      decision in Antigravity's shape.
- [ ] `hook_config` for Antigravity writes a `PreToolUse` entry with the
      matcher from the sketch and the adapter command, plus `PostToolUse` for
      the audit record and `SessionStart` for context injection.
- [ ] The audit record gains `harness`, `model` and `place`. The agents log
      gains one line at session start naming them. `session_log` gets an
      Antigravity path through `PreInvocation`.
- [ ] A test harness script, `scripts/harness_smoke.sh`, feeds the adapter the
      recorded Antigravity payloads for a write under `immutable/` and a
      delete under `append_only/` and asserts a deny, so the guard is checked
      on every machine at install time without running Antigravity.

Acceptance: in a real Antigravity conversation on the PI's Mac, a write under
`immutable/` is refused with murmurent's own message, and the audit record
shows the refusal with `harness: antigravity`. Recorded in `harnesses.md`.

Also in this phase, the perimeter below the hooks, which is not Antigravity
work but is what rule 4 requires:

- [ ] `murmurent security acl check <data-root>` (read-only) reports whether
      `immutable/` is writable by anyone but its owner and whether
      `append_only/` allows delete, so the PI sees the filesystem state the
      hooks assume. Setting the permissions stays a human step on the server.

### Phase 3: the routing table (small)

- [ ] `core/route_policy.py`: loader, `Route` dataclass, validation that
      `harness` names a profile, `place` matches the profile's place, and
      `data` holds only the three tiers. Problems reported, defaults kept.
- [ ] `templates/models.yaml`: the two-row example above, every line
      explained.
- [ ] `murmurent route <kind> [--project]`: prints the row; refuses on
      sensitivity; `--json`; exit 0 always, as `machines` does.
- [ ] `murmurent route --command <kind> "<prompt>"`: prints the headless
      command line the profile builds (`claude -p …`, `agy -p … --model …`)
      and does not run it. Running is a later branch.
- [ ] The millwright gains operation 12, "which harness takes this": runs
      `murmurent route` and reports the row and the refusal reason, never
      choosing on its own.

Acceptance: `murmurent route literature_scan --project <a protected project>`
refuses with the reason in one line; the same for a standard project prints
the row.

### Phase 4: one record for every harness (medium)

- [ ] `TranscriptStore` for Claude Code (`~/.claude/projects/<slug>/*.jsonl`)
      and `read_events` for its format, tested on a recorded session.
- [ ] The same for Antigravity, written only once a real
      `transcript.jsonl` exists on the PI's Mac to read; until then
      `murmurent sessions` reports "antigravity: N conversations in the
      index, transcripts not read", from `conversation_summaries.db`.
- [ ] `murmurent sessions [--since <date>]`: one row per session across
      harnesses: when, harness, model, place, project, tool calls, refusals.
      Read-only, `--json`.
- [ ] The dashboard's agent pane reads this record instead of only the
      agents log, so a session in Antigravity appears beside one in Claude
      Code.

Acceptance: after a morning of mixed use, `murmurent sessions` lists both
kinds, and the counts match what each harness's own interface shows.

### Phase 5: merge and release

- [ ] A second member uses the Antigravity install for a week on their own
      machine and reports in the project channel.
- [ ] `CHANGELOG.md` entry under Unreleased, the version bumped at the
      release that follows.
- [ ] `docs/setup.md` gains a section "A second harness" pointing at
      `harnesses.md`; `docs/cli_manual.md` gains `harness`, `route` and
      `sessions`.
- [ ] Merge `harnesses` into `main` by pull request; the PI merges.

## Tests, at every phase

- Profiles are pure: every renderer and adapter is tested against fixtures
  in a temporary home, with no harness installed and no network.
- The Claude Code profile is proven identical to today's behaviour by a
  rendering comparison test, kept for the life of the branch.
- Hook logic tests run through every adapter from the same fixtures, so a
  guard that holds in one harness holds in all.
- The whole suite (`pytest -q`, 3300 tests and growing) stays green at the
  end of every phase; a phase does not end on a skip.
- What cannot be tested without the real harness (phases 1, 2 and 4 each
  have one such item) is checked by hand on the PI's Mac and recorded in
  `harnesses.md` with the date and the version of Antigravity.

## Risks and what the plan does about them

| Risk | Where it bites | What the plan does |
|---|---|---|
| Google retains, reviews and trains on interactions under the personal sign-in | Any restricted or protected data in an Antigravity session | `data:` on every route, enforced by `murmurent route`; the install prints the warning every time; `phi_check` runs through the adapter; the PI decides on a Google Cloud sign-in before any non-standard project is routed |
| Governance hooks absent until phase 2 | Every Antigravity session from the install in phase 1 to the adapter in phase 2 | Phase 1's install prints that the hooks are not yet installed; the routing table carries no row for Antigravity until phase 2 is merged |
| Antigravity changes its paths, tool names or model list | Renderers and adapters silently write to the wrong place | Every path and name is a constant in the profile with its source and date; `murmurent harness list` checks the paths exist; model names are checked at install against the harness's own list, never trusted from the table |
| Skills lose `disable-model-invocation` | A skill meant to be typed is chosen by the model | The installer names those skills and asks; `murmurent-reset` is never linked into Antigravity |
| Two transcript formats, one unread | The record is half of what the lab did | `murmurent sessions` says what it could not read rather than omitting it |
| Permissions live in Antigravity's own settings, which murmurent never writes | The code-free deny rules are not there | The installer prints the exact lines and `murmurent harness list` reports whether they are present |
| The branch drifts from `main` | A painful merge in phase 5 | Weekly merges of `main` into `harnesses`; every phase ends mergeable |

## Decisions the PI makes before each phase

1. Before phase 1: whether the Antigravity App on the Mac stays on the
   personal sign-in for the trial, with telemetry turned off in its
   settings, and which projects (standard only) it may be used in.
2. Before phase 2: whether to set the filesystem permissions on biodatsci's
   data root as `murmurent security acl check` reports, since that is the
   perimeter the hooks assume.
3. Before phase 3: the first two rows of `policy/models.yaml`, and the task
   kinds the lab will name.
4. Before phase 5: whether Faraday's two harnesses are the next branch, and
   whether a Google Cloud sign-in is worth its cost for restricted projects.

## What this plan does not decide

- The nightly review (the "dreaming" of the design note): it reads the event
  record from phase 4 and is its own branch.
- Running a route (`murmurent route --run`): the command line is built in
  phase 3 and run on a later branch, once the record from phase 4 can show
  what it did.
- Faraday. Its OpenCode and Qwen Code profiles are two files against the
  phase 0 interface, written when Faraday serves a model that a harness can
  reach, and their place is `lab_server`, which is what lets protected data
  through.
