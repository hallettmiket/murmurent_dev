"""Agent versions at five levels, and switching an agent off per project (#186).

Everything is in tmp_path: a fake commons, ~/.claude/agents, vault, lab
management repo and project repo. Never the real ones.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest
from click.testing import CliRunner

from murmurent.core import agent_forks as af
from murmurent.core import agent_levels as lv

AGENT = "---\nname: {n}\ndescription: {d}\nfreeze: {f}\ncategory: member\n---\nbody\n"


def _write(path, name, desc="d", freeze="personal"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(AGENT.format(n=name, d=desc, f=freeze), encoding="utf-8")
    return path


@pytest.fixture
def world(monkeypatch, tmp_path):
    commons = tmp_path / "repo" / "agents"
    for n in ("blacksmith", "artist"):
        _write(commons / f"{n}.md", n, "centre")
    _write(commons / "security_guard.md", "security_guard", "centre", freeze="frozen")
    cc = tmp_path / "cc" / "agents"
    cc.mkdir(parents=True)
    vault = tmp_path / "vault"
    lab = tmp_path / "lab-mgmt"
    (lab / "agents").mkdir(parents=True)
    repo = tmp_path / "proj"
    (repo / ".claude" / "agents").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.setenv("MURMURENT_REPO_ROOT", str(tmp_path / "repo"))
    monkeypatch.setenv("MURMURENT_CC_AGENTS_DIR", str(cc))
    monkeypatch.setenv("MURMURENT_AGENT_FORKS_DIR", str(vault / "agent_forks"))
    monkeypatch.setenv("MURMURENT_PERSONAL_AGENTS_DIR", str(vault / "agents"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    from murmurent.core import vault_sync
    monkeypatch.setattr(vault_sync, "personal_vault_root", lambda: vault)
    for n in ("blacksmith", "artist", "security_guard"):
        (cc / f"{n}.md").symlink_to(commons / f"{n}.md")
    return {"tmp": tmp_path, "commons": commons, "cc": cc, "vault": vault,
            "lab": lab, "repo": repo}


def test_levels_in_order(world):
    assert lv.resolve("blacksmith").level == lv.CENTRE
    _write(world["lab"] / "agents" / "blacksmith.md", "blacksmith", "lab")
    assert lv.resolve("blacksmith").level == lv.LAB
    af.fork_agent("blacksmith")                       # the person's own version
    assert lv.resolve("blacksmith").level == lv.PERSON  # beats the lab's (Mike's decision)
    _write(world["repo"] / ".murmurent" / "agents" / "blacksmith.md", "blacksmith", "project")
    assert lv.resolve("blacksmith", repo=world["repo"]).level == lv.PROJECT
    _write(world["vault"] / "projects" / "proj" / "agents" / "blacksmith.md", "blacksmith", "mine")
    win = lv.resolve("blacksmith", project="proj", repo=world["repo"])
    assert win.level == lv.PERSON_PROJECT and win.label == "your version for this project"


def test_locked_agents_stay_centre(world):
    _write(world["lab"] / "agents" / "security_guard.md", "security_guard", "lab")
    _write(world["vault"] / "projects" / "proj" / "agents" / "security_guard.md", "security_guard")
    assert lv.resolve("security_guard", project="proj", repo=world["repo"]).level == lv.CENTRE
    with pytest.raises(RuntimeError):
        lv.set_switched_off("proj", "security_guard", True)


def test_user_level_takes_the_lab_version_unless_you_have_your_own(world):
    _write(world["lab"] / "agents" / "blacksmith.md", "blacksmith", "lab")
    _write(world["lab"] / "agents" / "artist.md", "artist", "lab")
    (world["cc"] / "artist.md").unlink()
    (world["cc"] / "artist.md").write_text("my own artist\n")      # hand-written
    lv.sync_user_level()
    assert os.readlink(world["cc"] / "blacksmith.md") == str(world["lab"] / "agents" / "blacksmith.md")
    assert (world["cc"] / "artist.md").read_text() == "my own artist\n"
    # The lab removes its version: back to the centre's.
    (world["lab"] / "agents" / "blacksmith.md").unlink()
    lv.sync_user_level()
    assert os.readlink(world["cc"] / "blacksmith.md") == str(world["commons"] / "blacksmith.md")


def test_repo_gets_winners_and_switch_offs(world):
    repo = world["repo"]
    agents = repo / ".claude" / "agents"
    (agents / "artist.md").symlink_to(world["commons"] / "artist.md")
    (agents / "kept.md").write_text("a real file the person wrote\n")
    _write(world["vault"] / "projects" / "proj" / "agents" / "blacksmith.md", "blacksmith", "mine")
    settings = repo / ".claude" / "settings.local.json"
    settings.write_text(json.dumps({"permissions": {"deny": ["Bash(rm:*)"]}}))
    lv.set_switched_off("proj", "artist", True)
    rep = lv.sync_repo(repo, "proj")
    assert os.readlink(agents / "blacksmith.md").endswith("projects/proj/agents/blacksmith.md")
    assert (agents / "kept.md").read_text().startswith("a real file")
    assert "kept" in rep.left
    gi = (repo / ".gitignore").read_text()
    assert ".claude/agents/blacksmith.md" in gi and "kept.md" not in gi
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert deny == ["Bash(rm:*)", "Agent(artist)"]
    # Back on: murmurent's rule goes, the person's own rule stays.
    lv.set_switched_off("proj", "artist", False)
    lv.sync_repo(repo, "proj")
    assert json.loads(settings.read_text())["permissions"]["deny"] == ["Bash(rm:*)"]


def test_committed_links_are_left_alone(world):
    repo = world["repo"]
    link = repo / ".claude" / "agents" / "artist.md"
    link.symlink_to("/home/someone_else/agents/artist.md")
    subprocess.run(["git", "-C", str(repo), "add", ".claude/agents/artist.md"], check=True)
    rep = lv.sync_repo(repo, "proj")
    assert os.readlink(link) == "/home/someone_else/agents/artist.md"
    assert any("committed link" in n for n in rep.notes)


def test_project_off_list_in_the_marker(world):
    (world["repo"] / ".murmurent.yaml").write_text("agents_off: [artist, adversary]\n")
    assert lv.switched_off("proj", world["repo"]) == {"artist"}   # never a guardian


def test_cli_fork_for_one_project(world, monkeypatch):
    from murmurent.cli import cli
    monkeypatch.setattr(lv, "local_project_repos", lambda: [("proj", world["repo"])])
    out = CliRunner().invoke(cli, ["agent", "fork", "blacksmith", "--project", "proj"])
    assert out.exit_code == 0, out.output
    mine = world["vault"] / "projects" / "proj" / "agents" / "blacksmith.md"
    assert mine.is_file()
    assert os.readlink(world["repo"] / ".claude" / "agents" / "blacksmith.md") == str(mine)


# ---- the dashboard's versions window -------------------------------------

@pytest.fixture
def client(world, monkeypatch):
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app
    (world["lab"] / "lab.md").write_text("---\nlab: mh\npi: '@the_pi'\n---\n")
    monkeypatch.setattr(lv, "local_project_repos", lambda: [("proj", world["repo"])])
    return TestClient(create_app())


def test_versions_window_actions(client, world, monkeypatch):
    monkeypatch.setenv("MURMURENT_USER", "bob")
    v = client.get("/api/agents/blacksmith/levels?project=proj").json()
    assert v["in_use"]["level"] == lv.CENTRE and not v["switched_off"] and not v["is_pi"]
    r = client.post("/api/agents/blacksmith/fork_project", json={"project": "proj"})
    assert r.status_code == 200 and r.json()["created"]
    assert client.get("/api/agents/blacksmith/levels?project=proj").json()["in_use"]["level"] \
        == lv.PERSON_PROJECT
    assert client.post("/api/agents/artist/switch", json={"project": "proj", "off": True}).status_code == 200
    assert client.get("/api/agents/artist/levels?project=proj").json()["switched_off"]
    assert client.post("/api/agents/security_guard/switch",
                       json={"project": "proj", "off": True}).status_code == 409
    assert client.post("/api/agents/artist/share_lab").status_code == 403   # not the PI


def test_pi_makes_the_lab_version(client, world, monkeypatch):
    monkeypatch.setenv("MURMURENT_USER", "the_pi")
    r = client.post("/api/agents/artist/share_lab")
    assert r.status_code == 200, r.text
    assert (world["lab"] / "agents" / "artist.md").is_file()
    assert os.readlink(world["cc"] / "artist.md") == str(world["lab"] / "agents" / "artist.md")
