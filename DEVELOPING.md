# Working on murmurent itself

**This file is in the development repository only.** It is not part of a
release. If you are here to *use* murmurent, you want the public repo at
[hallettmiket/murmurent](https://github.com/hallettmiket/murmurent), whose
README is written for that; the copy of it here is
[`release/README_public.md`](release/README_public.md).

[`README.md`](README.md) is this repository's own landing page — the repo map,
the pull-request flow, and a short form of the release steps below. This file is
the long form: setup, `rules/local/`, the pre-push gates, and the release and
PyPI procedures in full.

## The two repositories

| | |
|---|---|
| [`hallettmiket/murmurent`](https://github.com/hallettmiket/murmurent) | **release only.** One commit per release, no development history, no issues, no PRs. This is what people clone and install. |
| [`hallettmiket/murmurent_dev`](https://github.com/hallettmiket/murmurent_dev) | **development.** All history, issues, PRs, branches and build notes. You are here. |

Code flows one way, dev to public, and only at a release. Nothing is ever
committed directly to the public repo.

## What is in this repository

| Folder | What's in it |
|---|---|
| [`agents/`](agents/) | The 14 shared agents — Oracle, Bookworm, Adversary and the rest — one plain-English Markdown file each. This is the heart of Murmurent; an agent is defined by writing instructions for it, not by writing code. |
| [`rules/`](rules/) | Five short documents that Claude Code loads into *every* session, covering things like where data may be written. `rules/local/` holds the settings belonging to one particular institution, and is never published. |
| [`skills/`](skills/) | The slash commands, such as `/murmurent-push`. One folder each, containing a `SKILL.md`. |
| [`src/murmurent/`](src/murmurent/) | The Python code behind the `murmurent` command: `commands/` has one file per command, `core/` the logic they share, `dashboard/` the web dashboard, `hooks/` the checks that stop a Claude Code session writing where it shouldn't, `mcp/` the servers that let agents search your notes. |
| [`docs/`](docs/) | Everything on <https://hallettmiket.github.io/murmurent/>. |
| [`tests/`](tests/) | Around 2,300 automatic checks that Murmurent still works. |
| [`release/`](release/) | The tooling that builds the public version — see "Publishing a new version" below. |
| [`scripts/`](scripts/) | Installers, launchers, and scripts that fill a test machine with realistic fake labs and people. |

Two conventions worth knowing before you edit an agent. Every agent must begin
its final reply with a one-line verdict, no more than 200 characters, because
that line is all the dashboard shows — the reasoning is in
[`rules/headline_first.md`](rules/headline_first.md). And if you add a new
agent, add it to that file's table and to [`CLAUDE.md`](CLAUDE.md) in the same
breath, or the next person won't know it exists.

## Setting up to develop

You need Python 3.12+ (`uv` will fetch one if you have none), `git`, and
[Claude Code](https://claude.com/claude-code).

```bash
git clone https://github.com/hallettmiket/murmurent_dev.git ~/repos/murmurent_dev
cd ~/repos/murmurent_dev
uv tool install --python 3.12 -e .     # editable: your edits take effect at once
bash scripts/setup.sh                   # symlink agents/ rules/ skills/ into ~/.claude/
murmurent install --hooks               # register hooks + MCP servers
```

`scripts/setup.sh` symlinks rather than copies, so editing an agent or a rule
in this clone changes what every Claude Code session on this machine loads. That
is the point, and it is also why a careless edit here is felt immediately.

**Check which commons you are actually reading**, especially if you also have
murmurent installed from PyPI:

```bash
uv run --python 3.12 python3 -c "from murmurent.core.commons import commons_root, commons_source; print(commons_source(), commons_root())"
```

It should print `clone` and the path to this clone. Run it through `uv`, for the
same reason as the test suite: a bare `python3` is often a conda `base` that has
no `murmurent` installed at all, and answers `ModuleNotFoundError` to a question
you did not ask. If it prints `package`, the
CLI is reading the copy inside the wheel and your edits will do nothing.
The editable install above normally prevents that; `export MURMURENT_COMMONS_ROOT=$PWD`
forces it.

Do **not** run `scripts/bootstrap.sh` for development: it clones the *public*
repo, which has no history and no tests.

### One commons, and how it is resolved

`core.commons.commons_root()` is the single answer to "where is the commons?",
and the rule it implements is **the clone you installed is the clone your repos
follow**:

1. `$MURMURENT_COMMONS_ROOT`, an explicit override.
2. The clone this package runs from, when installed `-e`. So a clone at
   `~/repos/murmurent_dev` — which is where this file tells you to put one — is
   found, not just the conventional path.
3. `~/repos/murmurent`, **if it actually contains a commons**. Checked by
   content, so an empty directory left by a failed clone cannot out-rank the
   packaged copy and leave someone with no agents.
4. The copy inside the installed wheel.

A clone always beats the packaged copy, because editing an agent and seeing no
effect is the worst failure this could have.

`repo adopt` and `repo upgrade` used to be the exception, resolving through
`core.repo.murmurent_repo_root()` — hardcoded `~/repos/murmurent`. On a machine
holding both clones the two disagreed, and the symptom was silent: `doctor`
reported the commons coming from `murmurent_dev` while a repo adopted a moment
earlier was linked into `~/repos/murmurent`, so an agent you edited here was
live in `~/.claude/agents/` and absent from that repo. Fixed; the
`$MURMURENT_REPO_ROOT` workaround that used to be necessary is not any more, and
`tests/test_readiness_drift.py` fails if the two resolvers diverge again.

To see which commons a repo follows, ask it:

```bash
murmurent repo status ~/repos/<repo>     # prints "follows commons <path>"
```

### Upgrading a development clone

```bash
cd ~/repos/murmurent_dev && git pull
uv tool install --python 3.12 --reinstall -e .   # only needed when pyproject.toml changed
bash scripts/setup.sh                             # new agents, rules, skills; removes links to retired ones
murmurent doctor
murmurent repo upgrade --all
```

Run the reinstall through `uv`, or through the interpreter murmurent actually
runs under (`murmurent doctor` prints it). The `pip` on your PATH is often a
different Python, a conda `base` for instance, and then the reinstall either
lands in the wrong interpreter or stops with
`Package 'murmurent' requires a different Python`.

**Clones made before 2026-09-01** point their `origin` at the release
repository, which was rewritten to one commit per release when the two repos
were split. `git pull` in such a clone fails with unrelated histories. The
doctor's `clone` check detects this (full history, release remote) and prints
the fix:

```bash
git remote set-url origin git@github.com:hallettmiket/murmurent_dev.git
git pull
```

Keep the directory where it is. `~/.claude/` and every ready repo symlink into
it by absolute path, and an editable install finds the commons at any path.

### Deployment-specific rules: `rules/local/`

`rules/` holds the rules that are true for every centre and ship publicly.
`rules/local/` holds the ones true only for this deployment: a private repo, a
Slack channel ID, a local convention. `setup.sh` symlinks both, and the release
allowlist withholds `rules/local/` entirely.

**Anything naming a private repo, a person, a channel ID or an institution
belongs in `rules/local/`.** `tests/test_release_hygiene.py` fails the build if
such a thing appears in a file that ships.

## Before you push

```bash
uv run --python 3.12 --extra dev pytest -q   # the suite
python3 release/check_allowlist.py           # every tracked file classified
```

Run pytest through `uv`. A bare `python3 -m pytest` takes whatever `python3` is
on your PATH, which is often a conda `base`: below the 3.12 floor and without
fastapi, slack-sdk or mcp, so dozens of modules fail to import and the run looks
broken when nothing is. (`check_allowlist.py` needs only `yaml`, so it is
indifferent.) A few tests are sensitive to the environment rather than the code
— establish your own baseline on a clean `main` before reading a failure as
yours.

The allowlist check matters more than it looks. **A file you add that matches
no rule stops the next release**, deliberately: a path nobody classified is a
decision nobody made. Classify it in `release/allowlist.yaml` in the same
commit that adds it.

## Cutting a release

1. Decide the version. CalVer `YYYY.M.MICRO`, one source of truth in
   `src/murmurent/__init__.py`. See [`docs/versioning.md`](docs/versioning.md)
   for when to bump and when not to.
2. Update `CHANGELOG.md`.
3. If the release changes anything a user does, update
   [`release/README_public.md`](release/README_public.md) — the user-facing
   README, which the export copies into the release tree as `README.md` and
   which PyPI renders as the project page. Editing this repo's own `README.md`
   does not reach a single user. Do it **before** the tag: the export takes the
   README from the tag, not from your working copy.
4. Commit, then tag: `git tag -a v2026.9.2 -m "..." && git push origin v2026.9.2`
5. Export:

   ```bash
   bash release/make_release.sh v2026.9.2 https://github.com/hallettmiket/murmurent.git
   ```

   Run it with `--dry-run` first if you want to see the tree without pushing.
   It refuses to proceed unless the allowlist classifies everything, no
   shipping file names a private repo, a grant document or a Slack ID, and
   `release_readme` exists in the tag being released.
6. It prints the **dev SHA**. Put that in the GitHub Release notes. Two repos
   means two tags for one version, and that line is the only thing connecting a
   public release back to the commit it came from.
7. Create the Release on the public repo. Publishing it triggers
   `.github/workflows/publish.yml`, which uploads to PyPI.

## Publishing to PyPI

The workflow uses **trusted publishing**, so there is no API token to store.
One-time setup, which only the PyPI account owner can do:

1. Sign in at [pypi.org](https://pypi.org) and go to *Your projects* →
   *Publishing* → *Add a new pending publisher*.
2. Fill in exactly:

   | field | value |
   |---|---|
   | PyPI Project Name | `murmurent` |
   | Owner | `hallettmiket` |
   | Repository name | `murmurent` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The repository is the **public** one, not `murmurent_dev`: that is where
   releases are published from.
3. In the public repo, *Settings → Environments → New environment* named
   `pypi`.
4. In the public repo, *Settings → Variables → Actions*, add
   `PYPI_ENABLED = true`.

Until step 4 the publish job is **skipped**, visibly, in every release run. The
build job still runs, so a release that cannot be packaged is caught either
way. The gate is an explicit variable rather than a silent condition, so the
run page says plainly whether anything was published.

After it is set up, installation for users becomes:

```bash
uv tool install murmurent
```

That is a **complete** install as of 2026.9.3. The wheel force-includes the
commons under `murmurent/commons/`, `core/commons.py` finds them, and
`murmurent install` wires them into `~/.claude/`. No clone, no `curl | bash`.

A clone always wins over the packaged copy, by content rather than by name, so
editing an agent here takes effect immediately and an empty directory left by a
failed clone cannot leave someone with no agents.

**Before a release, verify this by hand** — the cheap tests in
`tests/test_packaged_commons.py` guard the packaging config, but only a real
install exercises the whole path:

```bash
uv build --out-dir /tmp/d
FAKE=$(mktemp -d)
HOME=$FAKE PATH="$FAKE/.local/bin:$PATH" uv tool install --python 3.12 /tmp/d/*.whl
HOME=$FAKE PATH="$FAKE/.local/bin:$PATH" murmurent install
ls $FAKE/.claude/agents/ $FAKE/.claude/rules/ $FAKE/.claude/skills/
```

Expect 14 agents, 5 rules, 6 skills, a linked `CLAUDE.md`, and no broken
symlinks.

## The one-line install, and testing it

The install path users actually take is:

```bash
curl -fsSL https://raw.githubusercontent.com/hallettmiket/murmurent/main/scripts/bootstrap.sh | bash
```

To test it end to end without touching your own `~/.claude`, point `HOME` at a
scratch directory:

```bash
FAKE=$(mktemp -d)
HOME=$FAKE bash -c 'curl -fsSL https://raw.githubusercontent.com/hallettmiket/murmurent/main/scripts/bootstrap.sh | bash'
HOME=$FAKE PATH="$FAKE/.local/bin:$PATH" murmurent --version
```

Do this before any release that touches `scripts/`, `pyproject.toml` or the
allowlist. It is the only check that exercises what a stranger actually runs.
