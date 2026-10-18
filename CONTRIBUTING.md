# Contributing to Murmurent

How to get a change into Murmurent for good. The short version is in the
[README](README.md#making-a-change); this page gives each step in full, with the
reasons.

## Opening a pull request

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
material (institutional Slack identifiers, grant documents, internal notes)
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

## Changing the documentation website

Everything at <https://mikehallett.science/murmurent/> is built from the
Markdown files in [`docs/`](docs/). Editing one and merging it is all that's
needed: the site rebuilds itself.

Two things will trip you up. A new page has to be listed in
[`mkdocs.yml`](mkdocs.yml), or the build fails rather than quietly omitting it.
And the build treats a broken link as an error, so check yours before merging:

```bash
uv run --python 3.12 --extra docs mkdocs build --strict   # reports any problem
uv run --python 3.12 --extra docs mkdocs serve            # preview in a browser
```

This repository publishes its own copy of the site as a preview, separate from
the one users read; the public version updates when a new release is published.
