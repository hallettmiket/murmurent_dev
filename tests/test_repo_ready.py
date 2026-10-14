"""
Purpose: Pin what "ready" means and which agents adopt pins (PR #167).
Author: emucaki and Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: throwaway git repos under tmp_path, linked against the real commons
Output: pytest assertions

Adapted from emucaki's tests in PR #167, which found that readiness tested
only that ``.claude/agents/`` EXISTED, a test that could never fail because
adopt creates the folder first. The fix taken is the other one: readiness
depends on the ``.murmurent.yaml`` marker alone. Every agent already works in
every folder from ``~/.claude/agents/``; a link in a repo only pins one, and
pins are per-machine (#150), so adopt pins nothing unless asked.

  * ``make_ready()`` agent precedence: explicit list > existing marker's
    picks > none. An explicit ``[]`` means deliberately none.
  * ``Readiness.ready`` is the marker, nothing else.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from murmurent.core import repo_ready as rr
from murmurent.core.commons import commons_root


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clone"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def _linked(repo: Path) -> list[str]:
    d = repo / ".claude" / "agents"
    return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []


@pytest.fixture
def commons_available() -> set[str]:
    """The agents ``make_ready`` links against, read from ``commons_root()``,
    which is what ``make_ready`` itself uses (emucaki's note: not
    ``agent_forks.commons_agent_names()``, which can resolve a different clone)."""
    names = {p.stem for p in (commons_root() / "agents").glob("*.md")}
    if not names:
        pytest.skip("commons agents dir not resolvable in this environment")
    return names


# --- agent selection -------------------------------------------------------

def test_fresh_adopt_pins_nothing(tmp_path: Path) -> None:
    """No --agents means no links: the agents already work here."""
    repo = _git_repo(tmp_path)
    rr.make_ready(repo)
    assert rr.read_marker(repo)["agents"] == []
    assert _linked(repo) == []


def test_explicit_agents_are_honoured(tmp_path: Path, commons_available: set[str]) -> None:
    repo = _git_repo(tmp_path)
    wanted = sorted(commons_available)[:2]
    rr.make_ready(repo, agents=wanted)
    assert rr.read_marker(repo)["agents"] == wanted
    assert _linked(repo) == wanted


def test_explicit_empty_list_means_deliberately_none(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    rr.make_ready(repo, agents=[])
    assert rr.read_marker(repo)["agents"] == []
    assert _linked(repo) == []


def test_rerun_preserves_existing_picks(tmp_path: Path, commons_available: set[str]) -> None:
    """Re-adopting must neither widen nor drop what the repo already pins."""
    repo = _git_repo(tmp_path)
    wanted = sorted(commons_available)[:2]
    rr.make_ready(repo, agents=wanted)
    rr.make_ready(repo)                      # no agents= on the second run
    assert rr.read_marker(repo)["agents"] == wanted


# --- what "ready" means ----------------------------------------------------

def test_fresh_adopt_is_ready(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    rr.make_ready(repo)
    assert rr.readiness(repo).ready is True


@pytest.mark.parametrize("agents_dir", ["missing", "empty", "pinned"])
def test_marker_alone_decides(tmp_path: Path, agents_dir: str) -> None:
    repo = _git_repo(tmp_path)
    rr.ensure_marker(repo, lab="test", agents=[])
    d = repo / ".claude" / "agents"
    if agents_dir != "missing":
        d.mkdir(parents=True)
    if agents_dir == "pinned":
        (d / "blacksmith.md").write_text("stub", encoding="utf-8")
    assert rr.readiness(repo).ready is True


def test_agents_without_a_marker_are_not_ready(tmp_path: Path) -> None:
    """A .claude/agents/ folder is Claude Code's own feature; it does not make
    a repo murmurent-ready."""
    repo = _git_repo(tmp_path)
    d = repo / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "blacksmith.md").write_text("stub", encoding="utf-8")
    assert rr.readiness(repo).ready is False
