# A second harness: what Google Antigravity can take from the commons

A **harness** is the program around a model that gives it tools, rules and
memory: Claude Code is one, Google Antigravity is another. Murmurent so far
runs on Claude Code alone. This note records what Antigravity offers today,
read from its own documentation and from its installation on one Mac, maps
the shared murmurent parts (agents, rules, skills, hooks, MCP servers, the
command line) onto it, and sketches the smallest first build. It is a design
sketch; nothing in it is built.

Read on 2026-11-16 from the Antigravity App 2.32.1 installed at
`/Applications/Antigravity.app`, its data folder `~/.gemini/antigravity/`, the
documentation it ships inside that folder (`builtin/skills/antigravity_guide/`
and `builtin/skills/agy-customizations/docs/`) and the public pages under
`https://antigravity.google/docs/`. Antigravity changes quickly: check the
dates before relying on a line below. Anything not read from a source is marked
**unconfirmed**.

## The three facts that most change the design

1. **Antigravity has hooks that can refuse a tool call before it runs**, in the
   same shape as Claude Code's: a `PreToolUse` hook reads the tool call as JSON
   on standard input and answers `{"decision": "deny"}`. The data-governance
   hooks can therefore be carried over, with one translation of tool names.
   Source: `docs/hooks` and the shipped `agy-customizations/docs/hooks.md`.
2. **Antigravity is not one model.** The model list on 2026-11-16 holds Gemini
   4 (Carbon, Argon, Hydrogen), Gemini 3.x Flash and Pro, Claude Sonnet 5.5
   and Opus 5.5, and GPT-OSS-120b, each gated by subscription tier. A routing
   table must name a model, not a harness, since the same harness can run a
   Claude model. Source: `docs/models`.
3. **Under a personal Google account, Google may read and train on every
   interaction unless telemetry is turned off, and Google staff may review
   them.** The terms say so in Section 5. Only a Google Cloud (enterprise)
   sign-in runs under the Google Cloud terms. A paid Google AI Pro or Ultra
   subscription does not change this. Source: `https://antigravity.google/terms`,
   `docs/enterprise`.

## 1. What Antigravity offers today

### Surfaces, and which one is installed here

Antigravity has four surfaces: the **App** (a desktop program that runs agents
outside any editor; its documentation calls it "Antigravity 2.0"), the **IDE**
(an editor built on VS Code), the **CLI** (`agy`, a terminal program), and a
**Python SDK** (`pip install google-antigravity`). Each keeps its own data
folder under `~/.gemini/`: `antigravity/` for the App, `antigravity-cli/` for
the CLI, `antigravity-ide/` for the IDE. All four share one set of
customisations under `~/.gemini/config/`. Source: shipped `antigravity_guide`,
`docs/hooks`.

On this Mac only the **App** is installed (bundle version 2.32.1). There is no
`agy` on the path and no `~/.gemini/antigravity-cli/` folder. The App has been
opened but has run no conversation yet: `conversation_summaries.db` holds zero
rows and `brain/` is empty.

| Question | Answer | Source |
|---|---|---|
| Command-line or headless mode | Yes, the CLI: `agy -p "<prompt>"` runs one prompt and exits, with `--output-format json` or `stream-json`, `--json-schema` for structured output, `--model` and `--effort`. The CLI is a separate install (`curl -fsSL https://antigravity.google/cli/install.sh \| bash`, binary at `~/.local/bin/agy`). The Python SDK is a second headless route. | `docs/cli/reference`, `docs/getting-started?tab=cli`, shipped `references/sdk.md` |
| Gemini CLI | Antigravity CLI is Gemini CLI's upgrade path and reads the same `~/.gemini/GEMINI.md`; `agy plugin import gemini` converts Gemini CLI extensions and commands. Gemini CLI is not installed here. | `docs/cli/gcli-migration` |
| Models | Gemini 4 Carbon (Ultra, Enterprise), Argon (Pro, Ultra, Enterprise), Hydrogen (all); Gemini 3.8 Flash (all); Gemini 3.7, 3.6 Flash and 3.1 Pro (Enterprise); Claude Sonnet 5.5 and Opus 5.5 (paid Pro, Ultra, Enterprise); Claude 4.6 and GPT-OSS-120b (removed 2026-11-18). Background models (image generation, indexing) are Gemini and cannot be changed. The CLI can also run against a `GEMINI_API_KEY` directly, Gemini models only. | `docs/models`, `docs/install` |
| Project rules | `AGENTS.md` or `GEMINI.md` in any folder from the working folder up to the repository root, always on, no front matter. `.agents/rules/*.md` (top level only), each needing a front-matter `trigger` of `always_on`, `model_decision`, `glob` or `manual`. Global: `~/.gemini/GEMINI.md`, `~/.gemini/config/GEMINI.md`, `~/.gemini/config/rules/*.md`. 24,000 bytes per file; 20,000 tokens for all always-on rules together, beyond which the largest are reduced to a path the agent reads on demand. | `docs/rules`, shipped `docs/rules.md` |
| "Knowledge" items | **Unconfirmed.** Neither the shipped guide nor the public pages read today describe a knowledge store; the current customisation types are rules, skills, plugins, hooks, MCP servers and subagents. | shipped `agy-customizations/SKILL.md` |
| Agent Skills standard | Yes. `.agents/skills/<name>/SKILL.md` in the workspace, `~/.gemini/config/skills/` globally; the page links agentskills.io. Only `name` and `description` front matter are honoured. A skill is loaded by its description, not by a slash command. | `docs/skills` |
| Hooks that refuse a tool call | Yes. `hooks.json` in `.agents/` or `~/.gemini/config/`; events `SessionStart`, `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`. A `PreToolUse` command gets the call on standard input (`toolCall.name`, `toolCall.args`, camel-case keys) and answers `decision: allow / deny / ask / force_ask / auto_approve / deny_unless_prior_grant`. Tool names differ from Claude Code's: `run_command`, `write_to_file`, `replace_file_content`, `multi_replace_file_content`, `view_file`. Only shell-command hooks; they run synchronously. | `docs/hooks`, shipped `docs/hooks.md` |
| Permission rules | A second guard, without code: `deny` lists of `write_file(<folder>)`, `command(<regex>)`, `mcp(<server>/<tool>)`, stored in the CLI's `settings.json` or the App's settings. Deny beats ask beats allow; a folder matches recursively. Whether a write deny also blocks a delete through the shell is **unconfirmed**. | `docs/permissions` |
| MCP servers | `mcpServers` map in `~/.gemini/config/mcp_config.json` (global), `<workspace>/.agents/mcp_config.json` (one project), or inside a plugin. Stdio: `command`, `args`, `env`, `cwd`. Remote: `serverUrl` (Streamable HTTP only). MCP tools run in "ask" mode until a permission rule allows them. On this Mac the global file exists and is empty. | `docs/mcp`, `~/.gemini/config/mcp_config.json` |
| Subagents | `.agents/agents/<name>.md` or `~/.gemini/config/agents/<name>.md`: front matter `name`, `description`, `tools`, `model` (`inherit`, `flash` or `pro` only), `mcpServers`, `skills`; the body is the system prompt. The same shape as `agents/*.md` here. | `docs/subagents` |
| Session transcripts on disk | `<data folder>/brain/<conversationId>/.system_generated/logs/transcript.jsonl`, where the data folder is `~/.gemini/antigravity/` (App), `antigravity-cli/` or `antigravity-ide/`. Every hook receives the path as `transcriptPath`. A search index of all conversations sits beside it in `conversation_summaries.db` (SQLite, full-text). The record format inside the file is **unconfirmed** (no conversation has run here yet). | `docs/hooks`, this Mac |
| Data handling | Personal account (free, Plus, Pro, Ultra): Google records "Interactions" (user data, interaction data, metadata, feedback) and uses them to "evaluate, develop, and improve" its products and machine-learning technology; employees and contractors may review them; the terms tell you not to submit confidential information. Telemetry can be turned off in settings, after which Google still keeps what it needs to run the service and keep it safe. Deletion is by email to antigravity-support@google.com. A Claude model adds Anthropic's terms. Google Cloud sign-in: logs go to the customer's own project under the Google Cloud terms, with `us` or `eu` residency and VPC Service Controls; whether Cloud data is excluded from training is **unconfirmed** from the page read. | `https://antigravity.google/terms` (Sections 3, 5, 8), `docs/enterprise` |

The App on this Mac is signed in with a personal account (its state file
records the consumer onboarding, not a Cloud project). Which telemetry setting
it has was not read; the setting lives in the App's own interface, not in a
file this note could inspect. Treat it as on until checked.

## 2. The commons, part by part

| Part of the commons | In Antigravity | What to do |
|---|---|---|
| **Agents** (`agents/*.md`) | Subagents in `~/.gemini/config/agents/<name>.md`, same front-matter-plus-prompt shape. Differences: `tools` must list Antigravity's tool names; `model` is a tier, not a model name; the headline-first rule and the `Aloud:` line work unchanged since they are prose. | **Generated translation**: copy each agent, rewrite the `tools` line, drop fields Antigravity does not know. |
| **Rules** (`rules/*.md`, `rules/local/*.md`) | A rules folder with front matter, or one always-on `GEMINI.md`. The six shared rules total well under 24,000 bytes each. Claude Code loads them from `~/.claude/rules/` by symbolic link; Antigravity reads only its own paths. | **Generated translation**: render each rule into `~/.gemini/config/rules/<name>.md` with `trigger: always_on` prepended (or concatenate into `~/.gemini/config/GEMINI.md`). Mind the 20,000-token shared budget: `voice.md` and `headline_first.md` are always-on; `oracle_schema.md` can be `model_decision` with a description. |
| **Skills** (`skills/*/SKILL.md`) | `~/.gemini/config/skills/<name>/`, Agent Skills standard. `disable-model-invocation`, `allowed-tools` and `argument-hint` are ignored, so a skill meant to be typed, never chosen by the model (`murmurent-machines`, `murmurent-reset`), can be picked by the model on its own. `$ARGUMENTS` is **unconfirmed**. | **Loads as is** for the procedure; **review each** for the lost `disable-model-invocation` guard before linking. Linking the folder is enough. |
| **Hooks** (`src/murmurent/hooks/*.py`) | `hooks.json`, same stdin-to-stdout JSON contract, different tool names and camel-case keys (`toolCall.args.CommandLine` instead of `tool_input.command`). `raw_guard` and `protected_paths` are the ones that matter; `phi_check` (outgoing text), `session_log` (`UserPromptSubmit`, which Antigravity lacks; `PreInvocation` with `lastUserInput` is the nearest), `context_inject` (`SessionStart` with `injectSteps`). | **Generated translation**: one adapter module that maps an Antigravity payload onto the Claude Code shape and calls the existing hook, registered in `~/.gemini/config/hooks.json`. Add the `write_file(<data root>/immutable/)` permission deny as a second, code-free line of defence. Until the adapter exists, **the governance hooks are absent** in every Antigravity session. |
| **MCP servers** (`src/murmurent/mcp/*`) | `mcp_config.json`, stdio, same `command`/`args`/`env` keys as `~/.claude.json`. | **Loads as is**: write the four registrations into `~/.gemini/config/mcp_config.json`, plus `mcp(murmurent-*/\*)` allow rules so the tools do not prompt on every call. |
| **The `murmurent` CLI** | Any shell tool the agent may run. The slash skills that call it work once the skill is loaded. | **Loads as is**. The `command(murmurent)` allow rule saves a prompt per call. |
| **Output style** (`output_styles/plain_english.md`) | No output-style concept. | **Generated translation**: fold it into the rendered always-on rules. |
| **Session records** (`session_log` into the vault's `sessions/<date>/`) | No `UserPromptSubmit`. | **Translation** via `PreInvocation` (`lastUserInput`), or read `transcript.jsonl` afterwards. |

## 3. The smallest useful first build

### `murmurent install --harness antigravity`

Today `murmurent install --hooks` writes into Claude Code's `settings.json` and
`~/.claude.json`. The new flag writes the same facts into Antigravity's paths
and nothing else:

1. `~/.gemini/config/mcp_config.json`: merge the four `MCP_REGISTRATIONS`
   from `install_cmd.py` under `mcpServers`, same keys, leaving other servers
   alone.
2. `~/.gemini/config/rules/murmurent_<name>.md`: one file per shared rule and
   per `rules/local/` rule, the original text with a front matter of
   `trigger: always_on` (`oracle_schema.md`: `model_decision`), plus
   `murmurent_voice.md` holding the output style. Regenerated on every run, so
   the rules stay one source.
3. `~/.gemini/config/skills/<name>` and `~/.gemini/config/agents/<name>.md`:
   links to `skills/`, and translated copies of `agents/` with the `tools`
   line rewritten. First build may skip the agents.
4. `~/.gemini/config/hooks.json`: a `murmurent-governance` entry with
   `PreToolUse` matcher `run_command|write_to_file|replace_file_content|multi_replace_file_content`
   running `python -m murmurent.hooks.antigravity_adapter`, which reshapes
   the payload and calls `raw_guard` then `protected_paths`. The adapter is the
   one new piece of code.
5. Print what it wrote, and print the telemetry warning from fact 3 above.

Never touches `~/.gemini/antigravity-cli/settings.json` (permissions live
there and in the App's own settings; the build asks the PI to add the
`write_file` deny lines by hand and prints them).

### `policy/models.yaml` and `murmurent route`

A **routing table** says which harness and model takes which kind of task,
declared in the lab records repository beside `policy/machines.yaml`, read the
same way (`machine_policy.py` is the pattern: a profile fills in what the lab
does not say, a wrong value is reported and the default kept).

```yaml
# policy/models.yaml: who takes which kind of task. Two rows to start.
routes:
  software_build:
    harness: claude_code            # claude_code | antigravity_app | antigravity_cli
    model: claude-opus-5-5
    data: [standard, restricted, protected]   # sensitivity tiers it may see
    why: governance hooks installed; vendor terms already accepted for the lab
  literature_scan:
    harness: antigravity_cli
    model: gemini-4-argon
    data: [standard]                # never restricted or protected: see risks
    agent: bookworm
    why: cheap long-context reading of public text; nothing of the lab's leaves
```

`murmurent route <task-kind>` prints the row, or `no route: <kind>` and the
kinds that exist. First build prints and nothing more: no session is started by
it. A second step can have it print the command line (`agy -p ... --model
...`, or `claude -p ...`). The sensitivity list is the one field that is not
decoration: `murmurent route` refuses to print an Antigravity row for a
project whose record says `protected` until the Cloud sign-in is confirmed.

### Reading both harnesses' transcripts

A nightly review reads what every session did yesterday (which rules were
loaded, which tool calls were refused, which data paths were touched). Claude
Code keeps one `.jsonl` per session under `~/.claude/projects/<folder slug>/`.
Antigravity keeps one `transcript.jsonl` per conversation under
`~/.gemini/antigravity/brain/<conversationId>/.system_generated/logs/` (and the
CLI under `antigravity-cli/`), with `conversation_summaries.db` as the index of
which conversation belongs to which workspace and when it last ran.

The review takes a list of **transcript stores**, one per installed harness,
each with a glob and a reader that yields `(time, session, tool, args,
decision)`. The Antigravity reader is written only once a real transcript
exists to read; its line format is unconfirmed today. Until then the review
reports "Antigravity: N conversations in the index, transcripts not read".

## 4. What is built, and how to use it

Phases 0 and 1 of [`harnesses_plan.md`](harnesses_plan.md) are on the
`harnesses` branch. A harness is a **profile** in
`src/murmurent/core/harness_policy.py`, one class per harness answering the
same questions; `harness_claude_code.py` and `harness_antigravity.py` are the
two so far.

### No harness is required

Which harnesses an institution runs is its own choice, and murmurent runs
with any one of them alone (rule 6 of the plan). Two layers decide:

- **The lab**: `enabled:` in `policy/harnesses.yaml` of the lab records
  repository lists the harnesses it allows. A harness outside the list is
  shown as "not allowed by the lab" and refused by `install` and `enable`.
  No list means every harness is allowed. The same file may change a
  harness's `place`, `models` or `description`; anything else is reported
  and the profile's value kept.
- **The machine**: `harnesses:` in `~/.murmurent/machine.yaml`, written by
  `murmurent harness enable <name>` or by `murmurent install --harness
  <name>`. With no choice made, murmurent acts on every allowed harness it
  finds on the machine (`claude` on the path or `~/.claude/`; the Antigravity
  app, its data folder or `agy` on the path) and says so.

```bash
murmurent harness list          # every harness: place, hooks can refuse, headless, chosen, state here
murmurent harness enable antigravity
murmurent harness disable claude_code   # the choice only; nothing is uninstalled
```

`murmurent doctor` checks the chosen harnesses and no other, so a machine
without Claude Code is never told to install it. A harness that is on the
machine but not chosen and without the commons is a warning, not a failure.

### `murmurent install --harness antigravity`

```bash
murmurent install --harness antigravity --dry-run   # what would be written
murmurent install --harness antigravity             # write it, and record the choice
```

It writes, under `~/.gemini/config/` (the folder the App, the IDE and the
CLI share), overwriting only what it wrote last time:

| What | Where | How |
|---|---|---|
| Rules (`rules/*.md`, `rules/local/*.md`), the output style, the commons overview | `rules/murmurent_<name>.md` | Each with a `trigger: always_on` front matter; `oracle_schema.md` gets `model_decision` with a sentence saying when to read it. A file over Antigravity's 24,000-byte limit is **skipped and named** rather than cut off (today: `CLAUDE.md`, 25 KB). The total is checked against the 20,000-token budget. |
| Skills | `skills/<name>` | Links to the commons. A skill marked `disable-model-invocation` (meant to be typed, never chosen by the model) is left out and named, since Antigravity ignores that guard; `--all-skills` links it anyway. |
| Agents | `agents/<name>.md` | A translated copy: `name` and `description` kept, `model: inherit`, the body (the prompt) unchanged. A `tools` line only when every required tool has a confirmed Antigravity name; today `Glob`, `Grep`, `WebFetch` and `WebSearch` do not, so every agent gets Antigravity's full set, and the report says so once. The fields Antigravity has no place for are listed once. |
| MCP servers | `mcp_config.json` | The four murmurent servers merged under `mcpServers`; every other server kept. |

| The governance hooks | `hooks.json` | A named hook, `murmurent-governance`, merged in beside the person's own: `PreToolUse` on every tool that can change a file, `PostToolUse` for the audit record, `SessionStart` for the project context and the agents-log line, `PreInvocation` for the session record. All four run `python -m murmurent.hooks.adapter --harness antigravity --event <name>`. |

The report ends with two notes to act on by hand (MCP tools run in ask
mode until a permission rule allows them; `murmurent harness smoke
antigravity` checks the hooks) and the data-handling warning, printed every
time.

### The governance hooks in another harness

Checked by hand on 2026-11-16, Antigravity App 2.32.1 on the PI's Mac: after
the install wrote `hooks.json`, a conversation asked to delete a file under
the data root's `immutable/` was refused with murmurent's own message.
Before that, running the hook command with an empty environment (as the App
runs it) had shown the guards could not see the data root; the command now
carries it (PR 329).

Phase 2. The three guards that protect the data root (`raw_guard`,
`protected_paths`, `phi_check`) are unchanged: they evaluate a tool call in
Claude Code's shape. What changed is that every harness's payload now becomes
one neutral **tool event** (shell, write, edit, notebook, read, agent, other)
through its profile's `to_event`, and that event is turned back into the shape
the guards read. So one guard serves every harness, and the same recorded
cases (`templates/hook_payloads/<harness>.json`) are proven to get the same
decisions through both adapters.

`murmurent.hooks.adapter` is the one entry point for a harness other than
Claude Code. For a `PreToolUse` call it runs the guards in order and answers
in the harness's shape: a deny is `{"decision": "deny", "reason": ...}`; for
allow it says `{"decision": "ask"}`, which hands the call to the harness's own
permission check, so the person's "always allow" choices stand and nothing is
widened (an explicit allow would auto-approve the call). Antigravity's
contract says `decision` is required: `{}`, which the App let pass, was an
unsupported decision to its command-line tool, which refused every call that
way on 2026-11-16. When the adapter cannot decide (unreadable input, a crash)
it gives that same neutral answer. It also writes the audit row
with the harness, the model and the place, the agents-log line at session
start, and the prompt into the vault's session record once per prompt. It
never raises: a guard that throws is treated as allow, and everything else
is skipped with the reason on stderr when `MURMURENT_HOOK_DEBUG=1`.

Antigravity's argument names are only partly confirmed (`CommandLine` is
documented; the file keys `TargetFile`, `AbsolutePath` and the rest come from
the tools' common lineage). The adapter therefore also takes the first
absolute path among a write's arguments, so a key it did not expect cannot
blind the guards; the recorded case "write under immutable with an
unexpected key name" proves it.

```bash
murmurent harness smoke antigravity   # every recorded case through the hooks, in a scratch data root
murmurent harness smoke claude_code   # the same cases through Claude Code's adapter
```

The Antigravity hook adapter runs under the Python that installed murmurent;
on a machine that runs murmurent from a development checkout, the hooks see
the branch that checkout has. **The perimeter below the hooks** is the
filesystem, which `murmurent security acl-check <data-root>` reads without
changing anything: whether `immutable/` is writable by anyone but its owner,
and whether `append_only/` lets a member add files but not delete another's
(the sticky bit). The fixes it prints are for the PI to run on the server.

A plain `murmurent install` with Antigravity chosen, or found and nothing
chosen, does the same after the Claude Code steps. `--hooks` alone keeps its
old meaning: Claude Code only.

### Checked by hand

2026-11-16, Antigravity App 2.32.1 on the PI's Mac, personal sign-in with
telemetry off (global settings, Account, "Enable Telemetry"). After
`murmurent install --harness antigravity` and the five permission grants
added once in the App's global settings, a conversation in a murmurent-ready
repository listed the rendered rules, searched the oracle over MCP and ran
`murmurent machines load`. Reported working by the PI.

Later the same day, the command-line tool (`agy` 1.5.9, installed that
afternoon) refused `murmurent machines load` with "tool call denied by
pre-tool hook". The adapter had answered `{}` for allow; the tool's contract
says `decision` is required, and it reads a missing one as a refusal. Fixed
by answering `ask` (above). The tool reads the same `~/.gemini/config/hooks.json`
as the App and picks up a rewrite of it without a restart.

### The routing table

Phase 3. `policy/models.yaml` in the lab records repository says which
harness, which model and which place take which kind of task, and for which
sensitivity tiers. `templates/models.yaml` is the commented example, with two
rows; the lab names the kinds its routines use. It is read the way the
machines and harnesses files are: a row with a harness murmurent does not
know (or the lab has not enabled), a place that is not where that harness
runs, or a data tier that does not exist is reported and dropped, and the
other rows stand. There are no built-in rows: a lab that has written none
has no routes, and the command says so.

```bash
murmurent route                                   # every route the lab declared
murmurent route literature_scan                   # the row, for the project of this folder
murmurent route literature_scan --project coin_seq
murmurent route literature_scan --command "find papers on DCIS"   # also the command line, not run
```

The `data:` list of a row is the one field that is not documentation. With
`--project` (or the project of the current folder), a route whose list does
not include the project's tier is **refused**, with the place named in the
reason, since the place is what the tier is about. A protected project never
reaches a row whose place is a personal Google sign-in, whatever the model.
Exit 0 always, as `machines` does.

`--command` prints the headless command line the route's harness would run,
built by the profile (`claude -p ...`, `agy -p ... --model ...`). It is
printed and not run; running a route, and reading what it did, is a later
branch. The millwright's operation 12 runs `murmurent route` and reports the
row or the refusal, and never chooses on its own.

### One session record for every harness

Phase 4. Each profile reads its own transcripts into one kind of row (time,
harness, model, place, session, project, tool, a short summary of the
arguments): Claude Code's one file per session under `~/.claude/projects/`,
Antigravity's `transcript.jsonl` under each conversation's folder in
`~/.gemini/antigravity/brain/` (read from the App 2.32.1's own files on
2026-11-16: one JSON object per step; a `PLANNER_RESPONSE` step carries the
tool calls). The audit log, which the hooks write for every harness, adds
the refusals and, for Antigravity, the model, since its transcript names
none.

```bash
murmurent sessions                 # yesterday's and today's sessions, every harness
murmurent sessions --since 2026-11-01
murmurent sessions --all --json
```

One row per session: start, end, harness, model, place, project, tool calls,
refusals. A harness whose transcripts could not be read has a row of its own
saying so, never a silent gap. The dashboard's agent pane already shows the
line the adapter writes at an Antigravity session's start, beside Claude
Code's.

The same live conversations showed the App's own tool names (`read_file`
with a `Path` argument, `search_web`, `run_command`), not the `view_file`
of its hooks documentation. The governance hook therefore now matches every
tool, and a tool name murmurent has not met is classed by what it says
(`edit`, `write`, `create`, `delete`, `command`, `read`) so that a write
tool under a new name still reaches the guards; a name that says nothing is
allowed, as before.

### The Claude Code assumptions still in the code

Read on 2026-11-16 with the two profile modules excluded. Each moves behind a
profile in the phase named; "text" means a help string or docstring only.

| Kind | Files | Phase |
|---|---|---|
| Install paths: where agents, rules, skills, settings and `CLAUDE.md` are linked or read | `scripts/setup.sh`, `scripts/bootstrap.sh` (text), `scripts/install_remote.sh` (text), `commands/setup_cmd.py`, `commands/doctor_cmd.py` (done: checks the chosen harnesses), `commands/install_cmd.py` (text), `commands/repo_cmd.py`, `commands/project_push_cmd.py`, `commands/centre_cmd.py`, `commands/agent_cmd.py` (text), `cli.py` (text), `core/agent_forks.py`, `core/agent_levels.py`, `core/agent_in_use.py`, `core/agent_links.py`, `core/agent_edit.py` (text), `core/personal_agents.py`, `core/repo_ready.py`, `core/repo_inventory.py`, `core/adopt.py`, `core/project_cc_init.py`, `core/remote_adopt.py`, `core/remote_install.py`, `core/vault_provision.py`, `core/paper_package.py`, `core/choreography_init.py`, `core/security_agent_review.py`, `core/projectize.py` (text), `dashboard/server.py` (text), `hooks/context_inject.py`, the hook and MCP docstrings, `scripts/murmurent_sec_scan.sh`, the push, project-push, reset and admin skills | 1 (the global links: done through `install --harness`); the per-repository links (`repo adopt`, `repo upgrade`, `project_cc_init`, the remote installs) and the agent forks: phase 1, second PR |
| Session state: transcripts, the audit log, the agents log, agent memory | `hooks/audit.py` (done: the row carries harness, model and place), `dashboard/audit_log.py` (text), `core/role_audit.py` (text), `core/project_gather.py`, `dashboard/snapshot.py`, `dashboard/workspace_file.py`, `dashboard/contract.py`, `core/project_cc_init.py` (the tail task), `scripts/murmurent_log_agent_event.sh`, `scripts/start_workspace.sh`, the update-me skill | 4 |
| The harness as a program: running `claude`, detecting a session | `dashboard/launchers.py`, `dashboard/workspace_file.py`, `scripts/bootstrap.sh` | 3 (the headless command) and 4 |
| Later, said so in the docs | the training movies (one harness on screen); the `teacher` modes and the course skill (Claude Code subagents) | not planned |

There are no `claude -p` calls and no `claude` subprocess in the code today:
murmurent has never run a harness headless, so phase 3 builds that command
line rather than replacing one.

## Risks

- **Governance hooks absent.** Every Antigravity session on this Mac today
  runs with no `raw_guard` and no `protected_paths`; the App can write under
  `immutable/`. The adapter hook and the `write_file` deny rules close this,
  and until both are installed the routing table must send no task that
  touches the data root to Antigravity.
- **Protected data reaching a second vendor.** Under the personal sign-in in
  use here, Google may retain, review and train on prompts, code and tool
  output. A `protected` project (patient-derived data under an ethics board)
  cannot go there at all; a `restricted` one (unpublished results, a patent
  position) should not. The `data:` field of each route is the guard, plus
  the `phi_check` hook once adapted. A Google Cloud sign-in with `us` or `eu`
  residency is the only documented route to contractual terms, and whether it
  excludes training is still unconfirmed.
- **Two transcript stores, two formats.** The nightly review and the session
  record in the vault each need a second reader. Until written, half of what
  the lab did is invisible to the review.
- **Model names drift.** Three models on the list are removed two days after
  this note was written. A route must be checked against `agy models` at
  install time, not trusted.
- **Skills lose their guards.** `disable-model-invocation` is not honoured,
  so a skill meant for a person to type can be chosen by the model.
- **Permissions live in two places** (the CLI's `settings.json`, the App's
  own settings), neither of which the installer should write. A rule the PI
  sets in one surface does not hold in the other.

## What was not done

Nothing was installed, no setting changed, no `agy` CLI fetched, no
conversation run in Antigravity, and nothing was sent to Google. The CLI and
SDK are described from documentation only.
