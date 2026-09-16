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

Murmurent occupies three repositories on GitHub. The division explains
several of the procedures below.

- **[`murmurent_dev`](https://github.com/hallettmiket/murmurent_dev) — this
  repository, which is private.** Contains all development: the full change
  history, issues and proposals, the test suite, and one institution's private
  settings.
- **[`murmurent`](https://github.com/hallettmiket/murmurent) — the public
  release.** What users download and install. It contains released versions
  only: no development history, no discussion, no private settings. It is
  rebuilt from murmurent_dev at each release.
- **[`murmurent_public`](https://github.com/hallettmiket/murmurent_public) — the
  public directory.** The institutions running Murmurent and how to request to
  join one, plus an index of shared workflows (termed choreographies in
  Murmurent) that anyone can install.

Changes propagate in one direction only. They are made in murmurent_dev and
copied to the release repository when a new version is published. Nothing is
committed directly to the release repository.

## Getting set up

Requires [git](https://git-scm.com/),
[Claude Code](https://claude.com/claude-code) and
[uv](https://docs.astral.sh/uv/). Python need not be installed separately; `uv`
obtains the required version.

```bash
git clone git@github.com:hallettmiket/murmurent_dev.git ~/repos/murmurent_dev
cd ~/repos/murmurent_dev
uv tool install --python 3.12 -e .   # install Murmurent from this folder
murmurent install                    # connect it to Claude Code
murmurent doctor                     # check it worked
```

Murmurent now runs from this folder. The next Claude Code session uses the
agents defined here, and edits to an agent take effect immediately without
rerunning any command.

The `murmurent doctor` command can be used whenever something looks
wrong: it checks the whole installation and describes, for each problem it finds,
a possible fix.

DO NOT install with `scripts/bootstrap.sh`. That installs
the *public release*, so your changes here would have no effect on anything.
[`DEVELOPING.md`](DEVELOPING.md) covers the more awkward situations, including
what to do if you already had Murmurent installed a different way.


## Making a folder Murmurent-ready

The agents are defined in this repository, in [`agents/`](agents/) — one
Markdown file per agent. Installation links that set into your home directory
once, and Claude Code reads it in **every** folder on the machine. All agents
are therefore available in all folders, and making a folder ready does not
affect agent availability. An agent can be redefined for a single folder; see
[the documentation](https://hallettmiket.github.io/murmurent/ready_vs_projects/).

**Making a folder Murmurent-ready means exactly four things:**

1. The **sensitive-data check** operates in that folder. Outbound content —
   web searches, shell commands, fetched URLs — is scanned for personal
   identifiers, which are removed before transmission. The check performs no
   action in folders that are not ready.
2. The folder can be marked as holding sensitive data, by adding one line to
   the `.murmurent.yaml` file described below:
   ```yaml
   sensitivity: clinical
   ```
3. The activity log records the originating folder for each entry.
4. The folder becomes eligible to join a Murmurent **project**, which is a
   distinct concept from a ready folder and is documented
   [here](https://hallettmiket.github.io/murmurent/ready_vs_projects/). Making
   a folder ready does not create a project.

Apply this to any folder holding research data, and to all folders holding
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

Neither command requires options. The folder must reside under `~/repos/`.
Existing contents are not modified: files, git history and any existing
`.claude/` settings are preserved. `adopt` adds a `.murmurent.yaml` file
recording the setup, a `CLAUDE.md` template, and VS Code settings. Commit the
first two.


## Updating your copy of murmurent_dev

Two commands apply other contributors' changes to your machine: the first
downloads them, the second installs them.

```bash
cd ~/repos/murmurent_dev
git pull
murmurent install
```

Run `murmurent install` with no options, as above. It performs the complete
update and is safe to run when nothing has changed.

Two conditional additions:

- If `pyproject.toml` changed, also run
  `uv tool install --python 3.12 --reinstall -e .`
- If the installation appears incorrect afterwards, run `murmurent doctor`,
  which reports each problem and the command that corrects it.

Changes to the text of an existing agent or rule take effect without any
command. A newly added agent requires the `murmurent install` above. No
command is required in individual folders.

[`DEVELOPING.md`](DEVELOPING.md) covers the awkward cases, including a copy of
this folder cloned before September 2026, where `git pull` fails.


## Pushing your changes to murmurent_dev: opening a pull request

Your edits take effect on your own machine as soon as they are saved.
Distributing them is a separate procedure: push the work to GitHub and open a
**pull request**, which proposes your changes for inclusion in the shared copy
of murmurent_dev.

Six steps, with each command given in full.

**1. Record the problem as an issue**, if the change is one other users
would notice. Issues are filed on the murmurent_dev GitHub page: open
<https://github.com/hallettmiket/murmurent_dev>, select the **Issues** tab,
then **New issue**. Three templates are offered: a defect report, a feature
request, and feedback from first-time use. Each template lists the information
required; complete the fields that apply. This step may be omitted for
corrections to typography.

**2. Work on a branch rather than on `main`.** A branch is a separate line
of development, so incomplete work does not affect other users. `main` is the
shared version, and releases are built from it.

```bash
git checkout -b fix/dashboard-crash      # any short name describing the change
```

Branch names are prefixed `fix/` for a correction, `feat/` for new
functionality, or `docs/` for documentation. When the change resolves a
numbered issue, include the number: `fix/130-dashboard-crash`.

**3. Make the change and add a test.** A test is code that verifies the
change behaves as intended and continues to verify it in every subsequent test
run, which prevents later modifications from reverting it. Add it to
[`tests/`](tests/), following the structure of the existing test closest to
what you changed.

Two further requirements: follow the style of the surrounding code, specified
in [`docs/style/code-style.md`](docs/style/code-style.md); and if the change
alters how Murmurent is used, record it in [`CHANGELOG.md`](CHANGELOG.md) and
update the document describing that feature.

**4. Classify any new file as publishable or not.** This requirement is
specific to Murmurent.

The public release is constructed by examining every file in murmurent_dev and
retaining only those listed as publishable in
[`release/allowlist.yaml`](release/allowlist.yaml). This prevents private
material — institutional Slack identifiers, grant documents, internal notes —
from being published inadvertently.

**A file absent from that list halts the next release**, by design: an
unclassified file represents a decision not yet made. If you added a file, add
its path to [`release/allowlist.yaml`](release/allowlist.yaml) under `ship:`
(publishable) or `withhold:` (must remain private), with a comment stating the
reason.

**5. Verify that nothing else is broken.** Two commands, both of which only
report results:

```bash
uv run --python 3.12 --extra dev pytest -q     # run every test
python3 release/check_allowlist.py             # every file is accounted for (step 4)
```

The first runs the full test suite, approximately 2,300 tests, in about two
minutes. The expected result is `passed` with no `failed`. A small number of
tests depend on machine configuration rather than on the code; if a failure
appears unrelated to your change, run the same command on an unmodified copy of
`main` to determine whether it was failing beforehand.

**6. Submit the change for review.** Commit the work and upload the branch
to GitHub:

```bash
git add -A
git commit -m "Fix the dashboard crash when a project has no members"
git push -u origin fix/dashboard-crash
```

Then open a pull request, which proposes merging the branch into `main` and
provides the venue for review:

```bash
gh pr create --fill --base main
```

Say what you changed, why, and what you ran to check it. Once someone approves
it, merging the pull request on GitHub puts your change into `main`, and it
reaches everyone else the next time they update.


## Publishing a new version for everyone to download

This is how the code in this folder becomes the version that other people
install. Only the maintainer does it, so skip this section unless that is you.

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
