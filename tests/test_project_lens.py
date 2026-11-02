"""
Purpose: everyone sees every project they are involved with, not only the PI.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-27
Input: an identity card naming two groups, a records repo for each under a
       throwaway repositories folder, and one project card for a project
       hosted by a third lab. No network.
Output: pass or fail.

A person sees: any project that lists them, any project they hold a project
card for, and, when they are a group's PI, every project of that group
(#259). A project of their own lab that does not list them stays hidden from
a member; a project of another lab that merely sits in a repo they can read,
without listing them, stays hidden from everyone.
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


def test_member_sees_exactly_the_projects_listing_them(two_groups):
    """#259: a member no longer sees every project of their lab."""
    seen = {v.name: v for v in L.visible_projects("bob")}
    assert set(seen) == {"coin", "guest", "old"}
    assert "atlas" not in seen and "foreign" not in seen and "pipeline" not in seen
    assert seen["coin"].on_it is True
    assert seen["old"].status == "archived"


def test_the_pi_sees_every_project_of_their_group(two_groups, monkeypatch):
    monkeypatch.setenv("MURMURENT_USER", "the_pi")
    seen = {v.name: v for v in L.visible_projects("the_pi")}
    # atlas, coin, old: mh's projects (the_pi is mh's PI). guest and foreign
    # list the_pi. pipeline is seq's and does not list the_pi.
    assert set(seen) == {"atlas", "coin", "old", "guest", "foreign"}


def test_a_lead_sees_the_project_they_lead(two_groups):
    with _repo.use_lab_mgmt_root(two_groups / "murmurent_lab_mgmt_mh"):
        CP.upsert("ledbybob", lab="mh", lead="@bob")      # bob leads, is not listed
    assert "ledbybob" in {v.name for v in L.visible_projects("bob")}


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
    assert v.members == ("@bob",) and v.repos == () and v.as_of == ""


def test_a_card_bundle_carries_the_team_and_repositories(two_groups):
    """#259: the summary the lead's machine put in the bundle fills the row."""
    from murmurent.core.issuance import cards_dir
    cards_dir().mkdir(parents=True, exist_ok=True)
    (cards_dir() / "qa_project_xlab_shared.json").write_text(json.dumps({
        "project_card": {"payload": {"kind": "member", "group": "xlab/shared",
                                     "subject": {"handle": "@bob"}}, "signature": "x"},
        "lead_card": {}, "pi_card": {},
        "project_summary": {"name": "shared", "lab": "xlab", "lead": "@xpi",
                            "members": ["@xpi", "@bob", "@zed"],
                            "repos": [{"name": "shared", "role": "code",
                                       "remote_url": "git@github.com:xlab/shared.git"}],
                            "slack_workspace": "xlab", "slack_channel_id": "CX",
                            "as_of": "2026-11-02"}}))
    v = {v.name: v for v in L.visible_projects("bob")}["shared"]
    assert v.source == "card" and v.lead == "@xpi"
    assert v.members == ("@xpi", "@bob", "@zed")
    assert v.repos[0]["remote_url"].endswith("xlab/shared.git")
    assert v.slack_workspace == "xlab" and v.as_of == "2026-11-02"
    import datetime as dt
    from murmurent.dashboard import snapshot
    rows = {r.name: r for r in snapshot.build_response("bob", today=dt.date(2026, 11, 2)).projects}
    row = rows["shared"]
    assert row.hosted_by == "xlab" and row.card_as_of == "2026-11-02"
    assert sorted(row.cert_members) == ["@bob", "@xpi", "@zed"]
    assert [r["name"] for r in row.repos] == ["shared"]
    assert row.slack_url is None          # xlab's workspace is not known here


def test_host_records_on_this_machine_beat_the_card_summary(two_groups, monkeypatch):
    """When the host lab's records are on disk (the registry names them), the
    row comes from them, fresh, with source 'records'."""
    from murmurent.core.issuance import cards_dir
    from murmurent.core import registrar as REG
    xroot = _records(two_groups, "xlab", "xpi", ["xpi", "bob"])
    (xroot / "lab.md").write_text("---\nlab: xlab\nname: xlab\npi: '@xpi'\nkind: lab\n"
                                  "slack_workspace: xlab.slack.com\n---\n")
    _project(xroot, "shared", lab="xlab", members=["xpi", "bob"])
    monkeypatch.setattr(REG, "read_registry", lambda env=None: type("R", (), {
        "labs": [type("E", (), {"name": "xlab", "lab_mgmt_path": str(xroot),
                                "pi": "@xpi", "slack_workspace": None})()],
        "cores": []})())
    cards_dir().mkdir(parents=True, exist_ok=True)
    (cards_dir() / "qa_project_xlab_shared.json").write_text(json.dumps({
        "project_card": {"payload": {"kind": "member", "group": "xlab/shared",
                                     "subject": {"handle": "@bob"}}, "signature": "x"},
        "lead_card": {}, "pi_card": {},
        "project_summary": {"members": ["@stale"], "as_of": "2020-01-01"}}))
    v = {v.name: v for v in L.visible_projects("bob")}["shared"]
    assert v.source == "records" and v.record is not None
    assert set(v.members) == {"@xpi", "@bob"}
    assert CP.locate("shared")[0] is not None and CP.locate("shared")[1] == xroot


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
    assert set(rows) == {"coin", "guest"}     # archived hidden; only bob's (#259)
    assert rows["coin"].hosted_by is None
    assert rows["guest"].hosted_by == "other"
    assert rows["guest"].source == "records"


def test_an_explicit_repo_pin_narrows_the_lens_to_that_repo(two_groups, monkeypatch):
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(two_groups / "murmurent_lab_mgmt_seq"))
    assert {v.name for v in L.visible_projects("core_pi")} == {"pipeline"}
    assert {v.name for v in L.visible_projects("bob")} == set()   # seq's project, bob not on it
