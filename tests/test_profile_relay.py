"""A member's profile change reaches the PI and the roster (#187).

GitHub is never called: a fake `gh` runner records what would be sent and
returns canned answers. The roster is a throwaway git repository.
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest
import yaml

from murmurent.core import member_profile as mp
from murmurent.core import profile_relay as pr
from murmurent.core.frontmatter import parse_file


def _cp(rc=0, out="", err=""):
    return SimpleNamespace(returncode=rc, stdout=out, stderr=err)


class FakeGh:
    def __init__(self, issues=None):
        self.calls: list[list[str]] = []
        self.issues = issues or []

    def __call__(self, argv):
        self.calls.append(argv)
        if argv[:2] == ["issue", "list"]:
            return _cp(0, json.dumps(self.issues))
        if argv[:2] == ["issue", "create"]:
            return _cp(0, "https://github.com/lab/mgmt/issues/7\n")
        return _cp(0, "")


def test_body_round_trip():
    body = pr.render_body("@Bob", {"handle": "@bob", "contact": {"orcid": "0000-1", "email": ""}})
    assert pr.parse_body(body) == ("bob", {"contact": {"orcid": "0000-1", "email": ""}})
    assert pr.parse_body("just text") is None


def test_send_creates_then_updates():
    gh = FakeGh()
    res = pr.send_profile_update("bob", {"contact": {"orcid": "1"}}, run=gh, slug="lab/mgmt")
    assert res.ok and res.issue == 7
    assert any(c[:2] == ["issue", "create"] and "Profile update: @bob" in c for c in gh.calls)
    gh2 = FakeGh(issues=[{"number": 7, "title": "Profile update: @bob"}])
    res2 = pr.send_profile_update("bob", {"contact": {"orcid": "2"}}, run=gh2, slug="lab/mgmt")
    assert res2.ok and any(c[:3] == ["issue", "edit", "7"] for c in gh2.calls)


def test_send_without_a_github_copy_says_so(monkeypatch):
    monkeypatch.setattr(pr, "lab_mgmt_slug", lambda root=None: None)
    res = pr.send_profile_update("bob", {}, run=FakeGh())
    assert not res.ok and "tell them directly" in res.detail


@pytest.fixture
def roster(tmp_path):
    root = tmp_path / "lab-mgmt"
    (root / "members").mkdir(parents=True)
    (root / "members" / "bob.md").write_text(
        "---\nhandle: '@bob'\ngit_logins:\n  github: bobgh\ncontact:\n  email: old@x\n---\n# @bob\n")
    (root / "members" / "eve.md").write_text("---\nhandle: '@eve'\n---\n")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"]}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "seed"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True, env=env, capture_output=True)
    return root


def _issue(n, handle, author, edits):
    return {"number": n, "title": f"Profile update: @{handle}", "author": {"login": author},
            "body": pr.render_body(handle, edits)}


def test_ingest_applies_only_the_members_own_issue(roster):
    gh = FakeGh(issues=[
        _issue(1, "bob", "bobgh", {"contact": {"email": "new@x", "orcid": "9"},
                                   "git_logins": {"github": "attacker"}}),
        _issue(2, "bob", "mallory", {"contact": {"email": "evil@x"}}),
        _issue(3, "eve", "evegh", {"contact": {"email": "e@x"}}),
    ])
    rep = pr.ingest_profile_updates(apply=True, run=gh, slug="lab/mgmt", lab_mgmt=roster)
    by = {i.issue: i for i in rep.items}
    assert by[1].applied
    assert not by[2].applied and "not applied" in by[2].detail
    assert not by[3].applied and "no GitHub login" in by[3].detail
    meta = parse_file(roster / "members" / "bob.md").meta
    assert meta["contact"]["email"] == "new@x" and meta["contact"]["orcid"] == "9"
    assert meta["git_logins"]["github"] == "bobgh"            # never changed from an issue
    log = subprocess.run(["git", "-C", str(roster), "log", "--format=%s"],
                         capture_output=True, text=True).stdout
    assert "profile update from @bob" in log
    assert any(c[:3] == ["issue", "close", "1"] for c in gh.calls)
    assert not any(c[:3] == ["issue", "close", "2"] for c in gh.calls)


def test_ingest_dry_run_changes_nothing(roster):
    gh = FakeGh(issues=[_issue(1, "bob", "bobgh", {"contact": {"email": "new@x"}})])
    rep = pr.ingest_profile_updates(apply=False, run=gh, slug="lab/mgmt", lab_mgmt=roster)
    assert rep.items[0].detail == "would apply"
    assert parse_file(roster / "members" / "bob.md").meta["contact"]["email"] == "old@x"


def test_staging_travels_in_the_vault(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    vault = tmp_path / "vault"
    vault.mkdir()
    from murmurent.core import vault_sync
    monkeypatch.setattr(vault_sync, "personal_vault_root", lambda: vault)
    path = mp.stage_roster_profile("bob", {"contact": {"orcid": "1"}})
    assert path == vault / "profile" / "roster_profile.yaml"
    assert yaml.safe_load(path.read_text())["contact"]["orcid"] == "1"
    # Another machine: no local profile.yaml, but the same vault.
    (tmp_path / "home" / "profile.yaml").unlink()
    assert mp.staged_roster_profile("bob")["contact"]["orcid"] == "1"
