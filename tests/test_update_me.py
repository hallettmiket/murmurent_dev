"""
Purpose: Guard the project settings of the /murmurent-update-me skill (#152).
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: throwaway git repositories under tmp_path
Output: pytest assertions

The skill was built for the survival project with its settings fixed in the
code. These tests pin what replaced them: an optional `update_me:` block in the
repository's .murmurent.yaml, with defaults for every key. The agent-log pairing
logic has its own tests beside the script (test_gather_facts.py).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SKILL = Path(__file__).resolve().parent.parent / "skills" / "murmurent-update-me"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"um_{name}", SKILL / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "x_proj"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "remote", "add", "origin", "git@github.com:somelab/x_proj.git"], check=True)
    monkeypatch.chdir(r)
    return r


def _marker(repo: Path, data: dict) -> None:
    (repo / ".murmurent.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_defaults_without_a_block(repo: Path) -> None:
    gf = _load("gather_facts")
    _marker(repo, {"murmurent": 1, "lab": "mh"})
    gf.configure(repo, gf.read_settings(repo))
    assert gf.PROJECT == "x_proj"
    assert gf.OUTPUT_ROOT == gf.DATA_ROOT / "append_only" / "x_proj"
    assert (gf.GITHUB_OWNER, gf.GITHUB_REPO) == ("somelab", "x_proj")
    assert gf.OTHER_REPO_NAMES == ()
    assert gf.GATES == ()
    assert gf.LAB_GROUP                       # this account's main group, never blank
    assert "/repos/x_proj/" in gf.PROJECT_MARKERS


def test_manuscript_beside_the_repo_is_found(repo: Path) -> None:
    gf = _load("gather_facts")
    (repo.parent / "x_proj_manuscript").mkdir()
    gf.configure(repo, {})
    assert gf.OTHER_REPO_NAMES == ("x_proj_manuscript",)


def test_choreography_names_its_own_data_folder(repo: Path) -> None:
    gf = _load("gather_facts")
    _marker(repo, {"murmurent": 1, "kind": "choreography", "name": "survival", "data": {"root_subdir": "surv_data"}})
    gf.configure(repo, gf.read_settings(repo))
    assert gf.PROJECT == "survival"
    assert gf.OUTPUT_ROOT.name == "surv_data"


def test_the_block_overrides_every_default(repo: Path) -> None:
    gf = _load("gather_facts")
    _marker(repo, {"murmurent": 1, "update_me": {
        "project": "p", "outputs": "/tmp/out", "github": "o/n", "other_repos": [], "lab_group": "g",
        "gates": [{"label": "G", "folder": "f", "prefix": "r_", "experiment": "exp/1"}],
        "process_markers": ["/envs/p/"], "people": {"a": "A B"}}})
    gf.configure(repo, gf.read_settings(repo))
    assert (gf.PROJECT, str(gf.OUTPUT_ROOT), gf.GITHUB_OWNER, gf.GITHUB_REPO) == ("p", "/tmp/out", "o", "n")
    assert gf.GATES == (("G", "f", "r_", "exp/1"),) and gf.LAB_GROUP == "g"
    assert "/envs/p/" in gf.PROJECT_MARKERS and gf.PEOPLE == {"a": "A B"}


def test_last_update_is_per_project(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One post log serves every project; old survival lines have no project column."""
    gf = _load("gather_facts")
    log = tmp_path / "update_me_posted.log"
    log.write_text(
        "2026-10-01T08:00\tCSURV\tmhallet\n"            # survival, before 2026-10-14
        "2026-10-02T09:00\tCOTHER\tmhallet\tother\n"
        "2026-10-03T10:00\tCX\tmhallet\tx_proj\n"
        "2026-10-04T11:00\tCOTHER\tmhallet\tother\n",
        encoding="utf-8")
    monkeypatch.setattr(gf, "POST_LOG", log)
    gf.configure(repo, {})
    assert gf.last_post_time().isoformat(timespec="minutes") == "2026-10-03T10:00"
    gf.configure(repo, {"project": "survival", "channel": "CSURV"})
    assert gf.last_post_time().isoformat(timespec="minutes") == "2026-10-01T08:00"
    gf.configure(repo, {"project": "never_posted"})
    assert gf.last_post_time() is None


def test_small_counts_refused_unless_explicitly_allowed(repo: Path) -> None:
    ps = _load("post_summary")
    _marker(repo, {"murmurent": 1, "lab": "mh", "update_me": {"channel": "C1"}})
    ps.configure()
    assert ps.check_rules("- 3 patients were excluded")
    ps = _load("post_summary")
    _marker(repo, {"murmurent": 1, "lab": "mh", "update_me": {"channel": "C1", "allow_small_counts": True}})
    ps.configure()
    assert ps.check_rules("- 3 samples failed QC") == []
    assert ps.check_rules("- a dash — here")              # the other rules stay on


def test_no_channel_stops_with_a_sentence(repo: Path) -> None:
    ps = _load("post_summary")
    _marker(repo, {"murmurent": 1, "lab": "mh"})
    ps.configure()
    with pytest.raises(ps.StopWithMessage, match="update_me.channel"):
        ps.post("hello")


def test_channel_lab_and_project_come_from_the_marker(repo: Path) -> None:
    ps = _load("post_summary")
    _marker(repo, {"murmurent": 1, "lab": "lab_mh", "name": "survival", "update_me": {"channel": "C0C4LCYNNMS"}})
    ps.configure()
    assert (ps.PROJECT, ps.SLACK_GROUP, ps.CHANNEL_ID) == ("survival", "mh", "C0C4LCYNNMS")
    ps.configure("COVERRIDE")
    assert ps.CHANNEL_ID == "COVERRIDE"
