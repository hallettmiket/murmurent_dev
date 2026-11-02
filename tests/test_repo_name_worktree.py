"""
Purpose: Issue #250. In a git worktree the folder name is not the repository's
         name; ``repo_name`` reads the main copy's name, Slack routing and the
         project lookups use it, and ``murmurent project release-repo`` takes a
         repository off a record that should not claim it.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-01
Input:   temporary folders; one small git repository made on the fly.
Output:  pass or fail.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import repo as _repo
from murmurent.core import slack_routing as sr


@pytest.fixture
def world(monkeypatch, tmp_path):
    repos = tmp_path / "repos"
    lab_mgmt = tmp_path / "lab_mgmt"
    for d in (repos, lab_mgmt, tmp_path / "mm_home"):
        d.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "mm_home"))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "")
    return {"repos": repos}


def marked_repo(root: Path, name: str, **marker) -> Path:
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    (p / ".murmurent.yaml").write_text(yaml.safe_dump({"murmurent": 1, "lab": "mh", **marker}))
    return p


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@example.org", "-c", "user.name=t", *args],
                   cwd=cwd, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# repo_name
# ---------------------------------------------------------------------------


def test_a_plain_folder_is_named_after_itself(tmp_path):
    (tmp_path / "decolonize").mkdir()
    assert _repo.repo_name(tmp_path / "decolonize") == "decolonize"


def test_a_linked_worktree_is_named_after_the_main_copy(tmp_path):
    wt = tmp_path / "decolonize" / ".claude" / "worktrees" / "uk-biochemistry-4697a9"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(
        f"gitdir: {tmp_path}/decolonize/.git/worktrees/uk-biochemistry-4697a9\n")
    assert _repo.repo_name(wt) == "decolonize"


def test_a_relative_gitdir_is_resolved_from_the_worktree(tmp_path):
    wt = tmp_path / "decolonize" / ".claude" / "worktrees" / "slug"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../../.git/worktrees/slug\n")
    assert _repo.repo_name(wt) == "decolonize"


def test_a_submodule_keeps_its_own_folder_name(tmp_path):
    sub = tmp_path / "super" / "libs" / "thing"
    sub.mkdir(parents=True)
    (sub / ".git").write_text(f"gitdir: {tmp_path}/super/.git/modules/libs/thing\n")
    assert _repo.repo_name(sub) == "thing"


def test_project_repo_carries_the_name(tmp_path):
    wt = tmp_path / "decolonize" / ".claude" / "worktrees" / "slug"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {tmp_path}/decolonize/.git/worktrees/slug\n")
    (wt / ".murmurent.yaml").write_text("murmurent: 1\n")
    found = _repo.find_project_repo(wt)
    assert found is not None and found.name == "decolonize"


# ---------------------------------------------------------------------------
# routing from a real worktree (the case in the issue)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_a_note_from_a_git_worktree_routes_like_the_main_copy(world, tmp_path):
    repo = marked_repo(world["repos"], "decolonize")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "marker")
    wt = tmp_path / "elsewhere" / "uk-biochemistry-decolonization-4697a9"
    _git(repo, "worktree", "add", "-q", str(wt))
    assert (wt / ".murmurent.yaml").is_file()          # the worktree carries the marker
    cp.upsert("decolonize", lab="mh", slack_channel_id="CDECOL",
              repos=[cp.RepoRef(name="decolonize", path=str(repo))])

    from_main = sr.resolve_route(repo)
    from_worktree = sr.resolve_route(wt)
    assert from_main.channel_id == "CDECOL"
    assert (from_worktree.channel_id, from_worktree.project, from_worktree.repo) == \
        ("CDECOL", "decolonize", "decolonize")
    assert cp.project_name_for_cwd(wt) == "decolonize"


def test_two_claims_route_to_both_from_a_worktree(world, tmp_path):
    repo = marked_repo(world["repos"], "decolonize")
    for proj in ("edid", "decolonize"):
        cp.upsert(proj, lab="mh", slack_channel_id=f"C{proj.upper()}",
                  repos=[cp.RepoRef(name="decolonize", path=str(repo))])
    wt = tmp_path / "decolonize" / ".claude" / "worktrees" / "slug"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {world['repos']}/decolonize/.git/worktrees/slug\n")
    (wt / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    r = sr.resolve_route(wt)
    assert r.ok and sorted(x.channel_id for x in r.all) == ["CDECOLONIZE", "CEDID"]


# ---------------------------------------------------------------------------
# murmurent project release-repo
# ---------------------------------------------------------------------------


def test_release_repo_takes_the_repository_off_the_record(world):
    repo = marked_repo(world["repos"], "decolonize")
    other = marked_repo(world["repos"], "edid_notes")
    cp.upsert("edid", lab="mh", slack_channel_id="CEDID",
              repos=[cp.RepoRef(name="edid_notes", path=str(other)),
                     cp.RepoRef(name="decolonize", path=str(repo))])
    cp.upsert("decolonize", lab="mh", slack_channel_id="CDECOL",
              repos=[cp.RepoRef(name="decolonize", path=str(repo))])
    assert sorted(x.channel_id for x in sr.resolve_route(repo).all) == ["CDECOL", "CEDID"]

    out = CliRunner().invoke(cli, ["project", "release-repo", "edid", "decolonize"])
    assert out.exit_code == 0, out.output
    assert "no longer lists the repository decolonize" in out.output
    assert [r.name for r in cp.get("edid").repos] == ["edid_notes"]
    assert [x.channel_id for x in sr.resolve_route(repo).all] == ["CDECOL"]


def test_release_repo_refuses_what_is_not_there(world):
    cp.upsert("edid", lab="mh")
    out = CliRunner().invoke(cli, ["project", "release-repo", "edid", "decolonize"])
    assert out.exit_code != 0 and "no repo named" in out.output
    out = CliRunner().invoke(cli, ["project", "release-repo", "nope", "decolonize"])
    assert out.exit_code != 0 and "no cert-project named" in out.output
