# Murmurent — development repository

This is the development version of Murmurent. **If you are a user of Murmrent and not 
a developer, go to [hallettmiket/murmurent](https://github.com/hallettmiket/murmurent), 
which has the installation instructions, or read the
[documentation](https://hallettmiket.github.io/murmurent/).

Murmurent is shared AI infrastructure for research groups: a set of agents,
rules and workflows that a lab, a core facility or a whole research centre can
use in common, so that groups can work independently but pool their agents,
their data and their accumulated knowledge when it helps.

| I want to… | Where to go |
|---|---|
| install and use Murmurent | [hallettmiket/murmurent](https://github.com/hallettmiket/murmurent) |
| read the documentation | <https://hallettmiket.github.io/murmurent/> |
| report a problem, or ask for something new | [open an issue here](https://github.com/hallettmiket/murmurent_dev/issues) |
| change how Murmurent works | keep reading |

Before changing anything, read [`CLAUDE.md`](CLAUDE.md) — the description of
Murmurent that every Claude Code session loads automatically, and the shortest
explanation of how the pieces fit together.

## Why there are three repositories

Murmurent is spread over three places on GitHub, which is worth understanding
before you start, because it explains most of the procedures further down.

- **[`murmurent_dev`](https://github.com/hallettmiket/murmurent_dev) — this
  one, and it is private.** All the development happens here: the full history
  of every change, the discussion of problems and proposals, the automatic
  tests, and one institution's own private settings.
- **[`murmurent`](https://github.com/hallettmiket/murmurent) — the public
  release.** This is what people download and install. It holds finished
  versions only, with none of the history or discussion and none of the private
  settings, and it is built from this repository whenever a new version is
  published.
- **[`murmurent_public`](https://github.com/hallettmiket/murmurent_public) — the
  public directory.** A list of which institutions are running Murmurent and
  how to ask to join one, plus an index of shared workflows (termed choreographies in Murmurent) anyone can install.

Changes only ever travel one way: they are made here, and they reach the public
release when someone publishes a new version. Nothing is ever committed
directly to the release repo.

## Getting set up

You need [git](https://git-scm.com/),
[Claude Code](https://claude.com/claude-code) and
[uv](https://docs.astral.sh/uv/). You do not need to install Python: `uv`
fetches the right version if your machine hasn't got it.

```bash
git clone git@github.com:hallettmiket/murmurent_dev.git ~/repos/murmurent_dev
cd ~/repos/murmurent_dev
uv tool install --python 3.12 -e .   # install Murmurent from this folder
murmurent install                    # connect it to Claude Code
murmurent doctor                     # check it worked
```

Murmurent now runs from this folder, so your next Claude Code session uses the 
agents in it, and any edit you make to an agent takes effect immediately with nothing 
to rerun.

The `murmurent doctor` command can be used whenever something looks
wrong: it checks the whole installation and describes, for each problem it finds,
a possible fix.

DO NOT install with `scripts/bootstrap.sh`. That installs
the *public release*, so your changes here would have no effect on anything.
[`DEVELOPING.md`](DEVELOPING.md) covers the more awkward situations, including
what to do if you already had Murmurent installed a different way.


## Making a folder Murmurent-ready

Murmurent's agents are defined in this folder, in [`agents/`](agents/) — one
Markdown file per agent. When you installed Murmurent it linked that whole set
into your home directory, once, and Claude Code reads it in **every** folder on
your machine. So the agents are already available everywhere, and making a
folder ready is not what gives you them. (An agent can be redefined for one
folder only, which is occasionally useful and described in
[the documentation](https://hallettmiket.github.io/murmurent/ready_vs_projects/).)

**Making a folder Murmurent-ready means exactly four things:**

1. Murmurent's check on **sensitive data** starts running there. Before
   anything leaves your machine — a web search, a command, a fetch — it is
   scanned for personal identifiers and they are removed. In a folder that is
   not ready, this check does nothing.
2. The folder can be marked as holding sensitive data, by adding one line to
   the `.murmurent.yaml` file described below:
   ```yaml
   sensitivity: clinical
   ```
3. Murmurent's activity log records which folder each entry came from.
4. The folder becomes eligible to be joined to a Murmurent **project** — a
   separate concept from a ready folder, covered in
   [the documentation](https://hallettmiket.github.io/murmurent/ready_vs_projects/).
   Making a folder ready does not create one.

Do this for any folder holding research data, and certainly for any holding
sensitive data.

### How

Ask what state the folder is in:

```bash
murmurent repo status ~/repos/<folder>
```

Then run the command beside your verdict:

| Verdict | What it means | What to run |
|---|---|---|
| `✗ no such folder` | the path is wrong | check the path |
| `✗ not tracked by git` | the folder exists but is not a git repository | `git -C ~/repos/<folder> init`, then the next row |
| `• not set up yet` | a git repository Murmurent has never set up | `murmurent repo adopt ~/repos/<folder>` |
| `± half set up` | an earlier attempt stopped partway | the same `adopt` command; it completes the setup |
| `✓ ready`, older version | set up by an earlier version of Murmurent | `murmurent repo upgrade ~/repos/<folder>` |
| `✓ ready`, current | nothing to do | open Claude Code in it |

No options are needed on either command. The folder must be somewhere under
`~/repos/`, and nothing already in it is altered — your files, your git history
and your own `.claude/` settings are left exactly as they are. What `adopt`
adds is a `.murmurent.yaml` file recording the setup, a starter `CLAUDE.md`,
and VS Code settings. Commit the first two.


## Updating your copy of murmurent_dev

Other people are changing Murmurent too. Two commands bring their work onto
your machine: the first downloads it, the second applies it.

```bash
cd ~/repos/murmurent_dev
git pull
murmurent install
```

Run `murmurent install` with nothing after it, as above; that form does the
whole job, and it is safe to run when nothing has changed.

Two additions, both occasional:

- If `pyproject.toml` changed, also run
  `uv tool install --python 3.12 --reinstall -e .`
- If anything looks wrong afterwards, run `murmurent doctor`, which names each
  problem and the command that fixes it.

That is all. Reworded agents and rules reach you with nothing run at all; a
brand-new agent arrives with the `murmurent install` above. There is never
anything to run folder by folder.

[`DEVELOPING.md`](DEVELOPING.md) covers the awkward cases, including a copy of
this folder cloned before September 2026, where `git pull` fails.


## I changed something. How do I make it part of Murmurent?

Your edits already work on your own machine — that happened the moment you
saved the file. This section is about the separate job of getting the change
into Murmurent itself, so that everyone else gets it too.

Six steps. Nothing here is unusual if you have contributed to a shared project
before; if you haven't, the commands are all written out.

**1. Describe the problem on GitHub first**, if the change is something other
people would notice. Go to
[the issues page](https://github.com/hallettmiket/murmurent_dev/issues) and
click *New issue*. You'll be offered a few fill-in-the-blanks forms — one for
"something is broken", one for "Murmurent should be able to do X", one for
notes from someone trying Murmurent out for the first time. They exist so you
don't have to guess what information is useful; fill in what you can and leave
the rest. Skip this step for a typo fix.

**2. Work on a branch, not on `main`.** A branch is your own copy of the
project to change freely, so that unfinished work never affects anyone else.
`main` is the version everyone uses, and releases are made from it.

```bash
git checkout -b fix/dashboard-crash      # any short name describing the change
```

By convention the name starts with `fix/` for a repair, `feat/` for something
new, or `docs/` for writing. If you're fixing a numbered issue, include the
number: `fix/130-dashboard-crash`.

**3. Make the change, and add a test for it.** A test is a small piece of code
that checks your change does what you intended, and that keeps checking it
forever, so nobody accidentally undoes your work later. Put it in
[`tests/`](tests/) next to the existing ones and copy the shape of whichever is
closest to what you changed.

Two other things while you're there: write your code in the same style as the
code around it (the conventions are written down in
[`docs/style/code-style.md`](docs/style/code-style.md) if you want them
explicitly), and if your change affects how someone *uses* Murmurent, say so in
[`CHANGELOG.md`](CHANGELOG.md) and update whichever document explains that
feature.

**4. If you added a new file, say whether it's allowed to be published.** This
one is specific to Murmurent, so it needs a word of explanation.

Murmurent exists in two copies: this private working one, and a public one that
strangers download. The public copy is built by going through every file here
and keeping only the files that [`release/allowlist.yaml`](release/allowlist.yaml)
lists as publishable. That's how private things — one lab's Slack IDs, grant
documents, internal notes — are kept from being published by accident.

The consequence for you: **a file that isn't listed in that file stops the next
release.** Deliberately, because a file nobody has thought about is a decision
nobody has made. So if you added a file, open
[`release/allowlist.yaml`](release/allowlist.yaml) and add its path under
`ship:` (safe to publish) or `withhold:` (must stay private), with a short
comment saying why.

**5. Check that you haven't broken anything else.** Two commands, both of which
just print results and change nothing:

```bash
uv run --python 3.12 --extra dev pytest -q     # run every test
python3 release/check_allowlist.py             # every file is accounted for (step 4)
```

The first runs the whole test suite, a few thousand checks, in about two
minutes. You want it to end in `passed` with no `failed`. A handful of tests
depend on how a particular machine is configured rather than on the code, so if
something fails and looks unrelated to your change, run the same command on a
fresh copy of `main` and compare — that tells you whether it was already
failing before you started.

**6. Send it to be reviewed and merged.** First save your work and upload your
branch to GitHub:

```bash
git add -A
git commit -m "Fix the dashboard crash when a project has no members"
git push -u origin fix/dashboard-crash
```

Then open a **pull request** — a request for your branch to be folded into
`main`. It's where the change gets discussed before it becomes permanent:

```bash
gh pr create --fill --base main
```

Say what you changed, why, and what you ran to check it. Once someone approves
it, merging the pull request on GitHub puts your change into `main`, and it
reaches everyone else the next time they update.


## Publishing a new version for everyone to download

This is how the code in this folder becomes the version that other people
install. It is Mike's job rather than a contributor's, so skip this section
unless you are the one doing it.

Everything here happens twice over, in two places, so it helps to know the
shape before the steps. This folder is where Murmurent is written, and it is
private: it holds years of history and one lab's private settings. The
[public repository](https://github.com/hallettmiket/murmurent) is what people
download, and it holds nothing but finished versions — one entry per release,
no history. Publishing means building a clean copy of this folder, with every
private file removed, and putting it there. The script does the removing, by
consulting the list of publishable files described in step 4 of the previous
section.

The full procedure, including the one-time PyPI account setup and the checks to
run by hand beforehand, is in [`DEVELOPING.md`](DEVELOPING.md). In outline:

1. **Choose the new version number** and write it in
   `src/murmurent/__init__.py`, which is the only place it is recorded.
   Murmurent numbers versions by date — `2026.9.8` is the eighth release of
   September 2026. [`docs/versioning.md`](docs/versioning.md) says when a change
   deserves a new number and when it doesn't.
2. **Write what changed** in [`CHANGELOG.md`](CHANGELOG.md), for the people who
   will read it to decide whether to update.
3. **Update the instructions users read**, in
   [`release/README_public.md`](release/README_public.md), if this release
   changes anything they do. Do this *before* step 4 — the publishing script
   takes that file from the saved snapshot, not from your working copy.
4. **Save and label this version**, so you can always come back to exactly the
   code that was published:
   ```bash
   git commit -am "Release 2026.9.9"
   git tag -a v2026.9.9 -m "Release 2026.9.9"
   git push origin main v2026.9.9
   ```
5. **Build and publish the public copy.** Run it with `--dry-run` first, which
   shows you what would be published and sends nothing:
   ```bash
   bash release/make_release.sh v2026.9.9 https://github.com/hallettmiket/murmurent.git --dry-run
   bash release/make_release.sh v2026.9.9 https://github.com/hallettmiket/murmurent.git
   ```
   It refuses to run at all if any file is unaccounted for, or if a file due to
   be published mentions something private. When it finishes it prints a long
   code identifying the exact version of this folder it built from — paste that
   into the release notes in the next step, because it is the only record of
   which private version a public release came from.
6. **Announce it on the public repository**: on its GitHub page, *Releases* →
   *Draft a new release*, choose the tag from step 4, paste in the changelog
   entry and the code from step 5. Publishing that page automatically uploads
   the new version to PyPI, which is where `uv tool install murmurent` gets it
   from.

## Which README to edit

There are two front pages, because the two repositories have different readers,
and it is easy to edit the wrong one.

- **This file** is the front page of the private development repository — what
  you are reading. It is for people working on Murmurent, and it is never
  published.
- **[`release/README_public.md`](release/README_public.md)** is the front page
  users see. Publishing copies it into the public repository as its `README.md`,
  and it doubles as the description on Murmurent's PyPI page.

So install instructions, the identity and membership steps, and centre setup
are edited in `release/README_public.md`; anything for developers is edited
here. And if you ever edit the README in the public repository directly, your
edit is thrown away by the next release, which rebuilds that file from this
folder.


## Changing the documentation website

Everything at <https://hallettmiket.github.io/murmurent/> is built from the
Markdown files in [`docs/`](docs/). Editing one and merging it is all that's
needed — the site rebuilds itself.

Two things will trip you up. A new page has to be listed in
[`mkdocs.yml`](mkdocs.yml), or the build fails rather than quietly omitting it.
And the build treats a broken link as an error, so check yours before merging:

```bash
uv run --python 3.12 --extra docs mkdocs build --strict   # reports any problem
uv run --python 3.12 --extra docs mkdocs serve            # preview in a browser
```

This repository publishes its own copy of the site as a preview, separate from
the one users read; the public version updates when a new release is published.


## Conduct, licence, authors

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
Murmurent is Apache-2.0 ([`LICENSE`](LICENSE)).

Mike Hallett &mdash; michael.hallett@uwo.ca
