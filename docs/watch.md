# The watch list: where the Lookout reads

The [lookout](https://github.com/hallettmiket/murmurent/blob/main/agents/lookout.md)
reads the places where new techniques for agentic AI appear and reports the
few that would make murmurent better at its job. This file is where it
reads: each page, what to read on it, how it loads for a plain client, and
the date it was last read. The
[bookworm](https://github.com/hallettmiket/murmurent/blob/main/agents/bookworm.md)
keeps it, as it keeps the funder registry and the journal registry; the
lookout proposes a source and never edits the file.

**What an entry is and is not.** An entry says that a page exists and what
it showed on the date read. It is not a finding. The lookout opens the page
on the day it runs, because this is the fastest-moving list murmurent keeps:
a changelog gains entries weekly and a repository can be renamed between
two runs. A reader who wants to know what is new opens the page, not this
file.

**How each page loads** is recorded the way the funder registry records it:
`plain` answers a plain client with its content; `script` is drawn by
JavaScript, so a plain fetch gets a shell and the lookout must read it
through `WebFetch`, which renders; `feed` names an Atom or RSS feed beside
the page, which a plain client can read whole. Every page below answered a
plain client on 2026-11-26.

## Anthropic: the harness murmurent runs on first

| Source | Page | What to read | Loads | Feed | Read |
|---|---|---|---|---|---|
| Claude Code changelog | <https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md> | every version since the last run: new tools, settings, hooks, subagent and skill features, deprecations; the raw file is at <https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md> | plain | <https://github.com/anthropics/claude-code/releases.atom> | 2026-11-26 |
| Claude Code docs: changelog | <https://code.claude.com/docs/en/changelog> | the documented form of the same releases, with the pages that explain each feature | script | none | 2026-11-26 |
| Claude Platform release notes | <https://platform.claude.com/docs/en/release-notes/overview> | new models, API features, tools and deprecations; the Agent SDK's notes are linked from here | plain | none | 2026-11-26 |
| Claude Agent SDK for Python | <https://github.com/anthropics/claude-agent-sdk-python/releases> | each release's notes: what a program that drives Claude Code can now do. The releases page carried no notes on 2026-11-26; read the raw `CHANGELOG.md` at <https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/main/CHANGELOG.md>, which lags the releases by about two weeks, and the commits feed beside it | plain | commits feed: add `/commits/main.atom` to the repository address | 2026-11-26 |
| Anthropic engineering | <https://www.anthropic.com/engineering> | the long notes on how to build agents, write tools, manage context and evaluate; the posts murmurent's own rules most often cite | plain | none found on 2026-11-26 (`/rss.xml` answers 404) | 2026-11-26 |
| Anthropic news | <https://www.anthropic.com/news> | announcements; read only the titles, open an item only when it names a tool or method | plain | none | 2026-11-26 |
| Anthropic skills | <https://github.com/anthropics/skills> | the published skills and the skill-writing guidance; a new skill here is a candidate for a murmurent agent's "Optional helpers" | plain | commits feed: add `/commits/main.atom` | 2026-11-26 |
| Claude cookbooks | <https://github.com/anthropics/claude-cookbooks> | worked examples of techniques; read the recent commits, not the whole | plain | commits feed: add `/commits/main.atom` | 2026-11-26 |

## The other harnesses

| Source | Page | What to read | Loads | Feed | Read |
|---|---|---|---|---|---|
| Antigravity changelog | <https://antigravity.google/docs/changelog> | each release: agent, skill, hook and tool features, for the second harness murmurent runs on ([which agent works where](harnesses.md)) | plain | none | 2026-11-26 |
| OpenAI Codex changelog | <https://developers.openai.com/codex/changelog> | each release; the GitHub releases page is at <https://github.com/openai/codex/releases> with a feed | script | <https://github.com/openai/codex/releases.atom> | 2026-11-26 |
| Model Context Protocol | <https://modelcontextprotocol.io/specification/latest/changelog> | changes to the protocol murmurent's four data services speak; the releases are at <https://github.com/modelcontextprotocol/modelcontextprotocol/releases> | plain | add `.atom` to the releases address | 2026-11-26 |

## Methods

| Source | Page | What to read | Loads | Feed | Read |
|---|---|---|---|---|---|
| arXiv, by query | `https://export.arxiv.org/api/query?search_query=<terms>&sortBy=submittedDate&max_results=25` | the API returns Atom; one query per term in the Searches section below, newest first; open a paper's abstract page before reporting it. `https`, not `http`: the API answers `http` with a redirect and a plain client that does not follow it gets an empty body | plain | the query is the feed | 2026-11-26 |

## The community

| Source | Page | What to read | Loads | Feed | Read |
|---|---|---|---|---|---|
| Awesome Claude Code | <https://github.com/hesreallyhim/awesome-claude-code> | a curated list of skills, hooks, commands and workflows; read the recent commits for additions | plain | commits feed: add `/commits/main.atom` | 2026-11-26 |
| YouTube, by search | `WebSearch` with the query terms and the word `youtube` | the results page itself loads as an empty script shell for a plain client and for `WebFetch` (2026-11-26), so a video is found through web search, then its own page is opened for the description and transcript; reported from those, never as watched | search only | none | 2026-11-26 |

## Searches

Fixed queries, made of public terms. The lookout runs each on `WebSearch`,
on arXiv through the API above, and on YouTube, and opens every candidate's
own page before it reports it. A query never carries the centre's name, a
person's name, a project's name or a file path.

| Terms | What it is for |
|---|---|
| `agent memory` | the oracle, the lab oracle and the notebook: how agents keep and retrieve what they learned |
| `agent evaluation harness` | the agent tests and the harness matrix: how agent files are checked |
| `LLM agent security hooks` | the three data-root hooks and the security guard |
| `multi-agent orchestration research` | the choreographies and the judge |
| `MCP server bioinformatics` | the bookworm's databases and the four data services |
| `LLM scientific literature verification` | the bookworm's citation checker and the detective |
| `agentic AI life science research` | the mandate itself |
| `Claude Code subagents skills hooks` | the commons as a whole |

## Proposing a source

The lookout ends a report with **For the bookworm** when it read something
the list should hold: the page, what it showed, how it loads, and why
murmurent would miss it. The bookworm reads the page, adds the row with the
date, and the next run reads it.
