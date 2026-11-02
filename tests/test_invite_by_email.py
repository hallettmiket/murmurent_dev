"""
Purpose: Issue #258. A project member may be added by email: an address
         murmurent knows becomes its handle; any other records an invitation
         on the project and drafts the email to send; the enrollment that
         arrives settles the invitation.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   temporary folders; keys made on the fly.
Output:  pass or fail.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from murmurent.cli import cli
from murmurent.core import cert_projects as CP
from murmurent.core import idcert as C
from murmurent.core import idkeys as K
from murmurent.core import issuance as ISS
from murmurent.core import membership as MEM
from murmurent.core import project_invites as INV
from murmurent.core import project_members as PM


@pytest.fixture
def lab(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "pi_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "pi_li"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab_mgmt"))
    monkeypatch.setenv("MURMURENT_GROUP_SLACK_TOKEN", "xoxb-test")
    monkeypatch.setenv("MURMURENT_USER", "pi")
    K.generate_keypair()
    out = ISS.self_issue_pi_card("@pi", "mh")
    priv = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@allie", priv=priv, nonce="n", group="mh",
                                    email="allie@x.edu", slack="allieslack")
    ISS.issue_member_card("@allie", enrollment=req, group="mh")
    MEM.upsert_member("@allie", email="allie@x.edu")
    ISS.issue_project_lead_card("@pi", project="atlas")
    CP.upsert("atlas", lab="mh", slack_channel_id="CATLAS")
    return {"trust": out["trust_root"]}


def test_is_email():
    assert INV.is_email("tyler@uwo.ca") and INV.is_email(" A.B@c.d ")
    assert not INV.is_email("@tyler") and not INV.is_email("tyler") and not INV.is_email("")


def test_a_known_email_becomes_the_handle(lab):
    assert INV.resolve_email("Allie@X.edu") == "allie"
    assert INV.resolve_email("nobody@x.edu") == ""
    out = PM.add_member("atlas", "allie@x.edu", dm=False)
    assert out["ok"] and out["handle"] == "allie"
    assert "@allie" in CP.get("atlas").members and not CP.get("atlas").invited


def test_an_unknown_email_is_recorded_and_drafted(lab):
    opened = []
    out = PM.add_member("atlas", "Tyler@UWO.ca", actor="@pi", open_mail=True,
                        mail_opener=lambda mailto: opened.append(mailto) or True)
    assert not out["ok"] and out["error"] == "invited" and out["recorded"]
    assert out["opened"] and opened[0].startswith("mailto:tyler@uwo.ca")
    assert out["email"] == "tyler@uwo.ca"
    rows = CP.get("atlas").invited
    assert len(rows) == 1 and rows[0]["email"] == "tyler@uwo.ca" and rows[0]["by"] == "@pi"
    assert "tyler@uwo.ca" not in " ".join(CP.get("atlas").members)
    body = out["draft"]["body"]
    assert "murmurent enroll --project atlas" in body
    assert f"--trust-root {lab['trust']}" in body
    assert "send the file it writes (enroll.json) back to @pi" in body
    assert out["draft"]["mailto"].startswith("mailto:tyler@uwo.ca?subject=")
    # inviting again refreshes rather than duplicates
    PM.add_member("atlas", "tyler@uwo.ca", actor="@pi")
    assert len(CP.get("atlas").invited) == 1


def test_open_mail_draft_uses_the_opener_and_is_quiet_without_one(lab, monkeypatch):
    calls = []
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    assert INV.open_mail_draft("mailto:x@y.z", opener="/usr/bin/open")
    assert calls and calls[0][0] == "/usr/bin/open" and calls[0][1].startswith("mailto:")
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert INV.open_mail_draft("mailto:x@y.z") is False


def test_the_enrollment_settles_the_invitation(lab):
    PM.add_member("atlas", "tyler@uwo.ca", actor="@pi")
    ext = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@tyler", priv=ext, nonce="e1",
                                    email="Tyler@uwo.ca", slack="tylerslack")
    out = PM.add_member("atlas", "@tyler", enrollment=req, dm=False)
    assert out["ok"]
    cp = CP.get("atlas")
    assert "@tyler" in cp.members and not cp.invited


def test_withdraw_an_invitation(lab):
    PM.add_member("atlas", "tyler@uwo.ca")
    assert INV.withdraw("atlas", "tyler@uwo.ca") is True
    assert not CP.get("atlas").invited
    assert INV.withdraw("atlas", "tyler@uwo.ca") is False


def test_invited_is_written_and_read_back(lab):
    CP.upsert("atlas", lab="mh", invited=[{"email": "a@b.c", "by": "@pi", "at": "2026-11-02"}])
    assert CP.get("atlas").invited[0]["email"] == "a@b.c"
    assert "invited" in CP.get("atlas").to_dict()


def test_cli_prints_the_draft_when_mail_is_not_opened(lab):
    out = CliRunner().invoke(cli, ["project-add-member", "tyler@uwo.ca", "--project", "atlas",
                                   "--no-open-mail"])
    assert out.exit_code == 0, out.output
    assert "tyler@uwo.ca is invited to atlas" in out.output
    assert "Subject: Joining the murmurent project atlas" in out.output
    assert "murmurent enroll --project atlas" in out.output


def test_cli_known_email_is_a_normal_add(lab, monkeypatch):
    monkeypatch.setattr(PM, "_default_dm_sender", lambda ws, **kw: (True, "sent"))
    out = CliRunner().invoke(cli, ["project-add-member", "allie@x.edu", "--project", "atlas"])
    assert out.exit_code == 0, out.output
    assert "@allie added to" in out.output


def test_dashboard_add_by_email(lab, monkeypatch):
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app
    monkeypatch.setattr(INV, "open_mail_draft", lambda *a, **k: False)
    client = TestClient(create_app())
    r = client.post("/api/project/atlas/members?user=pi",
                    json={"handle": "tyler@uwo.ca"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["error"] == "invited" and j["email"] == "tyler@uwo.ca"
    assert j["draft"]["mailto"].startswith("mailto:")
    assert CP.get("atlas").invited[0]["email"] == "tyler@uwo.ca"
