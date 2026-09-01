# Working on murmurent itself

**This file is in the development repository only.** It is not part of a
release. If you are here to *use* murmurent, you want
[`README.md`](README.md) instead, and the public repo at
[hallettmiket/murmurent](https://github.com/hallettmiket/murmurent).

## The two repositories

| | |
|---|---|
| [`hallettmiket/murmurent`](https://github.com/hallettmiket/murmurent) | **release only.** One commit per release, no development history, no issues, no PRs. This is what people clone and install. |
| [`hallettmiket/murmurent_dev`](https://github.com/hallettmiket/murmurent_dev) | **development.** All history, issues, PRs, branches and build notes. You are here. |

Code flows one way, dev to public, and only at a release. Nothing is ever
committed directly to the public repo.

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

Do **not** run `scripts/bootstrap.sh` for development: it clones the *public*
repo, which has no history and no tests.

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
PYTHONPATH=src python3 -m pytest -q          # the suite
python3 release/check_allowlist.py           # every tracked file classified
```

The allowlist check matters more than it looks. **A file you add that matches
no rule stops the next release**, deliberately: a path nobody classified is a
decision nobody made. Classify it in `release/allowlist.yaml` in the same
commit that adds it.

## Cutting a release

1. Decide the version. CalVer `YYYY.M.MICRO`, one source of truth in
   `src/murmurent/__init__.py`. See [`docs/versioning.md`](docs/versioning.md)
   for when to bump and when not to.
2. Update `CHANGELOG.md`.
3. Commit, then tag: `git tag -a v2026.9.2 -m "..." && git push origin v2026.9.2`
4. Export:

   ```bash
   bash release/make_release.sh v2026.9.2 https://github.com/hallettmiket/murmurent.git
   ```

   Run it with `--dry-run` first if you want to see the tree without pushing.
   It refuses to proceed unless the allowlist classifies everything and no
   shipping file names a private repo, a grant document or a Slack ID.
5. It prints the **dev SHA**. Put that in the GitHub Release notes. Two repos
   means two tags for one version, and that line is the only thing connecting a
   public release back to the commit it came from.
6. Create the Release on the public repo. Publishing it triggers
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
