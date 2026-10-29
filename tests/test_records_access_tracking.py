"""Members not getting access to the lab records repo (``murmurent_lab_mgmt_<lab>``).

A collaborator grant is only an invitation. These tests pin the pieces that
turn a blind grant into something both sides can see:

  * group-reconcile reads collaborators AND pending invitations, and reports
    each member as access / pending / expired / none
  * an expired invitation is deleted and resent on --apply; a pending one gets
    a reminder DM with the accept link
  * the clone hint uses ``gh repo clone`` (works with HTTPS or SSH sign-in)
  * the member-side probe names which of the four causes applies
  * ``murmurent init`` refuses a GitHub login GitHub does not know
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from murmurent.core import group_reconcile as _gr
from murmurent.core import lab_records as _lr
from murmurent.commands import doctor_cmd, init_cmd


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _fake_gh(responses: dict, calls: list | None = None, default_rc: int = 1):
    """A subprocess.run stand-in: ``responses`` maps a substring of the joined
    command to (returncode, stdout, stderr)."""
    def run(cmd, **kwargs):
        if calls is not None:
            calls.append(cmd)
        joined = " ".join(cmd)
        for key, (rc, out, err) in responses.items():
            if key in joined:
                return SimpleNamespace(returncode=rc, stdout=out, stderr=err)
        return SimpleNamespace(returncode=default_rc, stdout="", stderr="no match")
    return run


# ---------------------------------------------------------------------------
# access state + classification
# ---------------------------------------------------------------------------


def test_access_state_reads_collaborators_and_invitations():
    collabs = json.dumps([{"login": "Alice"}, {"login": "owner"}])
    invites = json.dumps([
        {"id": 11, "invitee": {"login": "Bob"}, "created_at": _iso(2), "expired": False,
         "html_url": "https://github.com/org/lab/invitations"},
        {"id": 12, "invitee": {"login": "carol"}, "created_at": _iso(10), "expired": True},
    ])
    state = _gr.lab_mgmt_access_state("org/lab", runner=_fake_gh({
        "/collaborators": (0, collabs, ""), "/invitations": (0, invites, "")}))
    assert state["collaborators"] == {"alice", "owner"}
    assert set(state["invitations"]) == {"bob", "carol"}
    assert state["invitations"]["carol"]["expired"] is True
    assert state["invitations"]["carol"]["url"].endswith("/invitations")


def test_access_state_is_none_when_github_cannot_be_asked():
    assert _gr.lab_mgmt_access_state("org/lab", runner=_fake_gh({})) is None
    assert _gr.lab_mgmt_access_state("", runner=_fake_gh({})) is None


@pytest.mark.parametrize("login, state, kind", [
    ("alice", {"collaborators": {"alice"}, "invitations": {}}, "access"),
    ("@Alice", {"collaborators": {"alice"}, "invitations": {}}, "access"),
    ("bob", {"collaborators": set(), "invitations": {
        "bob": {"id": 1, "created_at": _iso(2), "expired": False, "url": "u"}}}, "pending"),
    ("bob", {"collaborators": set(), "invitations": {
        "bob": {"id": 1, "created_at": _iso(9), "expired": False, "url": "u"}}}, "expired"),
    ("bob", {"collaborators": set(), "invitations": {
        "bob": {"id": 1, "created_at": _iso(1), "expired": True, "url": "u"}}}, "expired"),
    ("dave", {"collaborators": set(), "invitations": {}}, "none"),
    ("dave", None, "unknown"),
])
def test_describe_member_access(login, state, kind):
    got, detail = _gr.describe_member_access(login, state)
    assert got == kind
    if kind == "pending":
        assert "expires in" in detail and "u" in detail


# ---------------------------------------------------------------------------
# reconcile: report, resend, nudge
# ---------------------------------------------------------------------------


@pytest.fixture
def roster_world(monkeypatch):
    roster = {
        "alice": {"email": "a@x.edu", "github": "alice", "slack": "U1"},
        "bob": {"email": "b@x.edu", "github": "bob", "slack": "U2"},
        "carol": {"email": "c@x.edu", "github": "carol", "slack": ""},
        "dave": {"email": "d@x.edu", "github": "dave", "slack": ""},
        "nokey": {"email": "n@x.edu", "github": "", "slack": ""},
    }
    monkeypatch.setattr(_gr, "group_roster", lambda g, env=None: roster)
    monkeypatch.setattr(_gr, "lab_mgmt_repo_slug", lambda: "org/lab")
    monkeypatch.setattr(_gr, "resolve_group_slack_token", lambda g: "")
    from murmurent.core import registrar as _R
    monkeypatch.setattr(_R, "read_group_profile", lambda g, env=None: {})
    state = {
        "collaborators": {"alice"},
        "invitations": {
            "bob": {"id": 1, "created_at": _iso(1), "expired": False,
                    "url": "https://github.com/org/lab/invitations"},
            "carol": {"id": 2, "created_at": _iso(12), "expired": True,
                      "url": "https://github.com/org/lab/invitations"},
        },
    }
    return state


def _line(res, handle):
    return next(line for line in res.lab_mgmt if line.startswith(f"@{handle}"))


def test_reconcile_report_classifies_every_member(roster_world):
    res = _gr.group_reconcile("mh", workspace_checker=lambda e: None,
                              access_fetcher=lambda repo: roster_world)
    assert "✓" in _line(res, "alice")
    assert "not yet accepted" in _line(res, "bob") and "invitations" in _line(res, "bob")
    assert "expired" in _line(res, "carol") and "--apply" in _line(res, "carol")
    assert "would grant" in _line(res, "dave")
    assert "no GitHub login" in _line(res, "nokey")


def test_reconcile_apply_resends_expired_grants_new_and_nudges_pending(roster_world):
    granted, resent, dms = [], [], []
    res = _gr.group_reconcile(
        "mh", apply=True, workspace_checker=lambda e: None,
        access_fetcher=lambda repo: roster_world,
        lab_mgmt_granter=lambda repo, login: (granted.append(login) or (True, "ok")),
        invitation_resender=lambda repo, login, st: (resent.append(login) or (True, "ok")),
        dm_sender=lambda member, text: (dms.append((member["email"], text)) or (True, "ok")),
    )
    assert granted == ["dave"]          # never invited → invited now
    assert resent == ["carol"]          # expired → deleted + resent
    nudged = sorted(e for e, _ in dms)
    assert nudged == ["b@x.edu", "c@x.edu", "d@x.edu"]   # alice already has access
    bob_text = next(t for e, t in dms if e == "b@x.edu")
    assert "https://github.com/org/lab/invitations" in bob_text
    assert "gh repo clone org/lab" in bob_text
    assert "reminder DM sent" in res.lab_mgmt[res.lab_mgmt.index(_line(res, "bob")) + 1]


def test_reconcile_says_when_github_is_unreadable_and_still_grants(roster_world):
    granted = []
    res = _gr.group_reconcile(
        "mh", apply=True, workspace_checker=lambda e: None,
        access_fetcher=lambda repo: None,
        lab_mgmt_granter=lambda repo, login: (granted.append(login) or (True, "ok")),
        dm_sender=lambda member, text: (False, "no token"))
    assert any("could not read who has access" in line for line in res.lab_mgmt)
    assert sorted(granted) == ["alice", "bob", "carol", "dave"]


def test_reconcile_owner_is_never_invited(roster_world, monkeypatch):
    roster_world["collaborators"] = set()
    monkeypatch.setattr(_gr, "group_roster",
                        lambda g, env=None: {"pi": {"email": "", "github": "org", "slack": ""}})
    granted = []
    res = _gr.group_reconcile("mh", apply=True, workspace_checker=lambda e: None,
                              access_fetcher=lambda repo: roster_world,
                              lab_mgmt_granter=lambda r, l: (granted.append(l) or (True, "")),
                              dm_sender=lambda m, t: (True, ""))
    assert granted == [] and "owns org/lab" in _line(res, "pi")


def test_resend_deletes_the_expired_invitation_first():
    calls = []
    state = {"collaborators": set(), "invitations": {
        "carol": {"id": 42, "created_at": _iso(12), "expired": True, "url": "u"}}}
    ok, _ = _gr.resend_lab_mgmt_invitation(
        "carol", state, repo="org/lab", runner=_fake_gh({"DELETE": (0, "", ""),
                                                          "PUT": (0, "", "")}, calls))
    assert ok
    assert any("DELETE" in c and "invitations/42" in " ".join(c) for c in calls)
    assert any("PUT" in c and "collaborators/carol" in " ".join(c) for c in calls)
    assert calls.index(next(c for c in calls if "DELETE" in c)) < \
        calls.index(next(c for c in calls if "PUT" in c))


# ---------------------------------------------------------------------------
# personal-account repo: read-only refused by the API
# ---------------------------------------------------------------------------

_CANNOT = (1, "", "gh: Cannot assign bob permission of read (Validation Failed)")


def _personal_repo_runner(calls, *, patch_ok=True, already=False):
    def run(cmd, **kwargs):
        calls.append(cmd)
        joined = " ".join(cmd)
        if "permission=pull" in joined:
            return SimpleNamespace(returncode=_CANNOT[0], stdout="", stderr=_CANNOT[2])
        if "-X PUT" in joined and "collaborators" in joined:
            out = "" if already else json.dumps({"id": 77, "invitee": {"login": "bob"}})
            return SimpleNamespace(returncode=0, stdout=out, stderr="")
        if "PATCH" in joined and "invitations/77" in joined:
            return SimpleNamespace(returncode=0 if patch_ok else 1, stdout="", stderr="422")
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected " + joined)
    return run


def test_personal_repo_falls_back_to_invite_then_downgrade():
    calls = []
    ok, detail = _gr.grant_lab_mgmt_read("bob", repo="me/lab", runner=_personal_repo_runner(calls))
    assert ok and detail == "invited (read-only)"
    joined = [" ".join(c) for c in calls]
    assert "permission=pull" in joined[0]
    assert joined[1].endswith("repos/me/lab/collaborators/bob")       # no permission field
    assert "PATCH" in joined[2] and "permissions=read" in joined[2]


def test_personal_repo_reports_write_when_downgrade_refused():
    calls = []
    ok, detail = _gr.grant_lab_mgmt_read(
        "bob", repo="me/lab", runner=_personal_repo_runner(calls, patch_ok=False))
    assert ok and "WRITE access" in detail and "settings/access" in detail


def test_personal_repo_existing_collaborator_is_left_alone():
    calls = []
    ok, detail = _gr.grant_lab_mgmt_read(
        "bob", repo="me/lab", runner=_personal_repo_runner(calls, already=True))
    assert ok and "already a collaborator" in detail
    assert not any("PATCH" in " ".join(c) for c in calls)


def test_other_422s_are_not_retried():
    calls = []
    ok, detail = _gr.grant_lab_mgmt_read(
        "bob", repo="me/lab",
        runner=_fake_gh({"permission=pull": (1, "", "gh: Not Found (HTTP 404)")}, calls))
    assert not ok and len(calls) == 1


def test_report_flags_write_holders(roster_world):
    roster_world["roles"] = {"alice": "write"}
    res = _gr.group_reconcile("mh", workspace_checker=lambda e: None,
                              access_fetcher=lambda repo: roster_world)
    assert "write access" in _line(res, "alice") and "settings/access" in _line(res, "alice")


# ---------------------------------------------------------------------------
# clone command
# ---------------------------------------------------------------------------


def test_clone_command_uses_gh_repo_clone(monkeypatch):
    from murmurent.core import repo as _repo
    monkeypatch.setattr(_repo, "repos_root_for_display", lambda: "~/repos")
    cmd = _gr.records_clone_command("org/murmurent_lab_mgmt_mh", "mh")
    assert cmd == "gh repo clone org/murmurent_lab_mgmt_mh ~/repos/murmurent_lab_mgmt_mh"
    assert _gr.records_clone_command("", "mh") == ""


@pytest.mark.parametrize("url", [
    "git@github.com:org/murmurent_lab_mgmt_mh.git",
    "https://github.com/org/murmurent_lab_mgmt_mh.git",
    "https://github.com/org/murmurent_lab_mgmt_mh",
    "ssh://git@github.com/org/murmurent_lab_mgmt_mh.git",
])
def test_github_slug_from_any_remote(url):
    from murmurent.core import repo as _repo
    assert _repo.github_slug(url) == "org/murmurent_lab_mgmt_mh"
    assert _repo.github_slug("https://gitlab.com/org/x.git") == ""


# ---------------------------------------------------------------------------
# member-side probe
# ---------------------------------------------------------------------------


@pytest.fixture
def member_with_remote(monkeypatch):
    monkeypatch.setattr(_lr, "records_remote",
                        lambda group: "git@github.com:org/murmurent_lab_mgmt_mh.git")
    from murmurent.core import member_profile as _mp
    monkeypatch.setattr(_mp, "read_profile", lambda: {"github": "bob"})


def test_probe_no_gh(member_with_remote):
    acc = _lr.records_access_probe("mh", which=lambda name: None)
    assert acc.kind == "no_gh" and "gh auth login" in acc.fix


def test_probe_not_signed_in(member_with_remote):
    acc = _lr.records_access_probe("mh", which=lambda n: "/usr/bin/gh",
                                   runner=_fake_gh({"auth status": (1, "", "not logged in")}))
    assert acc.kind == "not_signed_in" and acc.fix == "gh auth login"


def test_probe_has_access(member_with_remote):
    acc = _lr.records_access_probe("mh", which=lambda n: "/usr/bin/gh", runner=_fake_gh({
        "auth status": (0, "", ""), "api user": (0, "bob\n", ""),
        "repos/org/murmurent_lab_mgmt_mh": (0, "org/murmurent_lab_mgmt_mh\n", "")}))
    assert acc.kind == "access" and acc.login == "bob" and acc.slug == "org/murmurent_lab_mgmt_mh"


def test_probe_no_access_points_at_invitations(member_with_remote):
    acc = _lr.records_access_probe("mh", which=lambda n: "/usr/bin/gh", runner=_fake_gh({
        "auth status": (0, "", ""), "api user": (0, "bob\n", ""),
        "repos/org/murmurent_lab_mgmt_mh": (1, "", "gh: Not Found (HTTP 404)")}))
    assert acc.kind == "no_access"
    assert "github.com/org/murmurent_lab_mgmt_mh/invitations" in acc.fix
    assert "group-reconcile mh --apply" in acc.fix


def test_probe_wrong_account(member_with_remote):
    acc = _lr.records_access_probe("mh", which=lambda n: "/usr/bin/gh", runner=_fake_gh({
        "auth status": (0, "", ""), "api user": (0, "bobby\n", ""),
        "repos/org/murmurent_lab_mgmt_mh": (1, "", "gh: Not Found (HTTP 404)")}))
    assert acc.kind == "wrong_account"
    assert "bobby" in acc.detail and "bob" in acc.detail


def test_probe_unknown_remote(monkeypatch):
    monkeypatch.setattr(_lr, "records_remote", lambda group: "")
    acc = _lr.records_access_probe("mh", which=lambda n: "/usr/bin/gh", runner=_fake_gh({
        "auth status": (0, "", ""), "api user": (0, "bob\n", "")}))
    assert acc.kind == "unknown" and "gh repo clone" in acc.fix


# ---------------------------------------------------------------------------
# doctor check
# ---------------------------------------------------------------------------


def _status(present: bool):
    return _lr.RecordsStatus(group="mh", path="/r/murmurent_lab_mgmt_mh", present=present,
                             is_git=present, remote="", hint="Clone the lab records ...")


def test_doctor_no_card_is_ok(monkeypatch):
    monkeypatch.setattr(_lr, "records_status", lambda: None)
    c = doctor_cmd.check_lab_records()
    assert c.status == doctor_cmd.OK


def test_doctor_clone_present_is_ok(monkeypatch):
    monkeypatch.setattr(_lr, "records_status", lambda: _status(True))
    assert doctor_cmd.check_lab_records().status == doctor_cmd.OK


def test_doctor_no_access_fails_with_the_fix(monkeypatch):
    monkeypatch.setattr(_lr, "records_status", lambda: _status(False))
    monkeypatch.setattr(_lr, "records_access_probe", lambda g: _lr.RecordsAccess(
        "no_access", "org/lab", login="bob", detail="bob cannot read org/lab", fix="check X"))
    c = doctor_cmd.check_lab_records()
    assert c.status == doctor_cmd.FAIL and c.fix == "check X" and "cannot read" in c.detail


def test_doctor_access_but_not_cloned_warns_with_clone_hint(monkeypatch):
    monkeypatch.setattr(_lr, "records_status", lambda: _status(False))
    monkeypatch.setattr(_lr, "records_access_probe", lambda g: _lr.RecordsAccess(
        "access", "org/lab", login="bob", detail="bob can read org/lab"))
    c = doctor_cmd.check_lab_records()
    assert c.status == doctor_cmd.WARN and c.fix.startswith("Clone the lab records")


# ---------------------------------------------------------------------------
# init: verify the login
# ---------------------------------------------------------------------------


def _ask(answers: list[str], *, lookup, confirm_answer=False, signed_in=""):
    echoed = []
    it = iter(answers)
    got = init_cmd._ask_github_login(
        prompt=lambda text, default="": next(it),
        confirm=lambda text, default=False: confirm_answer,
        echo=echoed.append, lookup=lookup, signed_in=lambda: signed_in)
    return got, echoed


def test_init_refuses_an_unknown_login_then_accepts_a_real_one():
    got, echoed = _ask(["bobb", "@bob"], lookup=lambda l: l == "bob")
    assert got == "bob"
    assert any("no account named 'bobb'" in e for e in echoed)


def test_init_blank_login_needs_confirmation():
    got, echoed = _ask(["", "bob"], lookup=lambda l: True, confirm_answer=False)
    assert got == "bob" and any("cannot give you access" in e for e in echoed)
    got, _ = _ask([""], lookup=lambda l: True, confirm_answer=True)
    assert got == ""


def test_init_accepts_unverifiable_login_with_a_note():
    got, echoed = _ask(["bob"], lookup=lambda l: None)
    assert got == "bob" and any("could not check" in e for e in echoed)


def test_init_prompt_defaults_to_the_signed_in_account():
    seen = {}
    init_cmd._ask_github_login(
        prompt=lambda text, default="": seen.setdefault("default", default) or "bob",
        confirm=lambda t, default=False: False, echo=lambda s: None,
        lookup=lambda l: True, signed_in=lambda: "bob")
    assert seen["default"] == "bob"
