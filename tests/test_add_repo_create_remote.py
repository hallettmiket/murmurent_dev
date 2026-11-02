"""
Purpose: Issue #269. `murmurent project add-repo --create-remote` creates a
         private <org>/<repo> on GitHub for a clone that has none, pushes it,
         records the remote on the project and grants every member access;
         a clone with no remote is named with the hint otherwise.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   throwaway git repositories under tmp_path; gh and git push seams.
Output:  pass or fail.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import membership as MEM
from murmurent.core import repo_remote as RR
from murmurent.core import slack_routing as sr


@pytest.fixture
def world(monkeypatch, tmp_path):
    repos = tmp_path / "repos"
    lab_mgmt = tmp_path / "lab_mgmt"
    for d in (repos, lab_mgmt, tmp_path / "mm_home"):
        d.mkdir(parents=True)
    (lab_mgmt / "lab.md").write_text("---\nlab: mh\npi: '@tester'\ngithub_org: mh-org\n---\n")
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "mm_home"))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "")
    MEM.upsert_member("@allie", github="allie-gh")
    return {"repos": repos, "lab_mgmt": lab_mgmt}


def _git(cwd: Path, *args: str):
    return subprocess.run(["git", "-c", "user.email=t@x", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True)


def git_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", branch)
    (path / ".murmurent.yaml").write_text(yaml.safe_dump({"murmurent": 1, "lab": "mh"}))
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "start")
    return path


def _seams(created, pushed):
    return dict(creator=lambda org, name: created.append(f"{org}/{name}") or (True, "created"),
                pusher=lambda repo_dir, url: pushed.append((str(repo_dir), url)) or (True, "pushed main"),
                github_reconciler=lambda project, env=None, remove_extras=True:
                    {"ok": True, "added": ["allie-gh"], "in_sync": False, "problems": [],
                     "repos": ["mh-org/brca_figures"]})


def test_create_remote_and_grant(world):
    repo = git_repo(world["repos"] / "brca_figures")
    cp.upsert("brca", lab="mh", member="@allie", repos=[cp.RepoRef(name="brca_figures", path=str(repo))])
    created, pushed = [], []
    out = RR.create_remote_and_grant("brca", "brca_figures", **_seams(created, pushed))
    assert out["ok"], out
    assert created == ["mh-org/brca_figures"]
    assert pushed == [(str(repo), "git@github.com:mh-org/brca_figures.git")]
    assert out["remote_url"] == "git@github.com:mh-org/brca_figures.git"
    entry = next(r for r in cp.get("brca").repos if r.name == "brca_figures")
    assert entry.remote_url == out["remote_url"] and entry.path == str(repo)
    assert out["github"]["added"] == ["allie-gh"] and out["problems"] == []


def test_an_existing_github_origin_is_kept(world):
    repo = git_repo(world["repos"] / "brca_figures")
    _git(repo, "remote", "add", "origin", "https://github.com/other/brca_figures.git")
    cp.upsert("brca", lab="mh", repos=[cp.RepoRef(name="brca_figures", path=str(repo))])
    created, pushed = [], []
    out = RR.create_remote_and_grant("brca", "brca_figures", **_seams(created, pushed))
    assert out["ok"] and not created and not pushed
    assert out["remote_url"] == "https://github.com/other/brca_figures.git"
    assert "kept" in out["created"]


def test_no_org_and_refusals_are_reported_not_raised(world, monkeypatch):
    repo = git_repo(world["repos"] / "x")
    cp.upsert("p", lab="mh", repos=[cp.RepoRef(name="x", path=str(repo))])
    (world["lab_mgmt"] / "lab.md").write_text("---\nlab: mh\npi: '@tester'\n---\n")
    out = RR.create_remote_and_grant("p", "x", creator=lambda o, n: (True, "created"))
    assert not out["ok"] and "set github_org" in out["problems"][0]
    out = RR.create_remote_and_grant("p", "x", org="mh-org",
                                     creator=lambda o, n: (False, "HTTP 403: resource not accessible"))
    assert not out["ok"] and "could not create mh-org/x" in out["problems"][0]
    assert cp.get("p").repos[0].remote_url == ""
    out = RR.create_remote_and_grant("p", "nope", org="mh-org")
    assert "does not list a repository named nope" in out["problems"][0]


def test_push_uses_the_current_branch(world, monkeypatch):
    repo = git_repo(world["repos"] / "x", branch="trunk")
    calls = []
    real = subprocess.run

    def fake(cmd, *a, **kw):
        if cmd[:3] == ["git", "-C", str(repo)] and "push" in cmd:
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, *a, **kw)
    monkeypatch.setattr(subprocess, "run", fake)
    ok, detail = RR._default_pusher(repo, "git@github.com:mh-org/x.git")
    assert ok and detail == "pushed trunk"
    assert calls and calls[0][-1] == "trunk"
    assert RR.origin_of(repo) == "git@github.com:mh-org/x.git"


def test_cli_add_repo_create_remote(world, monkeypatch):
    repo = git_repo(world["repos"] / "brca_figures")
    cp.upsert("brca", lab="mh", member="@allie")
    created, pushed = [], []
    seams = _seams(created, pushed)
    monkeypatch.setattr(RR, "_default_creator", seams["creator"])
    monkeypatch.setattr(RR, "_default_pusher", seams["pusher"])
    from murmurent.core import cert_provision as CPROV
    monkeypatch.setattr(CPROV, "reconcile_github", seams["github_reconciler"])
    out = CliRunner().invoke(cli, ["project", "add-repo", "brca", str(repo), "--create-remote"])
    assert out.exit_code == 0, out.output
    assert "GitHub: git@github.com:mh-org/brca_figures.git (created; pushed main)" in out.output
    assert "access granted to: allie-gh" in out.output
    assert created == ["mh-org/brca_figures"]
    assert "GitHub mh-org/brca_figures" in out.output      # project status shows the remote


def test_cli_add_repo_names_a_clone_without_a_remote(world):
    repo = git_repo(world["repos"] / "brca_figures")
    cp.upsert("brca", lab="mh")
    out = CliRunner().invoke(cli, ["project", "add-repo", "brca", str(repo)])
    assert out.exit_code == 0, out.output
    assert "has no GitHub remote yet, so members get no access to it" in out.output
    assert "--create-remote" in out.output
    assert "no GitHub remote" in out.output


def test_dashboard_add_repo_with_create_remote(world, monkeypatch):
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app
    repo = git_repo(world["repos"] / "brca_figures")
    cp.upsert("brca", lab="mh", lead="@tester")
    created, pushed = [], []
    seams = _seams(created, pushed)
    monkeypatch.setattr(RR, "_default_creator", seams["creator"])
    monkeypatch.setattr(RR, "_default_pusher", seams["pusher"])
    from murmurent.core import cert_provision as CPROV
    monkeypatch.setattr(CPROV, "reconcile_github", seams["github_reconciler"])
    client = TestClient(create_app())
    r = client.post("/api/project/brca/repos?user=tester",
                    json={"repo_name": "brca_figures", "role": "code", "path": str(repo),
                          "create_remote": True})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["remote"]["ok"] and j["remote"]["remote_url"].endswith("mh-org/brca_figures.git")
    assert created == ["mh-org/brca_figures"]
    assert any(x["name"] == "brca_figures" and x.get("remote_url") for x in j["repos"])
