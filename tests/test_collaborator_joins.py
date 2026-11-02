"""
Purpose: Issue #252. A member from another group can finish joining a
         project: the message that brings their bundle names the trust root
         and the exact import command; a pending member is sent the
         enrollment steps; ``import-card`` without a pinned root names the key
         and says "lab" for a lab that is its own root; ``enroll --project``
         points at ``project-add-member --enrollment``.
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
from murmurent.core import idcert as C
from murmurent.core import idkeys as K
from murmurent.core import issuance as ISS
from murmurent.core import project_members as PM


@pytest.fixture
def lab(monkeypatch, tmp_path):
    """A PI who is their own root (@mhallet, lab mh), one carded member
    (@allie) and a project 'faraday' the PI leads."""
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "pi_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "pi_li"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab_mgmt"))
    monkeypatch.setenv("MURMURENT_GROUP_SLACK_TOKEN", "xoxb-test")
    K.generate_keypair()
    out = ISS.self_issue_pi_card("@mhallet", "mh")
    priv = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@allie", priv=priv, nonce="n", group="mh",
                                    email="allie@x.edu", slack="allieslack")
    ISS.issue_member_card("@allie", enrollment=req, group="mh")
    ISS.issue_project_lead_card("@mhallet", project="faraday")
    return {"tmp": tmp_path, "trust": out["trust_root"]}


def _recorder(sent):
    def dm(workspace, *, text, slack="", email="", token=None,
           file_content=None, file_name="bundle.json"):
        sent.append({"workspace": workspace, "slack": slack, "email": email,
                     "text": text, "file_content": file_content})
        return (True, "recorded")
    return dm


def _outsider_bundle(lab):
    ext = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@tyler", priv=ext, nonce="e1",
                                    email="tyler@other.edu", slack="tylerslack")
    out = PM.add_member("faraday", "@tyler", enrollment=req, dm=False)
    assert out["ok"]
    return out["bundle"]


# ---------------------------------------------------------------------------
# the message that brings the bundle
# ---------------------------------------------------------------------------


def test_trust_root_of_a_self_rooted_bundle(lab):
    bundle = _outsider_bundle(lab)
    info = ISS.trust_root_of(bundle)
    assert info["self_rooted"] and info["lab"] == "mh"
    assert info["root"] == lab["trust"]
    assert info["realm"] == "mhallet-mh"
    assert info["import_command"] == \
        f"murmurent import-card bundle.json --trust-root {lab['trust']}"


def test_bundle_dm_names_the_root_and_the_full_command(lab):
    sent = []
    ext = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@tyler", priv=ext, nonce="e1",
                                    email="tyler@other.edu", slack="tylerslack")
    out = PM.add_member("faraday", "@tyler", enrollment=req,
                        dm_sender=_recorder(sent))
    assert out["ok"] and out["dm"]["sent"]
    text = sent[0]["text"]
    assert f"murmurent import-card bundle.json --trust-root {lab['trust']}" in text
    assert "lab 'mh'" in text
    assert "another route" in text          # confirm the key out of band
    assert sent[0]["file_content"]          # the bundle still travels as a file


def test_lead_bundle_dm_carries_the_root_too(lab):
    bundle = _outsider_bundle(lab)
    text = PM.bundle_dm_text("faraday", {"lead_card": bundle["lead_card"],
                                         "pi_card": bundle["pi_card"]},
                             kind="project LEAD card")
    assert "project LEAD card" in text and f"--trust-root {lab['trust']}" in text


# ---------------------------------------------------------------------------
# a pending member is told what to do
# ---------------------------------------------------------------------------


def test_pending_member_is_sent_the_enrollment_steps(lab):
    sent = []
    out = PM.add_member("faraday", "@tyler", record_pending=True,
                        dm_sender=_recorder(sent))
    assert not out["ok"] and out["recorded"] and out["dm"]["sent"]
    assert sent and "murmurent enroll --project faraday" in sent[0]["text"]
    assert sent[0]["slack"] == "tyler"       # no roster contact: the handle is tried
    assert sent[0]["file_content"] is None   # steps only, nothing to attach


def test_pending_member_without_dm_is_not_messaged(lab):
    sent = []
    out = PM.add_member("faraday", "@tyler", record_pending=True, dm=False,
                        dm_sender=_recorder(sent))
    assert out["recorded"] and not out["dm"]["sent"] and not sent


def test_pending_dm_failure_is_reported_not_raised(lab):
    def failing(workspace, **kw):
        return (False, "couldn't find tyler in the group's Slack workspace")
    out = PM.add_member("faraday", "@tyler", record_pending=True, dm_sender=failing)
    assert out["recorded"] and not out["dm"]["sent"]
    assert "couldn't find" in out["dm"]["detail"]


def test_cli_prints_the_steps_when_the_dm_fails(lab, monkeypatch):
    monkeypatch.setattr(PM, "_default_dm_sender",
                        lambda ws, **kw: (False, "no Slack token for 'mh'"))
    out = CliRunner().invoke(cli, ["project-add-member", "@tyler", "--project", "faraday"])
    assert out.exit_code == 0, out.output
    assert "awaiting a certificate" in out.output
    assert "send them yourself" in out.output
    assert "murmurent enroll --project faraday" in out.output


# ---------------------------------------------------------------------------
# import-card on the member's machine
# ---------------------------------------------------------------------------


def test_import_without_a_pinned_root_names_the_key_and_says_lab(lab, monkeypatch, tmp_path):
    bundle = _outsider_bundle(lab)
    # Tyler's machine: nothing pinned for Mike's lab.
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "tyler_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "tyler_li"))
    with pytest.raises(ISS.IssuanceError) as exc:
        ISS.verify_and_import_project_card(bundle)
    msg = str(exc.value)
    assert "no trust root pinned yet for lab 'mh'" in msg
    assert "centre" not in msg.split("trust realm")[0]
    assert f"--trust-root {lab['trust']}" in msg
    assert "pi_card.payload.subject.pubkey" in msg
    # and with the root given, it imports
    v, _ = ISS.verify_and_import_project_card(bundle, trust_root=lab["trust"])
    assert v.ok


def test_member_card_import_error_has_the_same_shape(lab, monkeypatch, tmp_path):
    priv = Ed25519PrivateKey.generate()
    req = C.make_enrollment_request("@bob", priv=priv, nonce="n2", group="mh")
    bundle = ISS.issue_member_card("@bob", enrollment=req, group="mh")
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "bob_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "bob_li"))
    with pytest.raises(ISS.IssuanceError, match="no trust root pinned yet for lab 'mh'"):
        ISS.verify_and_import_member_card(bundle)


def test_centre_rooted_bundle_keeps_the_centre_wording():
    """A PI card signed by a centre (issuer is not the subject) is a centre
    matter, and the message says so."""
    bundle = {"pi_card": {"payload": {"centre": "western_qa",
                                      "subject": {"fingerprint": "aa", "pubkey": "ed25519:A"},
                                      "issuer": {"fingerprint": "bb"},
                                      "roles": [{"group": "mh"}]}}}
    info = ISS.trust_root_of(bundle)
    assert not info["self_rooted"] and info["root"] == "" and info["lab"] == ""
    assert "centre-pin western_qa" in info["import_command"]


# ---------------------------------------------------------------------------
# enroll --project
# ---------------------------------------------------------------------------


def test_enroll_project_points_at_project_add_member(lab, monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "tyler_home"))
    monkeypatch.setenv("MURMURENT_USER", "tyler")
    K.generate_keypair()
    out_file = tmp_path / "enroll.json"
    out = CliRunner().invoke(cli, ["enroll", "--project", "faraday", "--out", str(out_file)])
    assert out.exit_code == 0, out.output
    assert out_file.is_file()
    assert "murmurent project-add-member @tyler --project faraday --enrollment" in out.output
    assert "--trust-root" in out.output
    assert "issue-project-card" not in out.output
