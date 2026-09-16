# Murmurent — development repository

**You are in `murmurent_dev`.** This is where Murmurent is built: all history,
every issue and pull request, the test suite, and the release machinery. It is
not what users install.

| I want to… | Go to |
|---|---|
| **use** Murmurent | [`hallettmiket/murmurent`](https://github.com/hallettmiket/murmurent) — the release repo, or `uv tool install murmurent` |
| **read** the docs | <https://hallettmiket.github.io/murmurent/> |
| **report** a bug or ask for a feature | [issues here](https://github.com/hallettmiket/murmurent_dev/issues) — the release repo has issues turned off |
| **work on** Murmurent | keep reading, then [`DEVELOPING.md`](DEVELOPING.md) |

Murmurent is shared agentic-AI infrastructure for researchers, labs, cores and
research centres: it lets groups work independently, pool agents and data when
collaboration helps, and accumulate institutional knowledge across projects.
[`CLAUDE.md`](CLAUDE.md) is the architectural overview Claude Code itself loads
at the start of every session in this repo — read it first, because the agents
you are editing are written against it.

## The three repositories

| | |
|---|---|
| [**`murmurent_dev`**](https://github.com/hallettmiket/murmurent_dev) | **Development. You are here.** Full history, issues, PRs, `tests/`, `release/`, `DEVELOPING.md`, and this deployment's own `rules/local/`. |
| [**`murmurent`**](https://github.com/hallettmiket/murmurent) | **Releases.** One squashed commit per release, no development history, issues disabled. Built from a tag here by [`release/make_release.sh`](release/make_release.sh) and published to PyPI from there. |
| [**`murmurent_public`**](https://github.com/hallettmiket/murmurent_public) | **The public directory.** Every institution running Murmurent, how to join it, and the index of published choreographies. |

Code flows one way — dev to release, and only at a release. **Nothing is ever
committed directly to the release repo**, and nothing develops against it: it
has no tests and no history to bisect.

## Get set up

You need `git`, [Claude Code](https://claude.com/claude-code), and
[uv](https://docs.astral.sh/uv/) (which fetches Python 3.12 for you if your
system has none).

```bash
git clone git@github.com:hallettmiket/murmurent_dev.git ~/repos/murmurent_dev
cd ~/repos/murmurent_dev
uv tool install --python 3.12 -e .      # editable: your edits take effect at once
bash scripts/setup.sh                   # symlink agents/ rules/ skills/ into ~/.claude/
murmurent install --hooks               # register the hooks + MCP servers
murmurent doctor                        # every problem it prints comes with its fix
```

`setup.sh` **symlinks** rather than copies, so editing an agent or a rule in
this clone changes what every Claude Code session on this machine loads. That is
the point, and also why a careless edit here is felt immediately.

Two things to know before you trust your first edit, both written up in
[`DEVELOPING.md`](DEVELOPING.md): how to confirm you are reading this clone's
commons and not a packaged copy, and why `rules/local/` exists. Do **not** run
`scripts/bootstrap.sh` to develop — it clones the release repo.

## Making a directory ready against your dev clone

A directory is **Murmurent-ready** when it carries a `.murmurent.yaml` marker
and a `.claude/agents/` of symlinks into the commons — that is what lets a
Claude Code session opened there use the agents. You will want this on the
throwaway repositories you test against, and on whatever you actually do
research in.

One procedure covers every starting point: a folder you made a minute ago, a
repository with ten years of history, or one an older Murmurent set up. Nothing
already there is touched. Ask first, because the answer decides the step:

```bash
murmurent repo status ~/repos/<directory>
```

| It says | Do this |
|---|---|
| `✗ not a git repo` | `git -C ~/repos/<directory> init`, then the next row |
| `• clone` | `murmurent repo adopt ~/repos/<directory> --agents <names>` |
| `± partial` | the same `adopt` — idempotent, it finishes the job |
| `✓ ready`, older version | `murmurent repo upgrade ~/repos/<directory> --all-agents` |
| `✓ ready`, current | open Claude Code in it |

Two things that catch people, neither of them dev-specific:

- **The directory must live under `~/repos/`.** `adopt` refuses any other path.
- **`adopt` links no agents unless you name them.** A bare `murmurent repo
  adopt` leaves `.claude/agents/` *empty* and the marker's `agents: []`. Pass
  `--agents oracle,blacksmith`, or follow with `repo upgrade <path>
  --all-agents`.

### The dev-clone trap: check where the links point

**`repo adopt` and `repo upgrade` do not resolve the commons the way the rest of
the CLI does.** They use `core.repo.murmurent_repo_root()`, which is
`~/repos/murmurent` unless `$MURMURENT_REPO_ROOT` says otherwise — while
`murmurent setup`, `install` and `doctor` use `core.commons.commons_root()`,
which prefers whichever clone you are actually running from. On a machine with
both clones the two disagree, and the symptom is quiet: your edit to an agent
here shows up in `~/.claude/agents/` and **not** in an adopted repo.

Check, rather than assume:

```bash
readlink ~/repos/<directory>/.claude/agents/adversary.md
```

If that prints a path under `~/repos/murmurent`, the repo is following the
release clone. Point adopt and upgrade at this one instead:

```bash
export MURMURENT_REPO_ROOT=~/repos/murmurent_dev
murmurent repo upgrade ~/repos/<directory> --all-agents
```

Put that `export` in your shell profile if you develop here routinely. It is
worth knowing this is a defect rather than a convention — see the note at the
end of this section in [`DEVELOPING.md`](DEVELOPING.md).

## Keeping your clone, and your repos, current

Someone else's changes reach you in two moves: update the clone, then update the
repositories wired to it. Doing only the first leaves every ready repo pointing
at yesterday's structure.

```bash
cd ~/repos/murmurent_dev
git pull                                          # collect other people's work
uv tool install --python 3.12 --reinstall -e .    # only when pyproject.toml changed
bash scripts/setup.sh                             # link new agents/rules/skills; prune retired ones
murmurent install --hooks                         # re-register hooks + MCP servers
murmurent doctor                                  # confirm what you are actually reading
MURMURENT_REPO_ROOT=~/repos/murmurent_dev murmurent repo upgrade --all
```

**Most of the time you need none of it.** Agent, rule and skill *text* is live
the moment you save, in this clone and in every ready repo, because everything
is symlinks rather than copies. That is the whole point of `setup.sh`. What
needs a command is anything structural:

| What changed in the pull | What you run |
|---|---|
| the wording of an agent, rule or skill | nothing — already live |
| a new agent, rule or skill file | `bash scripts/setup.sh`, then `repo upgrade --all --all-agents` |
| an agent was retired or renamed | `bash scripts/setup.sh` — it prunes the dangling link |
| Python code | nothing; the editable install reads your working tree |
| `pyproject.toml` (deps, entry points) | `uv tool install --python 3.12 --reinstall -e .` |
| the version, or the `.murmurent.yaml` schema | `murmurent repo upgrade --all` |
| you are not sure | the whole block above, in order — each step is idempotent |

`murmurent doctor` is the one to run when something feels stale: it names the
clone it is reading, its commit, and whether the packaged copy is shadowing it.

A clone made before 2026-09-01 has `origin` pointing at the release repo and its
`git pull` fails with unrelated histories; `doctor` detects exactly that and
prints the remote-url fix.

## Where things are

| Path | What lives there |
|---|---|
| [`agents/`](agents/) | The 14 commons agents, one Markdown file each. The public release essentially *is* this directory. Each must lead its final reply with a ≤200-char verdict ([`rules/headline_first.md`](rules/headline_first.md)), and adding one means adding its row to that rule and to [`CLAUDE.md`](CLAUDE.md) in the same commit. |
| [`rules/`](rules/) | The five hard rules auto-loaded into every session. `rules/local/` is this deployment's own and never ships. |
| [`skills/`](skills/) | The six user-invocable slash commands (`SKILL.md` per directory). |
| [`src/murmurent/`](src/murmurent/) | The Python package. `cli.py` is the entry point; `commands/` one module per CLI command group, `core/` the model and logic, `dashboard/` the FastAPI dashboard, `hooks/` the Claude Code hooks that enforce the data-governance rules, `mcp/` the MCP servers. |
| [`scripts/`](scripts/) | `setup.sh`, `bootstrap.sh`, launchers, and the `seed_*.py` demo-data scripts. |
| [`templates/`](templates/), [`instruments/`](instruments/) | Scaffolding written into new repos; instrument descriptors. |
| [`tests/`](tests/) | 161 test modules, ~2350 tests. `tests/agent_eval/cases/` holds agent-behaviour cases. Withheld from the release. |
| [`release/`](release/) | The release machinery: [`allowlist.yaml`](release/allowlist.yaml), [`check_allowlist.py`](release/check_allowlist.py), [`make_release.sh`](release/make_release.sh), and [`README_public.md`](release/README_public.md) — the user-facing README. Withheld from the release. |
| [`docs/`](docs/) | The MkDocs site published at the URL above. |

## How a change gets in

1. **An issue first**, for anything a user would notice. The templates are
   under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) (bug, feature,
   smoke-test finding).
2. **A branch**, named for what it does: `feat/…`, `fix/…`, `docs/…`, and
   `fix/<issue-number>-<slug>` when it closes one. Never commit to `main`.
3. **Write it, with a test.** Match the style of the code around you;
   [`docs/style/code-style.md`](docs/style/code-style.md) and
   [`docs/style/documentation.md`](docs/style/documentation.md) are the
   written-down version (type hints, `pathlib`, script headers, `black` and
   `isort` before committing).
4. **Classify any file you add** in [`release/allowlist.yaml`](release/allowlist.yaml),
   **in the same commit that adds it.** A path matching no rule stops the next
   release on purpose: a path nobody classified is a decision nobody made.
5. **Run the checks** (below) before you push.
6. **Open the PR** against `main`:
   ```bash
   gh pr create --fill --base main
   ```
   Describe what changed and why, and say what you ran. If the change touches
   shared code or data, the [`security_guard`](agents/security_guard.md) agent
   is meant to see it; methodological changes go past the
   [`adversary`](agents/adversary.md). Both run inside Claude Code — they are
   not CI jobs.
7. **Merge to `main`** once it is reviewed. `main` is what a release is cut
   from, so it is expected to be releasable at any time.

## Before you push

```bash
uv run --python 3.12 --extra dev pytest -q     # the suite
python3 release/check_allowlist.py             # every tracked file classified
```

Run pytest **through `uv`**, not through a bare `python3 -m pytest`. The
`python3` on your PATH is often a conda `base` — it is below the 3.12 floor and
has none of the runtime dependencies, so the suite collects with dozens of
`ModuleNotFoundError`s that look like real breakage and are not. Targeted runs
take the same prefix:

```bash
uv run --python 3.12 --extra dev pytest -q tests/test_release_hygiene.py
```

Two of these tests exist to stop a specific class of mistake, so read their
docstrings before you work around them:
[`tests/test_release_hygiene.py`](tests/test_release_hygiene.py) fails if a
shipping file names a private repo, a grant document or a Slack ID, and
[`tests/test_packaged_commons.py`](tests/test_packaged_commons.py) guards the
packaging that puts the commons inside the wheel.

A handful of tests are sensitive to the machine they run on rather than to the
code: they pick up whatever `code` binary is on your PATH, your git identity, or
a missing `age`. On an unmodified `main` in September 2026 this machine saw 4
failed / 2315 passed / 38 skipped. **Record your own baseline on a clean `main`
before assuming a failure is yours** — and when you do fix one of these, fix it
by removing the environment dependency, not by skipping the test.

## Exercising Murmurent without real people

Most of what the CLI does is irreversible-looking (mints keys, writes
`~/.murmurent/`, creates GitHub repos and Slack channels). Three ways to work
on it safely:

- **A scratch `HOME`**, which is how the release verification in
  [`DEVELOPING.md`](DEVELOPING.md) works: `HOME=$(mktemp -d)` in front of the
  command leaves your real `~/.claude/` and `~/.murmurent/` untouched.
- **The [`/murmurent-reset`](skills/murmurent-reset/SKILL.md) skill**, which
  tarballs `~/.murmurent` and then resets this machine to a first-run state, so
  `centre-init` can be exercised again. It has a `--dry-run`.
- **The seed scripts** — `scripts/seed_two_labs.py`, `seed_tutorial.py`,
  `seed_fake_users.py` — which populate fake labs, members, projects and
  certifications so the dashboard has something to show. Read the header of the
  one you run first: they write into real paths (`~/repos/lab_mgmt`,
  `~/.murmurent/lab_info/`) and `seed_two_labs.py` wipes what it reseeds.

The member / PI / mayor onboarding flows themselves — `enroll`,
`issue-member-card`, `import-card`, `centre-init` — are documented for the
people who run them in
[`release/README_public.md`](release/README_public.md) and on the
[docs site](https://hallettmiket.github.io/murmurent/identity/). You need them
to *test* the identity chain; you do not need to have joined a centre to
develop here.

## Cutting a release

Full procedure, with the PyPI trusted-publishing setup and the manual
pre-release checks: [`DEVELOPING.md`](DEVELOPING.md). In outline:

1. Bump the CalVer version in `src/murmurent/__init__.py` — the single source of
   truth ([`docs/versioning.md`](docs/versioning.md) says when to bump).
2. Update [`CHANGELOG.md`](CHANGELOG.md).
3. Update [`release/README_public.md`](release/README_public.md) if the release
   changes anything a user does — **before** tagging, because the export reads
   the README from the tag.
4. Commit and tag here: `git tag -a v2026.9.9 -m "…" && git push origin v2026.9.9`.
5. Export the release tree:
   ```bash
   bash release/make_release.sh v2026.9.9 https://github.com/hallettmiket/murmurent.git --dry-run
   bash release/make_release.sh v2026.9.9 https://github.com/hallettmiket/murmurent.git
   ```
   It refuses to run unless the allowlist classifies every tracked file and no
   shipping file names a deployment fact. It prints the **dev SHA** — put that
   in the GitHub Release notes, because two repos means two tags for one version
   and that line is the only thing tying a release back to the commit it came
   from.
6. Create the Release on the public repo. Publishing it triggers
   [`.github/workflows/publish.yml`](.github/workflows/publish.yml) there, which
   uploads to PyPI via trusted publishing.

## The two READMEs

This file is the development repository's landing page and **does not ship**.
The user-facing README lives at
[`release/README_public.md`](release/README_public.md) and `make_release.sh`
copies it to `README.md` in the release tree — which also makes it the PyPI
project page, via `readme = "README.md"` in
[`pyproject.toml`](pyproject.toml).

So: **install instructions, identity flows and centre setup are edited in
`release/README_public.md`. Developer instructions are edited here.** Neither
one is a copy of the other, and a README edited in the release repo is
overwritten by the next release.

## Documentation site

[`docs/`](docs/) is built with MkDocs Material and published to GitHub Pages by
[`.github/workflows/docs.yml`](.github/workflows/docs.yml) on any push to `main`
that touches `docs/**` or `mkdocs.yml`. That workflow ships, so it runs in **both**
repositories: this repo publishes a pre-release preview of the site, and the
release repo publishes the site users read at
<https://hallettmiket.github.io/murmurent/>. Build it locally before pushing doc
changes — the workflow runs `--strict`, so one broken link fails it:

```bash
uv run --python 3.12 --extra docs mkdocs build --strict
uv run --python 3.12 --extra docs mkdocs serve      # live preview
```

A page must be in the `nav:` of [`mkdocs.yml`](mkdocs.yml) or in its
`exclude_docs:` list; keep `exclude_docs` in step with the withheld entries in
the release allowlist.

## Conduct, licence, authors

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
Murmurent is Apache-2.0 ([`LICENSE`](LICENSE)).

Mike Hallett &mdash; michael.hallett@uwo.ca
