"""Repo readiness: agent selection on adopt, and what "ready" actually means.

Pins the two invariants that a silently agent-less adopt violated. A fresh
``murmurent repo adopt`` with no ``--agents`` used to create
``.claude/agents/``, link nothing into it, record ``agents: []`` — and still
report ``✓ ready``. The second half is why the first went unnoticed.

  * ``make_ready()`` agent precedence: explicit list > existing marker's
    picks > every agent the commons ships. An explicit ``[]`` means
    deliberately none and is NOT overridden by the default.
  * ``Readiness.ready`` counts LINKED AGENTS, not merely the existence of
    ``.claude/agents/``. An empty directory is not ready.
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
    """The agents ``make_ready`` will actually link, read from the clone it
    links against.

    Deliberately NOT ``agent_forks.commons_agent_names()``: that resolves via
    ``repo.murmurent_repo_root()``, while ``make_ready`` links against
    ``commons.commons_root()``, and the two disagree on a machine holding both
    a release clone and a development one. On such a machine this fixture
    passed only because both clones happened to ship the same names.
    """
    names = {p.stem for p in (commons_root() / "agents").glob("*.md")}
    if not names:
        pytest.skip("commons agents dir not resolvable in this environment")
    return names


# --- agent selection -------------------------------------------------------

def test_fresh_adopt_defaults_to_the_full_commons(tmp_path, commons_available):
    """No --agents on a fresh repo wires the standard set, as the docs promise.

    Regression: this fell through to the empty list and linked nothing.
    """
    repo = _git_repo(tmp_path)
    rr.make_ready(repo)

    marker = rr.read_marker(repo)
    assert marker is not None
    assert set(marker["agents"]) == commons_available
    assert set(_linked(repo)) == commons_available


def test_explicit_agents_are_honoured(tmp_path, commons_available):
    repo = _git_repo(tmp_path)
    wanted = sorted(list(commons_available)[:2])
    rr.make_ready(repo, agents=wanted)

    assert rr.read_marker(repo)["agents"] == wanted


def test_explicit_empty_list_means_deliberately_none(tmp_path, commons_available):
    """``agents=[]`` is a choice, not a missing value — the default must not
    override it, or a caller could never opt out."""
    repo = _git_repo(tmp_path)
    rr.make_ready(repo, agents=[])

    assert rr.read_marker(repo)["agents"] == []
    assert _linked(repo) == []


def test_rerun_preserves_existing_picks(tmp_path, commons_available):
    """Re-adopting a ready repo must not silently widen it to the full set."""
    repo = _git_repo(tmp_path)
    wanted = sorted(list(commons_available)[:2])
    rr.make_ready(repo, agents=wanted)
    rr.make_ready(repo)                      # no agents= on the second run

    assert rr.read_marker(repo)["agents"] == wanted


# --- what "ready" means ----------------------------------------------------

def test_marker_plus_linked_agents_is_ready(tmp_path, commons_available):
    repo = _git_repo(tmp_path)
    rr.make_ready(repo)

    assert rr.readiness(repo).ready is True


def test_empty_agents_dir_is_not_ready(tmp_path):
    """A marker beside an EMPTY .claude/agents/ is not ready.

    Regression: readiness tested `.is_dir()`, so this reported ✓ ready.
    """
    repo = _git_repo(tmp_path)
    rr.ensure_marker(repo, lab="test", agents=[])
    (repo / ".claude" / "agents").mkdir(parents=True)

    r = rr.readiness(repo)
    assert r.marker is not None
    assert r.has_agents is False
    assert r.ready is False


def test_missing_agents_dir_is_not_ready(tmp_path):
    repo = _git_repo(tmp_path)
    rr.ensure_marker(repo, lab="test", agents=[])

    assert rr.readiness(repo).ready is False


def test_no_marker_is_not_ready(tmp_path, commons_available):
    """Linked agents alone don't make a repo ready — the marker is required."""
    repo = _git_repo(tmp_path)
    agents_dir = repo / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "blacksmith.md").write_text("stub")

    r = rr.readiness(repo)
    assert r.has_agents is True
    assert r.ready is False
