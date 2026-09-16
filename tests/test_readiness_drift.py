"""One commons, and a repo that says when it has fallen behind it.

Three defects motivated this file, and each test names the one it pins.

1. ``repo adopt``/``repo upgrade`` resolved the commons through
   ``core.repo.murmurent_repo_root()`` — hardcoded ``~/repos/murmurent`` —
   while ``setup``/``install``/``doctor`` used ``core.commons.commons_root()``.
   On a machine holding a release clone and a development one they disagreed,
   so ``doctor`` truthfully reported reading the dev clone while a repo adopted
   seconds earlier was linked into the release clone. An agent edited in the
   clone under development was live in ``~/.claude/agents/`` and absent from the
   repo, with no error anywhere.

2. Nothing told anyone. A new agent in an upgrade has no symlink in an existing
   repo, and nothing retro-fits one; the repo simply does not have that agent
   and never says so.

3. The first automatic ``repo upgrade --all`` at the end of ``install``
   stamped a marker onto a years-old repo whose only bootstrap was a legacy
   ``CHARTER.md``, leaving untracked files in a repo whose owner had asked for
   nothing. An upgrade must not quietly become an adoption.
"""

from __future__ import annotations

import io
import json

import pytest

from murmurent.commands import repo_cmd
from murmurent.core import repo_ready
from murmurent.hooks import context_inject


def _fake_commons(root, agents=("oracle", "bookworm", "blacksmith")):
    """A directory that passes ``commons._looks_like_commons``."""
    for d in ("agents", "rules", "skills"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for a in agents:
        (root / "agents" / f"{a}.md").write_text(f"# {a}\n", encoding="utf-8")
    return root


def _git_repo(path):
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return path


@pytest.fixture
def two_clones(monkeypatch, tmp_path):
    """A dev clone (installed) and a release clone at the conventional path.

    The release clone gets an extra agent so a test can tell which one a
    symlink resolved to by name as well as by path.
    """
    dev = _fake_commons(tmp_path / "murmurent_dev")
    rel = _fake_commons(tmp_path / "murmurent", agents=("oracle", "legacy_only"))
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(dev))
    monkeypatch.setenv("MURMURENT_REPO_ROOT", str(rel))
    return dev, rel


# ---------------------------------------------------------------------------
# 1. one resolver
# ---------------------------------------------------------------------------


def test_adopt_links_into_the_commons_you_are_running(two_clones, tmp_path):
    """Not into whatever happens to sit at the conventional repo path."""
    dev, rel = two_clones
    repo = _git_repo(tmp_path / "repos" / "x1")

    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])

    link = repo / ".claude" / "agents" / "oracle.md"
    assert link.is_symlink()
    target = link.readlink()
    assert dev in target.parents, f"linked into {target}, expected under {dev}"
    assert rel not in target.parents


def test_upgrade_all_agents_takes_the_roster_from_the_running_commons(
    two_clones, tmp_path
):
    """``--all-agents`` must enumerate the same commons the links point into.

    The two used to be read from different roots, so a repo could be given a
    roster from one clone and symlinks into another.
    """
    dev, rel = two_clones
    repo = _git_repo(tmp_path / "repos" / "x2")
    repo_ready.make_ready(repo, lab="mh", agents=[])

    repo_ready.upgrade(repo, add_agents=None, all_agents=True)

    linked = {p.stem for p in (repo / ".claude" / "agents").glob("*.md")}
    assert linked == {"oracle", "bookworm", "blacksmith"}
    assert "legacy_only" not in linked, "roster came from the wrong clone"


# ---------------------------------------------------------------------------
# 2. the repo says when it has fallen behind
# ---------------------------------------------------------------------------


def test_notice_is_silent_when_the_repo_is_current(two_clones, tmp_path, monkeypatch):
    """The half that matters most: a notice that always fires is ignored."""
    repo = _git_repo(tmp_path / "repos" / "x3")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle", "bookworm", "blacksmith"])
    monkeypatch.chdir(repo)

    assert context_inject._readiness_notice() is None


def test_an_agent_absent_from_the_repo_is_not_reported(two_clones, tmp_path, monkeypatch):
    """Because it is still perfectly usable there.

    ``murmurent setup`` links the whole commons into ``~/.claude/agents/``,
    which Claude Code loads in every directory, so an agent missing from a
    repo's own ``.claude/agents/`` costs the user nothing. This hook used to
    announce it as "2 commons agent(s) are not linked into this repo", which
    read as "unavailable here" — false — and sent the reader to run a command
    whose effect they could not observe.
    """
    repo = _git_repo(tmp_path / "repos" / "x4")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])   # bookworm, blacksmith absent
    monkeypatch.chdir(repo)

    assert context_inject._readiness_notice() is None


def test_notice_flags_a_repo_following_a_different_commons(
    two_clones, tmp_path, monkeypatch
):
    """The state that makes an edit appear to do nothing."""
    dev, rel = two_clones
    repo = _git_repo(tmp_path / "repos" / "x5")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle", "bookworm", "blacksmith"])
    # Re-point one link at the other clone, as a pre-fix adopt would have.
    link = repo / ".claude" / "agents" / "oracle.md"
    link.unlink()
    link.symlink_to(rel / "agents" / "oracle.md")
    monkeypatch.chdir(repo)

    notice = context_inject._readiness_notice()

    assert notice is not None
    assert str(rel) in notice
    assert "not the murmurent you are running" in notice


def test_notice_is_found_from_a_subdirectory(two_clones, tmp_path, monkeypatch):
    """Sessions open inside ``exp/07_thing/``, not at the repo root."""
    dev, rel = two_clones
    repo = _git_repo(tmp_path / "repos" / "x6")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])
    link = repo / ".claude" / "agents" / "oracle.md"
    link.unlink()
    link.symlink_to(rel / "agents" / "oracle.md")
    deep = repo / "exp" / "07_thing"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    assert context_inject._readiness_notice() is not None


def test_no_notice_outside_a_ready_repo(two_clones, tmp_path, monkeypatch):
    plain = tmp_path / "repos" / "not_ready"
    plain.mkdir(parents=True)
    monkeypatch.chdir(plain)

    assert context_inject._readiness_notice() is None


def test_a_bare_version_bump_alone_is_not_reported(two_clones, tmp_path, monkeypatch):
    """``needs_upgrade`` is true after every release; the notice is not.

    A repo whose roster is complete but whose ``bootstrap_version`` lags must
    stay quiet. Reporting it would put a line in front of the user on every
    prompt after every upgrade, including upgrades that changed nothing for
    them, which is how a warning becomes furniture.
    """
    repo = _git_repo(tmp_path / "repos" / "x7")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])
    marker = repo / ".murmurent.yaml"
    marker.write_text(
        marker.read_text(encoding="utf-8").replace(
            repo_ready._version(), "2000.1.0"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    assert repo_ready.readiness(repo).needs_upgrade is True
    assert context_inject._readiness_notice() is None


def test_notice_never_raises_on_a_broken_repo(two_clones, tmp_path, monkeypatch):
    """This runs on every prompt submission; an exception would block it."""
    repo = _git_repo(tmp_path / "repos" / "x8")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])
    agents = repo / ".claude" / "agents"
    (agents / "dangling.md").symlink_to(tmp_path / "gone" / "nowhere.md")
    monkeypatch.chdir(repo)

    context_inject._readiness_notice()  # must not raise


def test_the_hook_emits_the_notice_with_no_project(two_clones, tmp_path, monkeypatch):
    """A merely-ready repo has no CHARTER, so the project block is absent.

    The notice has to travel on its own, or the people most likely to be
    behind — anyone whose repo was never made a project — never hear about it.
    """
    dev, rel = two_clones
    repo = _git_repo(tmp_path / "repos" / "x9")
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])
    link = repo / ".claude" / "agents" / "oracle.md"
    link.unlink()
    link.symlink_to(rel / "agents" / "oracle.md")
    monkeypatch.chdir(repo)

    out = io.StringIO()
    rc = context_inject.main(stdin=io.StringIO('{"prompt": "hi"}'), stdout=out)

    assert rc == 0
    ctx = (json.loads(out.getvalue()).get("hookSpecificOutput") or {})[
        "additionalContext"
    ]
    assert "murmurent readiness" in ctx
    assert "murmurent project context" not in ctx


# ---------------------------------------------------------------------------
# 3. an automatic upgrade is not an adoption
# ---------------------------------------------------------------------------


def test_marker_only_skips_a_legacy_charter_repo(two_clones, tmp_path, monkeypatch):
    """What ``install`` runs must not adopt anything.

    A repo carrying only a legacy ``CHARTER.md`` is migrated by a ``repo
    upgrade --all`` that a person typed. Run from ``install`` it must be left
    alone: stamping a marker on a repo nobody adopted leaves untracked files in
    someone's working tree as a side effect of upgrading murmurent.
    """
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    repos = tmp_path / "repos"

    legacy = _git_repo(repos / "old_project")
    (legacy / "CHARTER.md").write_text("---\nlab: mh\n---\n# old\n", encoding="utf-8")

    ready = _git_repo(repos / "already_ready")
    repo_ready.make_ready(ready, lab="mh", agents=["oracle"])

    rc = repo_cmd.cmd_upgrade(path=None, all_repos=True, add_agents_csv=None,
                              all_agents=False, quiet=True, marker_only=True)

    assert rc == 0
    assert not (legacy / ".murmurent.yaml").exists(), \
        "install stamped a marker on a repo nobody adopted"
    assert not (legacy / ".vscode").exists()
    assert (ready / ".murmurent.yaml").exists()


def test_a_typed_upgrade_all_still_migrates_a_legacy_repo(
    two_clones, tmp_path, monkeypatch
):
    """The migration path must survive the fix above."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    legacy = _git_repo(tmp_path / "repos" / "old_project")
    (legacy / "CHARTER.md").write_text("---\nlab: mh\n---\n# old\n", encoding="utf-8")

    rc = repo_cmd.cmd_upgrade(path=None, all_repos=True, add_agents_csv=None,
                              all_agents=False, quiet=True)

    assert rc == 0
    assert (legacy / ".murmurent.yaml").is_file()
    assert (legacy / "CHARTER.md").is_file(), "the CHARTER must be preserved"


# ---------------------------------------------------------------------------
# 4. one command to set a folder up with the agents
# ---------------------------------------------------------------------------


def test_adopt_all_agents_links_every_agent(two_clones, tmp_path):
    """``--all-agents`` exists so nobody has to invent an agent list.

    Without it, adopt takes ``--agents a,b,c`` or links nothing at all, so the
    documentation had to tell a newcomer to type a specific pair of agent names
    for no stated reason, and a bare adopt left an empty ``.claude/agents/``
    that only showed up later as a missing agent.
    """
    dev, _ = two_clones
    repo = _git_repo(tmp_path / "_repos" / "x10")   # cmd_adopt requires the repos root

    rc = repo_cmd.cmd_adopt(path=str(repo), lab="mh", agents_csv=None,
                            host_name="local", all_agents=True)

    assert rc == 0
    linked = {p.stem for p in (repo / ".claude" / "agents").glob("*.md")}
    assert linked == {"oracle", "bookworm", "blacksmith"}


def test_adopt_all_agents_fails_loudly_with_no_commons(tmp_path, monkeypatch):
    """Better than silently making a repo ready with no agents."""
    import click

    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(tmp_path / "nothing_here"))
    repo = _git_repo(tmp_path / "_repos" / "x11")

    with pytest.raises(click.ClickException):
        repo_cmd.cmd_adopt(path=str(repo), lab="mh", agents_csv=None,
                           host_name="local", all_agents=True)


def test_status_verdicts_avoid_git_jargon():
    """The verdicts are read by researchers, not by git users.

    "• clone" named git's concept rather than the reader's situation and gave
    no hint of what to do next; the internal verdict keys are unchanged, so the
    dashboard and adopt.py are unaffected.
    """
    shown = repo_cmd._GLYPH
    assert "clone" not in shown["plain clone"]
    assert shown["plain clone"] == "• not set up yet"
    assert "git" in shown["not a git repo"]
