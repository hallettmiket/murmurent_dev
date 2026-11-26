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
plain client on 2026-11-26, from a member's own machine. The scheduled run
reaches fewer of them: see the next section.

## Reading from the scheduled run

The scheduled run works on Anthropic's machines, in a sandbox that reaches
only the sites its **cloud environment** allows
([how to set that](lookout.md#the-network-setting)). Two things follow.

**The sites that must be on the allowed list**, because the default list
does not hold them: `youtube.com`, `arxiv.org`, `antigravity.google`,
`modelcontextprotocol.io` and `developers.openai.com`, each with its
subdomains.

**GitHub pages of other repositories cannot be allowed at all.** A cloud
run reaches `github.com` through a gateway that serves only the
repositories attached to the task, so a releases page, a commits feed or
the GitHub API for any other repository is refused (seen on 2026-11-26,
issue 360). The files of a public repository still load from
`raw.githubusercontent.com`, which is on the default list. So from the
scheduled run, each GitHub source below is read from the file named here,
not from its page or its feed:

| Source | Read this file from the scheduled run | What it gives | Read |
|---|---|---|---|
| Claude Code changelog | <https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md> | every version, newest first; the whole of what the releases feed carries | 2026-11-26 |
| Claude Agent SDK for Python | <https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/main/CHANGELOG.md> | each version's notes; lags the releases by about two weeks | 2026-11-26 |
| Anthropic skills | <https://raw.githubusercontent.com/anthropics/skills/main/.claude-plugin/marketplace.json> | the list of published skills; one that no earlier report and no murmurent file names is new. A skill's own file is at `.../main/skills/<name>/SKILL.md` | 2026-11-26 |
| Claude cookbooks | <https://raw.githubusercontent.com/anthropics/claude-cookbooks/main/registry.yaml> | every worked example with its title, description, path and date; read the entries dated since the last report | 2026-11-26 |
| OpenAI Codex | none of use: the repository's `CHANGELOG.md` only points at the releases page | read <https://developers.openai.com/codex/changelog> once that site is allowed | 2026-11-26 |
| Model Context Protocol | <https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/draft/changelog.mdx> | the changes in the draft of the next version; the published changelog is on `modelcontextprotocol.io` once that site is allowed | 2026-11-26 |
| Awesome Claude Code | <https://raw.githubusercontent.com/hesreallyhim/awesome-claude-code/main/README.md> | the whole list as it stands today, a large file; there is no record of what was added when, so an entry counts as new only when no earlier report names it | 2026-11-26 |

A file shows what the repository holds today, not what changed since the
last run. Where the table says so, the lookout's earlier reports are what
tells new from old. A source that could be read neither way is
`UNRESOLVED` with the reason, as always.

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
| YouTube, by search | `WebSearch` with the query terms and the word `youtube` | a fallback for a video outside the channels below: the results page loads as an empty script shell for a plain client (2026-11-26), so a video is found through web search and read by its transcript with `scripts/lookout_videos.py transcript <id>`; never as watched | search only | none | 2026-11-26 |

## Video: the channels

People who publish near-daily videos on Claude Code techniques are a source
the pages above do not replace: a feature often reaches a channel as a
worked example days before it reaches a written guide. The lookout reads
them the only way that is honest: by the **transcript**, never the title and
never as watched. `scripts/lookout_videos.py list --since <date>` reads each
channel's own feed (`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`,
plain XML, the last fifteen uploads) and prints what was uploaded since the
last run; `scripts/lookout_videos.py transcript <video id>` prints the
transcript, through the `youtube-transcript-api` package, which the lookout
may install in its own sandbox (that changes nothing in murmurent). A video
with no transcript is `UNRESOLVED`.

**Which channels are worth it is learned, not assumed.** Every report's
"Read and set aside" names each channel, how many uploads were read, and
what came of them. The bookworm moves that into the **Yield** column, so a
channel that has given nothing in a month is dropped and one the lookout
keeps proposing is added. The list below is the starting point, from one
afternoon's search on 2026-11-26, not a ranking.

| Channel | Address | What it covers | Yield | Read |
|---|---|---|---|---|
| Chase AI | <https://www.youtube.com/feeds/videos.xml?channel_id=UCoy6cTJ7Tg0dqS-DI-_REsA> | Claude Code for non-programmers, tool roundups, new releases the day they land; near-daily | none yet | 2026-11-26 |
| IndyDevDan | <https://www.youtube.com/feeds/videos.xml?channel_id=UC_x36zCEGilGpB1m-V4gmjg> | agentic engineering: CLAUDE.md, hooks, skills, multi-agent orchestration; weekly | none yet | 2026-11-26 |
| Cole Medin | <https://www.youtube.com/feeds/videos.xml?channel_id=UCMwVTLZIRRUyyVrkjDpn4pA> | agents, MCP, memory ("second brain"), Claude Code workflows; weekly | none yet | 2026-11-26 |
| Simon Scrapes | <https://www.youtube.com/feeds/videos.xml?channel_id=UCdCR4-uYOg5ju-IUuDnfnQA> | new Claude Code features within days of release, explained for non-specialists | none yet | 2026-11-26 |
| Nick Saraev | <https://www.youtube.com/feeds/videos.xml?channel_id=UCbo-KbSjJDG6JWQ_MTZ_rNA> | long-form, technical Claude Code courses and workflows | none yet | 2026-11-26 |
| Nate Herk | <https://www.youtube.com/feeds/videos.xml?channel_id=UC2ojq-nuP8ceeHqiroeKhBA> | Claude Code and automation for beginners | none yet | 2026-11-26 |
| AI Jason | <https://www.youtube.com/feeds/videos.xml?channel_id=UCrXSVX9a1mj8l0CMLwKgMVw> | Claude Code workflows and agent patterns | none yet | 2026-11-26 |
| Matthew Berman | <https://www.youtube.com/feeds/videos.xml?channel_id=UCawZsQWqfGSbCI5yjkdVkTA> | model and tool comparisons, news; broad, so read only the Claude Code uploads | none yet | 2026-11-26 |
| Anthropic | <https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA> | the company's own channel: feature walkthroughs, model launches; occasional | none yet | 2026-11-26 |

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
