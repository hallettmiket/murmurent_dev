"""
Purpose: tests for issue #243, "stray Slack messages": the one resolver that
         decides which channel a note about a repository goes to, and the
         removal of every fallback that used to send a project's notes to a
         shared development channel.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-30
Input: temporary folders only. No network, no real lab records.
Output: pass or fail.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from murmurent.core import cert_projects as cp
from murmurent.core import slack_routing as sr
from murmurent.dashboard import slack_notify as sn


@pytest.fixture
def world(monkeypatch, tmp_path):
    repos = tmp_path / "repos"
    lab_mgmt = tmp_path / "lab_mgmt"
    home = tmp_path / "mm_home"
    for d in (repos, lab_mgmt, home):
        d.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(home))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    # no registry in this world: the lab channel comes from a seam
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "")
    return {"repos": repos}


def marked_repo(root: Path, name: str, **marker) -> Path:
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    (p / ".murmurent.yaml").write_text(yaml.safe_dump({"murmurent": 1, "lab": "mh", **marker}))
    return p


def test_route_uses_the_owning_projects_channel(world):
    repo = marked_repo(world["repos"], "vc")
    cp.upsert("param_complexity", lab="mh", slack_channel_id="CPARAM",
              repos=[cp.RepoRef(name="vc", path=str(repo))])
    r = sr.resolve_route(repo)
    assert (r.channel_id, r.project, r.source) == ("CPARAM", "param_complexity", "project")
    assert "param_complexity" in r.describe()


def test_route_project_without_channel_posts_nowhere(world):
    repo = marked_repo(world["repos"], "bioinfo")
    cp.upsert("bioinfo", lab="mh", repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    r = sr.resolve_route(repo)
    assert not r.ok and r.channel_id == ""
    assert "provision-slack bioinfo" in r.reason


def test_route_goes_to_every_project_that_lists_the_repository(world):
    """A repository in several projects (#253): one note, each project's channel."""
    repo = marked_repo(world["repos"], "bioinfo")
    cp.upsert("bioinfo", lab="mh", slack_channel_id="CBIO",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    cp.upsert("teaching", lab="mh", slack_channel_id="CTEACH",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    r = sr.resolve_route(repo)
    assert r.ok and r.candidates == ["bioinfo", "teaching"]
    assert [(x.channel_id, x.project) for x in r.all] == [("CBIO", "bioinfo"), ("CTEACH", "teaching")]
    assert "project 'bioinfo'" in r.describe() and "project 'teaching'" in r.describe()


def test_route_skips_a_listing_project_without_a_channel(world):
    repo = marked_repo(world["repos"], "bioinfo")
    cp.upsert("bioinfo", lab="mh", repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    cp.upsert("teaching", lab="mh", slack_channel_id="CTEACH",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    r = sr.resolve_route(repo)
    assert r.ok and [x.channel_id for x in r.all] == ["CTEACH"]


def test_two_projects_sharing_one_channel_get_one_post(world):
    repo = marked_repo(world["repos"], "bioinfo")
    for name in ("bioinfo", "teaching"):
        cp.upsert(name, lab="mh", slack_channel_id="CSAME",
                  repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    assert [x.channel_id for x in sr.resolve_route(repo).all] == ["CSAME"]


def test_post_note_posts_to_each_project_and_reports_each(world, monkeypatch):
    repo = marked_repo(world["repos"], "bioinfo")
    cp.upsert("bioinfo", lab="mh", slack_channel_id="CBIO",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    cp.upsert("teaching", lab="mh", slack_channel_id="CTEACH",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    posted = []
    ok, _r, detail = sr.post_note("hello", start=repo, token="xoxb",
                                  poster=lambda ch, text, token=None: posted.append(ch) or True)
    assert ok and posted == ["CBIO", "CTEACH"]
    assert detail.count("posted to") == 2

    posted.clear()
    ok, _r, detail = sr.post_note("hello", start=repo, token="xoxb",
                                  poster=lambda ch, text, token=None: ch == "CBIO")
    assert not ok and "posted to CBIO" in detail and "refused the message for CTEACH" in detail


def test_route_marker_override_wins(world):
    repo = marked_repo(world["repos"], "murmurent_dev", slack_channel="CDEV12345")
    cp.upsert("Murmurent", lab="mh", slack_channel_id="CMURM",
              repos=[cp.RepoRef(name="murmurent_dev", path=str(repo))])
    r = sr.resolve_route(repo)
    assert (r.channel_id, r.source) == ("CDEV12345", "marker")


def test_route_marker_override_must_be_a_channel_id(world):
    repo = marked_repo(world["repos"], "x", slack_channel="#claude-test")
    r = sr.resolve_route(repo)
    assert not r.ok and "not a Slack channel id" in r.reason


def test_route_falls_back_to_the_lab_channel(world, monkeypatch):
    repo = marked_repo(world["repos"], "loose_repo")
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "CLAB" if lab == "mh" else "")
    r = sr.resolve_route(repo)
    assert (r.channel_id, r.source, r.lab) == ("CLAB", "lab", "mh")


def test_route_outside_any_repository(world, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    r = sr.resolve_route(plain)
    assert not r.ok and "not inside a murmurent repository" in r.reason


def test_route_by_explicit_project_name(world):
    cp.upsert("hockey", lab="mh", slack_channel_id="CHOCK")
    r = sr.resolve_route(project="hockey")
    assert (r.channel_id, r.source) == ("CHOCK", "project")
    assert not sr.resolve_route(project="nothing").ok


def test_post_note_posts_only_when_routed(world, monkeypatch):
    repo = marked_repo(world["repos"], "vc")
    cp.upsert("param_complexity", lab="mh", slack_channel_id="CPARAM",
              repos=[cp.RepoRef(name="vc", path=str(repo))])
    sent = []
    ok, route, detail = sr.post_note("hello", start=repo, token="tok",
                                     poster=lambda ch, text, token=None: sent.append((ch, text, token)) or True)
    assert ok and sent == [("CPARAM", "hello", "tok")] and detail.startswith("posted to CPARAM")

    other = marked_repo(world["repos"], "orphan")
    ok, route, detail = sr.post_note("hello", start=other, token="tok",
                                     poster=lambda *a, **k: sent.append("NO") or True)
    assert not ok and detail.startswith("not posted:") and "NO" not in sent


def test_project_channel_id_has_no_development_fallback(world, monkeypatch):
    # the old behaviour returned the deployment's dev channel for an unknown
    # project; now an unknown or channel-less project is simply empty
    monkeypatch.setattr(sn, "_CHAN_CLAUDE_CODE", "CDEVFALLBACK")
    assert sn._project_channel_id("never_heard_of_it") == ""
    cp.upsert("quiet", lab="mh")
    assert sn._project_channel_id("quiet") == ""
    cp.upsert("loud", lab="mh", slack_channel_id="CLOUD")
    assert sn._project_channel_id("loud") == "CLOUD"


def test_sea_state_change_skips_without_channel(world, monkeypatch):
    posted = []
    monkeypatch.setattr(sn, "_post", lambda ch, text, token=None: posted.append(ch) or True)
    cp.upsert("quiet", lab="mh")
    sn.sea_state_change(project="quiet", sea_id=1, actor="a", action="claim",
                        description="d", new_state="s")
    assert posted == []
    cp.upsert("loud", lab="mh", slack_channel_id="CLOUD")
    sn.sea_state_change(project="loud", sea_id=1, actor="a", action="claim",
                        description="d", new_state="s")
    assert posted == ["CLOUD"]
