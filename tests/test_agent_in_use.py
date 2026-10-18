"""Which agent definition Claude Code will use, and where it came from (#186 step 1).

All state is under tmp_path: a fake commons, a fake ~/.claude/agents, a fake
vault, and a fake repo. Never the real ones.
"""

from __future__ import annotations

import subprocess

import pytest

from murmurent.core import agent_forks as af
from murmurent.core import agent_in_use as aiu

AGENT = "---\nname: {n}\ndescription: d\nfreeze: personal\ncategory: member\n---\nbody\n"


@pytest.fixture
def world(monkeypatch, tmp_path):
    commons = tmp_path / "repo" / "agents"
    commons.mkdir(parents=True)
    for n in ("blacksmith", "artist", "bookworm"):
        (commons / f"{n}.md").write_text(AGENT.format(n=n), encoding="utf-8")
    cc = tmp_path / "cc" / "agents"
    cc.mkdir(parents=True)
    vagents = tmp_path / "vault" / "agents"
    vagents.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPO_ROOT", str(tmp_path / "repo"))
    monkeypatch.setenv("MURMURENT_CC_AGENTS_DIR", str(cc))
    monkeypatch.setenv("MURMURENT_AGENT_FORKS_DIR", str(tmp_path / "vault" / "agent_forks"))
    monkeypatch.setenv("MURMURENT_PERSONAL_AGENTS_DIR", str(vagents))
    return {"tmp": tmp_path, "commons": commons, "cc": cc, "vagents": vagents}


def test_link_into_commons_is_centre(world):
    (world["cc"] / "artist.md").symlink_to(world["commons"] / "artist.md")
    use = aiu.which("artist")
    assert use.level == aiu.CENTRE and use.label == "centre version"


def test_fork_is_yours_and_reports_upstream_change(world):
    (world["cc"] / "blacksmith.md").symlink_to(world["commons"] / "blacksmith.md")
    af.fork_agent("blacksmith")
    assert aiu.which("blacksmith").level == aiu.YOURS
    (world["commons"] / "blacksmith.md").write_text(AGENT.format(n="blacksmith") + "new\n")
    use = aiu.which("blacksmith")
    assert use.level == aiu.YOURS and use.upstream_changed


def test_personal_agent_link_is_yours(world):
    (world["vagents"] / "helper.md").write_text(AGENT.format(n="helper"))
    (world["cc"] / "helper.md").symlink_to(world["vagents"] / "helper.md")
    assert aiu.which("helper").level == aiu.YOURS


def test_hand_written_file_is_local(world):
    (world["cc"] / "bookworm.md").write_text("mine\n")
    use = aiu.which("bookworm")
    assert use.level == aiu.LOCAL_FILE and "other machines" in use.detail


def test_missing_and_broken_link(world):
    assert aiu.which("bookworm").level == aiu.MISSING
    (world["cc"] / "artist.md").symlink_to(world["tmp"] / "elsewhere" / "artist.md")
    use = aiu.which("artist")
    assert use.level == aiu.BROKEN_LINK and "cannot use" in use.detail


def test_unreadable_link_target_is_broken_not_an_error(world):
    """#150: a link into another member's home folder that you cannot read."""
    locked = world["tmp"] / "other_home"
    (locked / "agents").mkdir(parents=True)
    (locked / "agents" / "artist.md").write_text("theirs\n")
    (world["cc"] / "artist.md").symlink_to(locked / "agents" / "artist.md")
    locked.chmod(0o000)
    try:
        assert aiu.which("artist").level == aiu.BROKEN_LINK
    finally:
        locked.chmod(0o755)


def test_repo_version_beats_yours(world):
    repo = world["tmp"] / "proj"
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    (world["cc"] / "blacksmith.md").symlink_to(world["commons"] / "blacksmith.md")
    (agents / "blacksmith.md").write_text("project blacksmith\n")
    assert aiu.which("blacksmith", repo=repo).level == aiu.LOCAL_FILE  # not committed
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", ".claude/agents/blacksmith.md"], check=True)
    assert aiu.which("blacksmith", repo=repo).level == aiu.PROJECT
    # outside the repo, the user's own link still applies
    assert aiu.which("blacksmith").level == aiu.CENTRE


def test_which_all_lists_every_known_name(world):
    (world["cc"] / "artist.md").symlink_to(world["commons"] / "artist.md")
    (world["cc"] / "extra.md").write_text("x\n")
    names = [u.name for u in aiu.which_all()]
    assert names == sorted(["artist", "blacksmith", "bookworm", "extra"])


def test_dashboard_card_reads_the_file_in_use(world, monkeypatch):
    """After a member's own copy changes the model, the card shows theirs."""
    from murmurent.dashboard import snapshot
    (world["cc"] / "blacksmith.md").symlink_to(world["commons"] / "blacksmith.md")
    af.fork_agent("blacksmith")
    own = af.forks_dir() / "blacksmith.md"
    own.write_text(own.read_text().replace("category: member", "category: member\nmodel: haiku"))
    af._install_working_copy(own, world["cc"] / "blacksmith.md")
    row = next(r for r in snapshot._agents() if r.name == "blacksmith")
    assert row.in_use_level == aiu.YOURS and row.model == "haiku"
