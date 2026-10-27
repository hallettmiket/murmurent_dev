"""
Purpose: everyone sees every project they are involved with, not only the PI.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-27
Input: an identity card naming two groups, a records repo for each under a
       throwaway repositories folder, and one project card for a project
       hosted by a third lab. No network.
Output: pass or fail.

A person sees: their own groups' projects (recorded in each group's lab
records), any project that lists them, and any project they hold a project
card for. A project of another lab that merely sits in a repo they can read,
without listing them, stays hidden.
"""

from __future__ import annotations

import json

import pytest

from murmurent.core import cert_projects as CP
from murmurent.core import identity_card as IC
from murmurent.core import project_lens as L
from murmurent.core import repo as _repo


def _records(root, group: str, pi: str, members: list[str]):
    d = root / f"murmurent_lab_mgmt_{group}"
    (d / "members").mkdir(parents=True)
    (d / "lab.md").write_text(f"---\nlab: {group}\nname: {group}\npi: '@{pi}'\nkind: lab\n---\n")
    for h in members:
        (d / "members" / f"{h}.md").write_text(f"---\nhandle: '@{h}'\nstatus: active\n---\n")
    return d


def _project(records_dir, name: str, *, lab: str, members: list[str], status="active"):
    with _repo.use_lab_mgmt_root(records_dir):
        for m in members:
            CP.upsert(name, lab=lab, member=f"@{m}", lead="@the_pi")
        if status != "active":
            CP.set_status(name, status)


@pytest.fixture
def two_groups(monkeypatch, tmp_path):
    """@bob: member of mh and of seq. mh's records hold 3 projects, seq's 1."""
    repos = tmp_path / "repos"
    repos.mkdir()
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "home" / "lab_info"))
    monkeypatch.delenv("MURMURENT_LAB_MGMT_REPO", raising=False)
    monkeypatch.setenv("MURMURENT_USER", "bob")
    IC.import_card({"version": 1, "netname": "bob", "centre": "qa", "roles": [
        {"kind": "member", "group": "mh", "pi": "@the_pi", "group_kind": "lab"},
        {"kind": "member", "group": "seq", "pi": "@core_pi", "group_kind": "core"},
    ]})
    mh = _records(repos, "mh", "the_pi", ["the_pi", "bob", "amy"])
    seq = _records(repos, "seq", "core_pi", ["core_pi", "bob"])
    _project(mh, "atlas", lab="mh", members=["the_pi", "amy"])          # mh project, bob not on it
    _project(mh, "coin", lab="mh", members=["the_pi", "bob"])           # mh project, bob on it
    _project(mh, "guest", lab="other", members=["the_pi", "bob"])       # another lab's, lists bob
    _project(mh, "foreign", lab="other", members=["the_pi"])            # another lab's, not bob
    _project(mh, "old", lab="mh", members=["bob"], status="archived")
    _project(seq, "pipeline", lab="seq", members=["core_pi"])           # seq project
    return repos


def test_member_sees_their_groups_projects_and_the_ones_listing_them(two_groups):
    seen = {v.name: v for v in L.visible_projects("bob")}
    assert set(seen) == {"atlas", "coin", "guest", "old", "pipeline"}
    assert "foreign" not in seen
    assert seen["atlas"].on_it is False and seen["coin"].on_it is True
    assert seen["pipeline"].lab == "seq" and seen["pipeline"].source == "records"
    assert seen["old"].status == "archived"


def test_viewer_groups_come_from_the_card(two_groups):
    assert [(g, p.name) for g, p in L.viewer_group_paths("bob")] == [
        ("mh", "murmurent_lab_mgmt_mh"), ("seq", "murmurent_lab_mgmt_seq")]


def test_a_project_card_shows_a_project_hosted_elsewhere(two_groups, tmp_path):
    from murmurent.core.issuance import cards_dir
    cards_dir().mkdir(parents=True, exist_ok=True)
    (cards_dir() / "qa_project_xlab_crossover.json").write_text(json.dumps({
        "project_card": {"payload": {"kind": "member", "group": "xlab/crossover",
                                     "subject": {"handle": "@bob"}}, "signature": "x"},
        "lead_card": {}, "pi_card": {}}))
    seen = {v.name: v for v in L.visible_projects("bob")}
    assert "crossover" in seen
    v = seen["crossover"]
    assert v.source == "card" and v.lab == "xlab" and v.on_it and v.record is None


def test_someone_elses_project_card_is_not_mine(two_groups):
    from murmurent.core.issuance import cards_dir
    cards_dir().mkdir(parents=True, exist_ok=True)
    (cards_dir() / "qa_project_xlab_theirs.json").write_text(json.dumps({
        "project_card": {"payload": {"kind": "member", "group": "xlab/theirs",
                                     "subject": {"handle": "@amy"}}, "signature": "x"}}))
    assert "theirs" not in {v.name for v in L.visible_projects("bob")}


def test_dashboard_rows_say_which_lab_hosts_a_project(two_groups, monkeypatch):
    import datetime as dt
    from murmurent.dashboard import snapshot
    resp = snapshot.build_response("bob", today=dt.date(2026, 10, 27))
    rows = {r.name: r for r in resp.projects}
    assert set(rows) == {"atlas", "coin", "guest", "pipeline"}     # archived hidden
    assert rows["atlas"].hosted_by is None
    assert rows["pipeline"].hosted_by == "seq"
    assert rows["guest"].hosted_by == "other"
    assert rows["pipeline"].source == "records"


def test_an_explicit_repo_pin_narrows_the_lens_to_that_repo(two_groups, monkeypatch):
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(two_groups / "murmurent_lab_mgmt_seq"))
    assert {v.name for v in L.visible_projects("bob")} == {"pipeline"}
