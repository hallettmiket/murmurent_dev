"""
Purpose: Guard issue #150: a repo's links into one member's commons must stay
         on that member's machine.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: throwaway git repos and a fake commons under tmp_path
Output: pytest assertions

What went wrong: two members each adopted the same repo; one committed
``.claude/agents/*.md``, which are links into their own home folder, and the
other member's agents then pointed somewhere they could not read.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.core import agent_links as AL
from murmurent.core import repo_ready as RR

AGENTS = ("bookworm", "adversary")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    ).stdout


@pytest.fixture
def commons(tmp_path: Path) -> Path:
    root = tmp_path / "home_a" / "repos" / "murmurent"
    (root / "agents").mkdir(parents=True)
    for a in (*AGENTS, "artist"):
        (root / "agents" / f"{a}.md").write_text(f"# {a}\n", encoding="utf-8")
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "project"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "README.md").write_text("# p\n", encoding="utf-8")
    return r


# --- the .gitignore block ----------------------------------------------------

def test_gitignore_block_is_written_rewritten_and_removed(repo: Path) -> None:
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    assert AL.update_gitignore(repo, ["bookworm", "adversary"])
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith("*.pyc\n")
    assert ".claude/agents/adversary.md\n.claude/agents/bookworm.md" in text

    assert not AL.update_gitignore(repo, ["adversary", "bookworm"])  # no change

    AL.update_gitignore(repo, ["artist"])
    text = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "bookworm" not in text and ".claude/agents/artist.md" in text
    assert text.count(AL.BLOCK_BEGIN) == 1

    AL.update_gitignore(repo, [])
    assert (repo / ".gitignore").read_text(encoding="utf-8") == "*.pyc\n"


# --- adopt ---------------------------------------------------------------------

def test_adopt_keeps_the_links_out_of_git(repo: Path, commons: Path) -> None:
    RR.make_ready(repo, agents=list(AGENTS), murmurent_root=commons)
    for a in AGENTS:
        assert (repo / ".claude" / "agents" / f"{a}.md").is_symlink()
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert ".claude/agents" not in status, status
    assert ".gitignore" in status   # the block itself IS committed


def test_adopt_keeps_a_groups_own_agent_file(repo: Path, commons: Path) -> None:
    """A real file with a commons agent's name is the group's tuned version.
    It used to be deleted and replaced by a link."""
    own = repo / ".claude" / "agents" / "bookworm.md"
    own.parent.mkdir(parents=True)
    own.write_text("# our tuned bookworm\n", encoding="utf-8")
    RR.make_ready(repo, agents=list(AGENTS), murmurent_root=commons)
    assert not own.is_symlink()
    assert own.read_text(encoding="utf-8") == "# our tuned bookworm\n"
    # ...and it stays committable: only the real link is ignored.
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert ".claude/agents/bookworm.md" in status
    assert ".claude/agents/adversary.md" not in status


# --- links that were already committed --------------------------------------

def test_committed_links_are_found_and_reported(repo: Path, commons: Path) -> None:
    RR.make_ready(repo, agents=list(AGENTS), murmurent_root=commons)
    _git(repo, "add", "-f", ".claude/agents/bookworm.md")
    _git(repo, "commit", "-q", "-m", "oops")
    found = AL.tracked_machine_links(repo)
    assert [p for p, _ in found] == [".claude/agents/bookworm.md"]
    assert found[0][1] == str(commons / "agents" / "bookworm.md")

    probes = RR.upgrade(repo, murmurent_root=commons)
    warn = [p for p in probes if p.name == "committed agent links"]
    assert warn and warn[0].status == "warn"
    assert "rm --cached" in warn[0].detail and "repo upgrade" in warn[0].detail

    from murmurent.cli import cli
    out = CliRunner().invoke(cli, ["repo", "status", str(repo)]).output
    assert "committed links" in out and "bookworm.md" in out


def test_a_link_inside_the_repo_is_not_flagged(repo: Path) -> None:
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    (repo / "shared.md").write_text("# s\n", encoding="utf-8")
    (agents / "shared.md").symlink_to("../../shared.md")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "in-repo link")
    assert AL.tracked_machine_links(repo) == []
    assert not AL.is_machine_link(repo, ".claude/agents/shared.md")


def test_tracked_links_outside_git_is_empty(tmp_path: Path) -> None:
    assert AL.tracked_machine_links(tmp_path) == []


# --- the project-wide push ---------------------------------------------------

def test_project_push_never_stages_a_machine_link(repo: Path, commons: Path) -> None:
    from types import SimpleNamespace

    from murmurent.commands import project_push_cmd as PP

    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "bookworm.md").symlink_to(commons / "agents" / "bookworm.md")
    (agents / "ours.md").write_text("# a group agent\n", encoding="utf-8")
    res = PP.push_one_repo(SimpleNamespace(name="p", path=str(repo), host="local",
                                           remote_path=None), message="m")
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert ".claude/agents/ours.md" in committed
    assert "bookworm" not in committed
    assert res.status == PP.STATUS_COMMITTED_LOCAL


# --- the per-prompt hook -----------------------------------------------------

def test_hook_says_when_links_lead_into_another_home(
    repo: Path, commons: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from murmurent.hooks import context_inject as CI

    RR.make_ready(repo, agents=list(AGENTS), murmurent_root=commons)
    me = tmp_path / "home_b"
    mine = me / "repos" / "murmurent"
    (mine / "agents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: me)
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(mine))
    notice = CI._readiness_notice(str(repo))
    assert notice and "another person's home folder" in notice
    assert f"murmurent repo status {repo}" in notice
