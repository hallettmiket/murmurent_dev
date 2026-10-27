"""
Purpose: an expired identity card is explained at sign-in, not hidden behind a
         silent return to the sign-in page; a card about to expire is warned of.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-17
Input: a throwaway centre key and cards issued with chosen dates, under
       tmp_path. No network.
Output: pass or fail.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from murmurent.core import centre_root as CR
from murmurent.core import idcert as C
from murmurent.core import identity_card as IC
from murmurent.core import issuance as ISS

UTC = dt.timezone.utc
ISSUED = dt.datetime(2026, 7, 10, 12, 0, tzinfo=UTC)      # 90 days later: 2026-10-08


@pytest.fixture
def centre(monkeypatch, tmp_path):
    """A centre root key, pinned on this machine, and a PI key."""
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "li"))
    monkeypatch.setattr(ISS, "_lab_name", lambda: "mh")
    CR.generate_root_key()
    C.pin_root("qa", CR.root_public())
    IC.import_card({"version": IC.CARD_VERSION, "netname": "pi", "centre": "qa",
                    "roles": [{"kind": "lab_pi", "group": "mh", "pi": "@pi"}],
                    "issued_by": "@m", "issued_at": ISSUED.isoformat()})
    ISS.cards_dir().mkdir(parents=True, exist_ok=True)
    return {"root": CR.load_root_private(), "pi": Ed25519PrivateKey.generate()}


def pi_card(centre, issued=ISSUED):
    return C.issue_pi_card(handle="@pi", pi_pubkey=centre["pi"].public_key(), centre="qa",
                           root_priv=centre["root"], issued_at=issued)


def hold_pi_card(centre, issued=ISSUED):
    (ISS.cards_dir() / "qa_pi.json").write_text(C.dumps(pi_card(centre, issued)))


def hold_member_bundle(centre, member_issued):
    member = C.issue_member_card(handle="@student", member_pubkey=Ed25519PrivateKey.generate()
                                 .public_key(), group="mh", centre="qa", pi_priv=centre["pi"],
                                 pi_handle="@pi", issued_at=member_issued)
    (ISS.cards_dir() / "qa_member.json").write_text(json.dumps(
        {"member_card": member, "pi_card": pi_card(centre)}))


def test_an_expired_pi_card_says_when_and_how_to_renew(centre):
    hold_pi_card(centre)
    health = ISS.local_card_health(now=dt.datetime(2026, 10, 17, tzinfo=UTC))
    assert health.status == "reject" and health.kind == "pi"
    assert health.expires_on == "2026-10-08"
    assert "expired on 2026-10-08" in health.message
    assert "murmurent pi-init mh" in health.message


def test_a_card_close_to_expiry_is_warned_of_but_still_lets_you_in(centre):
    hold_pi_card(centre)
    health = ISS.local_card_health(now=dt.datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    assert health.status == "ok" and health.message == ""
    assert "expires on 2026-10-08 (in 5 days)" in health.warning


def test_a_card_far_from_expiry_says_nothing(centre):
    hold_pi_card(centre)
    health = ISS.local_card_health(now=dt.datetime(2026, 8, 1, tzinfo=UTC))
    assert health.status == "ok" and not health.warning and not health.message


def test_a_member_is_told_when_the_pi_card_inside_theirs_has_expired(centre):
    hold_member_bundle(centre, member_issued=dt.datetime(2026, 9, 1, tzinfo=UTC))
    health = ISS.local_card_health(now=dt.datetime(2026, 10, 10, tzinfo=UTC))
    assert health.status == "reject" and health.kind == "member"
    assert health.limited_by == "your PI's"
    assert health.message.startswith("Your PI's card, which yours depends on, expired on 2026-10-08")
    assert "murmurent pi-init mh" in health.message and "lab records" in health.message


def test_no_card_means_nothing_to_say(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "empty"))
    health = ISS.local_card_health()
    assert health.status == "no_card" and not health.message and not health.warning


# ---------------------------------------------------------------------------
# The dashboard: sign-in refuses with the reason; the page's data request does too
# ---------------------------------------------------------------------------

EXPIRED = ISS.CardHealth(status="reject", reason="expired", kind="pi", expires_on="2026-10-08",
                         limited_by="yours", days_left=-9,
                         message="Your murmurent identity card expired on 2026-10-08, so the "
                                 "dashboard cannot let you in. Renew it on this computer with:  "
                                 "murmurent pi-init mh")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_USER", "pi")
    from murmurent.dashboard.server import create_app
    return TestClient(create_app())


def test_sign_in_refuses_an_expired_card_with_the_reason(client, monkeypatch):
    monkeypatch.setattr(ISS, "local_card_health", lambda **kw: EXPIRED)
    r = client.post("/api/login/select", json={"handle": "pi", "role": "member",
                                               "remember_user": False})
    assert r.status_code == 403
    assert r.json()["detail"] == EXPIRED.message


def test_the_sign_in_page_hears_about_the_card_before_anyone_clicks(client, monkeypatch):
    monkeypatch.setattr(ISS, "local_card_health", lambda **kw: EXPIRED)
    notice = client.get("/api/login/resolve").json()["card_notice"]
    assert notice == {"kind": "error", "text": EXPIRED.message}

    soon = ISS.CardHealth(status="ok", warning="Your murmurent identity card expires on "
                          "2026-10-20 (in 3 days). Renew it on this computer with:  "
                          "murmurent pi-init mh")
    monkeypatch.setattr(ISS, "local_card_health", lambda **kw: soon)
    notice = client.get("/api/login/resolve").json()["card_notice"]
    assert notice["kind"] == "warning" and "in 3 days" in notice["text"]


def test_the_dashboard_data_request_gives_the_same_reason(client, monkeypatch):
    monkeypatch.setattr(ISS, "local_card_health", lambda **kw: EXPIRED)
    r = client.get("/api/dashboard?user=pi")
    assert r.status_code == 403 and r.json()["detail"] == EXPIRED.message


def test_a_broken_card_check_never_locks_anyone_out(client, monkeypatch):
    def boom(**kw):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(ISS, "local_card_health", boom)
    assert client.get("/api/login/resolve").json()["card_notice"] is None


# ---- a PI renewal reaches members through the lab records (#233) ----------

@pytest.fixture
def member_machine(centre, monkeypatch, tmp_path):
    """The same centre, but this machine belongs to @student, a member of mh."""
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(tmp_path / "repos"))
    IC.import_card({"version": IC.CARD_VERSION, "netname": "student", "centre": "qa",
                    "roles": [{"kind": "member", "group": "mh", "pi": "@pi",
                               "group_kind": "lab"}],
                    "issued_by": "@pi", "issued_at": ISSUED.isoformat()})
    return tmp_path / "repos" / "murmurent_lab_mgmt_mh"


def test_a_member_is_refused_when_the_pi_copy_runs_out_and_nothing_was_renewed(member_machine, centre):
    hold_member_bundle(centre, member_issued=ISSUED + dt.timedelta(days=80))
    health = ISS.local_card_health(now=dt.datetime(2026, 10, 17, tzinfo=UTC))
    assert health.status == "reject" and health.kind == "member"
    assert health.limited_by == "your PI's" and health.expires_on == "2026-10-08"
    assert "murmurent pi-init mh" in health.message
    assert "lab records" in health.message
    assert "murmurent enroll" not in health.message


def test_a_renewed_pi_card_in_the_lab_records_lets_the_member_in(member_machine, centre):
    hold_member_bundle(centre, member_issued=ISSUED + dt.timedelta(days=80))
    renewed = pi_card(centre, issued=ISSUED + dt.timedelta(days=89))
    note = ISS.publish_pi_card(renewed, member_machine)
    assert (member_machine / "pi_card.json").is_file()
    assert "pi_card.json" in note
    health = ISS.local_card_health(now=dt.datetime(2026, 10, 17, tzinfo=UTC))
    assert health.status == "ok", health.reason
    # The warning, if any, is now about the member's own card, not the PI's.
    assert health.limited_by == "yours"
    assert health.expires_on == (ISSUED + dt.timedelta(days=170)).date().isoformat()


def test_pi_init_publishes_the_card_into_the_lab_records(monkeypatch, tmp_path):
    from murmurent.core import idkeys as K
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "li"))
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(tmp_path / "repos"))
    monkeypatch.delenv("MURMURENT_LAB_MGMT_REPO", raising=False)
    K.generate_keypair()
    out = ISS.self_issue_pi_card("@pi", "mh")
    published = tmp_path / "repos" / "murmurent_lab_mgmt_mh" / "pi_card.json"
    assert published.is_file()
    assert json.loads(published.read_text())["payload"]["card_id"] == out["pi_card"]["payload"]["card_id"]
