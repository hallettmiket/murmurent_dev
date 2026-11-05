"""
Purpose: Issue #257. Readiness travels with the clone: make ready commits the
         marker and the CLAUDE.md stub; the release that linked a repository
         is recorded per machine, not in the committed marker; a clone that
         arrives with the marker is registered when install or reconcile
         sees it; a push from a machine without the bot token says what to
         run; the CLI and the dashboard pick the same agents.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   throwaway git repositories under tmp_path; the real commons.
Output:  pass or fail.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent import __version__
from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import repo_paths as rp
from murmurent.core import repo_ready as rr
from murmurent.core import slack_routing as sr


@pytest.fixture
def world(monkeypatch, tmp_path):
    repos = tmp_path / "repos"
    for d in (repos, tmp_path / "lab_mgmt", tmp_path / "mm_home"):
        d.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab_mgmt"))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "mm_home"))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "")
    return {"repos": repos, "tmp": tmp_path}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.email=t@x", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True)


def git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    (path / "README.md").write_text("hello\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-q", "-m", "start")
    return path


def _log(path: Path) -> str:
    return _git(path, "log", "--format=%s").stdout


# ---------------------------------------------------------------------------
# make ready commits the marker
# ---------------------------------------------------------------------------


def test_make_ready_commits_the_readiness_files_only(world):
    repo = git_repo(world["repos"] / "brca")
    (repo / "notes.txt").write_text("not for the commit\n")
    _git(repo, "add", "notes.txt")                    # staged, unrelated
    probes = rr.make_ready(repo, lab="mh", agents=[])
    by = {p.name: p for p in probes}
    assert by["commit"].status == "ok" and "committed" in by["commit"].detail
    assert _log(repo).splitlines()[0] == rr.READINESS_COMMIT_MESSAGE
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert ".murmurent.yaml" in committed and "CLAUDE.md" in committed
    assert "notes.txt" not in committed
    status = _git(repo, "status", "--porcelain").stdout
    assert "A  notes.txt" in status                    # still staged, untouched
    # a second run has nothing to commit
    again = {p.name: p for p in rr.make_ready(repo)}
    assert again["commit"].status == "ok" and "already committed" in again["commit"].detail


def test_make_ready_without_commit_leaves_it_to_the_person(world):
    repo = git_repo(world["repos"] / "brca")
    probes = rr.make_ready(repo, lab="mh", agents=[], commit=False)
    assert "commit" not in {p.name for p in probes}
    assert ".murmurent.yaml" in _git(repo, "status", "--porcelain").stdout


def test_a_failed_commit_says_what_to_run(world, monkeypatch):
    repo = git_repo(world["repos"] / "brca")
    rr._write_marker(repo, lab="mh", agents=[])
    real_run = subprocess.run

    def failing(cmd, *a, **kw):
        if "commit" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "fatal: cannot commit")
        return real_run(cmd, *a, **kw)
    monkeypatch.setattr(subprocess, "run", failing)
    probe = rr.commit_readiness(repo)
    assert probe.status == "warn"
    assert "git add .murmurent.yaml" in probe.detail and "git commit" in probe.detail


def test_commit_in_a_plain_folder_is_a_quiet_ok(world):
    folder = world["repos"] / "plain"
    folder.mkdir()
    (folder / ".murmurent.yaml").write_text("murmurent: 1\n")
    assert rr.commit_readiness(folder).status == "ok"


# ---------------------------------------------------------------------------
# the release that linked a repository is per machine
# ---------------------------------------------------------------------------


def test_marker_no_longer_carries_the_bootstrap_version(world):
    repo = git_repo(world["repos"] / "brca")
    rr.make_ready(repo, lab="mh", agents=[])
    marker = yaml.safe_load((repo / ".murmurent.yaml").read_text())
    assert "bootstrap_version" not in marker
    assert rr.bootstrap_version_of(repo) == str(__version__)
    assert not rr.readiness(repo).needs_upgrade


def test_an_old_marker_keeps_its_version_line_untouched(world):
    """Two machines on different releases used to push the line back and
    forth. Now nobody rewrites it; the machine record decides."""
    repo = git_repo(world["repos"] / "brca")
    (repo / ".murmurent.yaml").write_text(yaml.safe_dump({
        "murmurent": 1, "lab": "mh", "ready_since": "2026-01-01",
        "bootstrap_version": "2025.1.0", "agents": []}))
    _git(repo, "add", ".murmurent.yaml")
    _git(repo, "commit", "-q", "-m", "old marker")
    assert rr.readiness(repo).needs_upgrade            # never linked on this machine
    rr.upgrade(repo)
    marker = yaml.safe_load((repo / ".murmurent.yaml").read_text())
    assert marker["bootstrap_version"] == "2025.1.0"   # left as it was
    assert _git(repo, "status", "--porcelain", "--", ".murmurent.yaml").stdout == ""  # not dirtied
    assert rr.bootstrap_version_of(repo) == str(__version__)
    assert not rr.readiness(repo).needs_upgrade


def test_upgrade_registers_a_clone_that_arrived_with_the_marker(world):
    repo = git_repo(world["repos"] / "brca")
    (repo / ".murmurent.yaml").write_text(yaml.safe_dump(
        {"murmurent": 1, "lab": "mh", "ready_since": "2026-01-01", "agents": []}))
    assert rp.find("brca") is None or rp._read_record().get("brca") is None
    rr.upgrade(repo)
    assert rp._read_record().get("brca") == str(repo)


def test_register_ready_clones_finds_them_in_project_folders_too(world):
    ready = git_repo(world["repos"] / "atlas" / "atlas_manuscript")
    (ready / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    plain = git_repo(world["repos"] / "plain")
    seen = rr.register_ready_clones()
    assert seen == [ready]
    assert rp._read_record().get("atlas_manuscript") == str(ready)
    assert "plain" not in rp._read_record()


def test_reconcile_registers_ready_clones(world, monkeypatch):
    from murmurent.core import reconcile as rc
    ready = git_repo(world["repos"] / "brca")
    (ready / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    for name in ("detect_orphan_installations", "detect_orphan_registries",
                 "detect_missing_markers", "detect_unadopted_clones",
                 "detect_lab_mgmt_unsynced"):
        monkeypatch.setattr(rc, name, lambda: [])
    rc.reconcile()
    assert rp._read_record().get("brca") == str(ready)


# ---------------------------------------------------------------------------
# the worktree name, the token message, the CLI defaults
# ---------------------------------------------------------------------------


def test_make_ready_in_a_worktree_uses_the_main_copys_name(world):
    repo = git_repo(world["repos"] / "brca")
    wt = world["tmp"] / "elsewhere" / "brca-slug-1234"
    _git(repo, "worktree", "add", "-q", str(wt))
    rr.make_ready(wt, lab="mh", agents=[], commit=False)
    assert rp._read_record().get("brca") == str(wt)
    assert "brca-slug-1234" not in rp._read_record()
    assert "brca-slug-1234" not in (wt / "CLAUDE.md").read_text()
    assert rr.bootstrap_version_of(wt) and "brca" in rr._read_bootstrap_record()


def test_missing_bot_token_names_the_fix(world):
    repo = git_repo(world["repos"] / "brca")
    (repo / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    cp.upsert("brca", lab="mh", slack_channel_id="CBRCA",
              repos=[cp.RepoRef(name="brca", path=str(repo))])
    ok, _route, detail = sr.post_note("hi", start=repo, token="",
                                      poster=lambda *a, **k: True)
    assert not ok
    assert "no Slack bot token on this machine for project 'brca'" in detail
    # no identity card in this world, so this is a member's machine: it is told
    # to unlock the copy the PI shared, not to set the token up itself
    assert "murmurent group-slack-unlock mh" in detail


def test_cli_adopt_links_every_agent_by_default_like_the_dashboard(world):
    repo = git_repo(world["repos"] / "brca")
    out = CliRunner().invoke(cli, ["repo", "adopt", str(repo), "--lab", "mh"])
    assert out.exit_code == 0, out.output
    marker = yaml.safe_load((repo / ".murmurent.yaml").read_text())
    commons = sorted(p.stem for p in (rr.commons_root() / "agents").glob("*.md"))
    assert marker["agents"] == commons
    assert "commit: committed" in out.output or "✓ commit" in out.output
    assert _log(repo).splitlines()[0] == rr.READINESS_COMMIT_MESSAGE


def test_cli_adopt_named_agents_and_no_commit(world):
    repo = git_repo(world["repos"] / "brca")
    out = CliRunner().invoke(cli, ["repo", "adopt", str(repo), "--lab", "mh",
                                   "--agents", "oracle", "--no-commit"])
    assert out.exit_code == 0, out.output
    marker = yaml.safe_load((repo / ".murmurent.yaml").read_text())
    assert marker["agents"] == ["oracle"]
    assert ".murmurent.yaml" in _git(repo, "status", "--porcelain").stdout


def test_remote_marker_has_no_version_line_and_warns_about_kept_agents():
    from murmurent.core import remote_adopt as ra
    script = ra.build_remote_adopt_script(clone_path="/home/x/repos/p", project="p",
                                          agents=["oracle"], lab="mh",
                                          bootstrap_version="2026.1.0")
    assert "bootstrap_version" not in script
    assert "its agents list was not changed" in script
    script2 = ra.build_remote_adopt_script(clone_path="/home/x/repos/p", project="p",
                                           agents=[], lab="mh")
    assert "marker:ok:already exists" in script2
