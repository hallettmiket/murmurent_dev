"""Lab-record saves and updates combine with GitHub's newer commits instead of
failing silently (one Mac held 120 unsent commits and stopped seeing new members)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from murmurent.core import git_persist as gp
from murmurent.core import roster_sync as rs


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def two_copies(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    copies = []
    for name in ("server", "mac"):
        d = tmp_path / name
        subprocess.run(["git", "clone", "-q", str(remote), str(d)], check=True, capture_output=True)
        _git(d, "config", "user.email", "t@example.org")
        _git(d, "config", "user.name", "T")
        _git(d, "checkout", "-q", "-B", "main")
        copies.append(d)
    server, mac = copies
    (server / "members").mkdir()
    (server / "members" / "pi.md").write_text("pi\n")
    _git(server, "add", "-A"); _git(server, "commit", "-q", "-m", "start")
    _git(server, "push", "-q", "-u", "origin", "main")
    _git(mac, "pull", "-q", "origin", "main")
    _git(mac, "branch", "-q", "--set-upstream-to=origin/main", "main")
    return remote, server, mac


def test_a_save_refused_by_github_is_replayed_and_sent(two_copies):
    remote, server, mac = two_copies
    (server / "members" / "new_student.md").write_text("student\n")
    probes = gp.commit_and_push(server / "members" / "new_student.md", "roster: add student")
    assert probes[-1].status == "ok"
    (mac / "cert_projects").mkdir()
    (mac / "cert_projects" / "pin1.md").write_text("pin1\n")
    probes = gp.commit_and_push(mac / "cert_projects" / "pin1.md", "cert-project: pin1")
    assert probes[-1].status == "ok", probes[-1].detail
    sent = _git(mac, "ls-tree", "-r", "--name-only", "origin/main")
    assert "cert_projects/pin1.md" in sent and "members/new_student.md" in sent


def test_the_update_sends_commits_github_never_received(two_copies, monkeypatch):
    remote, server, mac = two_copies
    (mac / "cert_projects").mkdir()
    (mac / "cert_projects" / "survival.md").write_text("survival\n")
    _git(mac, "add", "-A"); _git(mac, "commit", "-q", "-m", "unsent save")     # never pushed
    (server / "members" / "milan.md").write_text("milan\n")
    _git(server, "add", "-A"); _git(server, "commit", "-q", "-m", "add milan")
    _git(server, "push", "-q")
    monkeypatch.setattr(rs, "lab_mgmt_repo_root", lambda: mac)
    res = rs.pull_lab_mgmt()
    assert res.ok, res.detail
    assert (mac / "members" / "milan.md").exists()                            # the new member arrives
    assert "cert_projects/survival.md" in _git(mac, "ls-tree", "-r", "--name-only", "origin/main")


def test_a_clash_overwrites_nothing(two_copies, monkeypatch):
    remote, server, mac = two_copies
    (mac / "members" / "pi.md").write_text("mac version\n")
    _git(mac, "commit", "-qam", "mac edit")
    (server / "members" / "pi.md").write_text("server version\n")
    _git(server, "commit", "-qam", "server edit"); _git(server, "push", "-q")
    monkeypatch.setattr(rs, "lab_mgmt_repo_root", lambda: mac)
    res = rs.pull_lab_mgmt()
    assert not res.ok and "nothing was overwritten" in res.detail
    assert _git(mac, "show", "HEAD:members/pi.md") == "mac version\n"
    assert _git(server, "show", "HEAD:members/pi.md") == "server version\n"
