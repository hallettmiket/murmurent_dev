# Murmurent: development repository

This is where Murmurent is written. **To install and use Murmurent, go to
[hallettmiket/murmurent](https://github.com/hallettmiket/murmurent) instead.**

**▶ [Watch the 7-minute getting-started video](https://mikehallett.science/assets/videos/murmurent_getting_started.html)**

You need [git](https://git-scm.com/), [Claude Code](https://claude.com/claude-code)
and [uv](https://docs.astral.sh/uv/).

## Set up

```bash
git clone git@github.com:hallettmiket/murmurent_dev.git ~/repos/murmurent_dev
cd ~/repos/murmurent_dev
uv tool install --python 3.12 -e .   # install Murmurent from this folder
murmurent install                    # connect it to Claude Code
murmurent doctor                     # check it worked
```

Murmurent now runs from this folder. An edit to an agent takes effect in the
next Claude Code session, with no command to run.

## Update

```bash
git pull
murmurent install
```

## Making a change

```bash
git checkout -b fix/<issue-number>-<short-name>   # 1. work on a branch, not main
# 2. make the change, and add a test in tests/
uv run --python 3.12 --extra dev pytest -q        # 3. check nothing broke
python3 release/check_allowlist.py                #    and that new files are classified
git push -u origin HEAD                           # 4. upload the branch
gh pr create --fill --base main                   #    and ask for review
```

Each step in full, with the reasons: [CONTRIBUTING.md](CONTRIBUTING.md).

## More

| I want to… | Read |
|---|---|
| understand how Murmurent fits together | [CLAUDE.md](CLAUDE.md) |
| fix an awkward install, or publish a release | [DEVELOPING.md](DEVELOPING.md) |
| change what users see on GitHub | [release/README_public.md](release/README_public.md), not this file |
| change the documentation website | the files in [docs/](docs/); see [CONTRIBUTING.md](CONTRIBUTING.md#changing-the-documentation-website) |
| report a problem or ask for a feature | [open an issue](https://github.com/hallettmiket/murmurent_dev/issues) |

---

[Code of Conduct](CODE_OF_CONDUCT.md). Apache-2.0 ([LICENSE](LICENSE)).
Mike Hallett, michael.hallett@uwo.ca
