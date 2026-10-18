"""
Tests for the Slack comms-fabric wiring (Phase B): lab/core channels named
after the group, members-only, with the channel id persisted. All Slack I/O
is injected — no test hits the wire.
"""

from __future__ import annotations

import pytest

from murmurent.core import centre_init as CI
from murmurent.core import centre_provision as CP
from murmurent.core import registrar as R
from murmurent.core import slack_comms as SC


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "lab_info"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab-mgmt"))
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MURMURENT_SLACK_TOKEN", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(R, "REGISTRAR_SENTINEL",
                        fake_home / ".murmurent" / "registrar")
    CI.init_centre(name="Demo", institution="Demo U", founding_mayor="@tbrowne",
                   unique_name="demo", slack_workspace="T0DEMO",
                   write_sentinel=False)
    return tmp_path


# ---- registrar helpers -------------------------------------------------

def test_set_and_read_group_channel_and_email_map(world):
    R.create_lab(name="lab_mh", display_name="MH Lab", pi_handle="@harry",
                 pi_email="harry@demo.edu")
    assert R.set_group_slack_channel("lab_mh", "C0LABMH") is True
    reg = R.read_registry()
    lab = next(l for l in reg.labs if l.name == "lab_mh")
    assert lab.slack_channel_id == "C0LABMH"
    # email map picks up the PI's email
    assert R.group_email_map("lab_mh") == {"harry": "harry@demo.edu"}
    # unknown group → no-op
    assert R.set_group_slack_channel("nope", "C0X") is False


# ---- slack_comms.ensure_group_channel ---------------------------------

def test_ensure_group_channel_noop_without_token(world, monkeypatch):
    monkeypatch.setattr(SC, "token_present", lambda: False)
    assert SC.ensure_group_channel("lab_mh", {"harry": "h@d.edu"}) is None


def test_ensure_group_channel_creates_and_invites(world, monkeypatch):
    monkeypatch.setattr(SC, "token_present", lambda: True)
    from murmurent.core.centre_provision import SlackChannelResult
    seen = {}
    def creator(name, *, private=True):
        seen["name"] = name
        seen["private"] = private
        return SlackChannelResult(ok=True, channel_id="C0NEW",
                                  channel_name=name, detail="created (HTTP 200)")
    def inviter(cid, handles, *, member_email_map=None, member_slack_map=None):
        seen["invite"] = (cid, list(handles), member_email_map)
        return {"channel_id": cid, "invited": handles, "already_in": [],
                "unresolved": [], "error": None}
    out = SC.ensure_group_channel("lab_mh", {"harry": "harry@demo.edu"},
                                  creator=creator, inviter=inviter)
    assert seen["name"] == "lab-mh"          # #lab-<group>, no repeated lab_ (#188)
    assert seen["private"] is True           # private
    assert out["channel_id"] == "C0NEW" and out["created"] is True
    assert out["invited"] == ["harry"]
    assert seen["invite"][0] == "C0NEW"


# ---- provision_lab_onboarding integration -----------------------------

def test_provision_creates_group_channel_and_persists_id(world, monkeypatch):
    R.create_lab(name="lab_mh", display_name="MH Lab", pi_handle="@harry",
                 pi_email="harry@demo.edu")
    created_with = {}
    def fake_slack(name, ws):
        created_with["name"] = name
        created_with["ws"] = ws
        return "C0LABMH"
    invited_with = {}
    def fake_inviter(cid, handles, *, member_email_map=None, member_slack_map=None):
        invited_with["args"] = (cid, list(handles), member_email_map)
        return {"invited": list(handles), "already_in": [], "unresolved": [],
                "error": None}
    probes = CP.provision_lab_onboarding(
        "lab_mh", slack_creator=fake_slack, member_inviter=fake_inviter,
        acl_runner=lambda *a, **k: (0, "", ""),
    )
    # #lab-<group> (#188); the group's own lab_ prefix is not repeated
    assert created_with["name"] == "lab-mh"
    # channel id persisted on the lab entry
    lab = next(l for l in R.read_registry().labs if l.name == "lab_mh")
    assert lab.slack_channel_id == "C0LABMH"
    # the PI (with email) was passed to the inviter
    assert invited_with["args"][0] == "C0LABMH"
    assert invited_with["args"][2] == {"harry": "harry@demo.edu"}
    # a slack probe is present + ok
    slack_probe = next(p for p in probes if p.name == "slack-channel")
    assert slack_probe.status == "ok"


def test_provision_skips_invite_without_token_or_inviter(world, monkeypatch):
    """No injected inviter + no env token → channel made + id stored, but the
    member invite is not attempted (the token-less-suite guarantee)."""
    R.create_lab(name="lab_mh", display_name="MH", pi_handle="@harry",
                 pi_email="harry@demo.edu")
    probes = CP.provision_lab_onboarding(
        "lab_mh", slack_creator=lambda n, w: "C0LABMH",
        acl_runner=lambda *a, **k: (0, "", ""),
    )
    lab = next(l for l in R.read_registry().labs if l.name == "lab_mh")
    assert lab.slack_channel_id == "C0LABMH"           # created + stored
    slack_probe = next(p for p in probes if p.name == "slack-channel")
    assert "0 member(s)" in slack_probe.detail         # invite not attempted


# ---- provision_centre_slack (mayor channel + broadcast seeding) -------

def test_provision_centre_slack_creates_mayor_channel_and_seeds_broadcasts(world):
    probes = CP.provision_centre_slack(
        channel_creator=lambda name, ws: "C0OPS" if name == "murmurent-ops" else None,
        channel_resolver=lambda name: "C0GEN" if name == "general" else None,
    )
    # mayor channel id persisted on the centre
    assert CI.read_centre().mayor_channel_id == "C0OPS"
    # broadcast_channels seeded: admin -> mayor channel, everyone -> #general
    prof = R.read_profile()
    assert prof["broadcast_channels"]["admin"] == "C0OPS"
    assert prof["broadcast_channels"]["everyone"] == "C0GEN"
    names = {p.name for p in probes}
    assert {"mayor-channel", "general-channel"} <= names


def test_provision_centre_slack_surfaces_create_error(world, monkeypatch):
    # Live path (no channel_creator injected) must show the real Slack error,
    # not a bare "could not be created".
    monkeypatch.setattr(CP, "slack_create_channel",
        lambda name, **k: CP.SlackChannelResult(
            ok=False, channel_name=name, error="missing_scope",
            detail="add groups:write and reinstall the app"))
    probes = CP.provision_centre_slack(channel_resolver=lambda n: None)
    mayor = next(p for p in probes if p.name == "mayor-channel")
    assert mayor.status == "warn"
    assert "missing_scope" in mayor.detail and "groups:write" in mayor.detail


def test_provision_centre_slack_reuses_existing_mayor_channel(world, monkeypatch):
    # name_taken → resolve + reuse the existing channel (idempotent re-run).
    monkeypatch.setattr(CP, "slack_create_channel",
        lambda name, **k: CP.SlackChannelResult(ok=False, channel_name=name,
                                                error="name_taken", detail="exists"))
    monkeypatch.setattr("murmurent.dashboard.slack_notify._lookup_channel_id_by_name",
                        lambda n: "C0EXISTING")
    probes = CP.provision_centre_slack(channel_resolver=lambda n: None)
    mayor = next(p for p in probes if p.name == "mayor-channel")
    assert mayor.status == "ok" and "C0EXISTING" in mayor.detail
    assert CI.read_centre().mayor_channel_id == "C0EXISTING"


def test_resolve_slack_token_env_then_file(monkeypatch, tmp_path):
    monkeypatch.delenv("MURMURENT_SLACK_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    cfg = tmp_path / ".config" / "murmurent"
    cfg.mkdir(parents=True)
    (cfg / "slack-token").write_text("xoxb-fromfile\n")
    # The file is the dashboard's token file (one setting for both paths).
    from murmurent.dashboard import slack_notify as _sn
    monkeypatch.setattr(_sn, "_TOKEN_FILE", cfg / "slack-token")

    # env-only (allow_file=False, the automatic-path default): file is ignored
    assert CP.resolve_slack_token() == ""
    # explicit command (allow_file=True): falls back to the file
    assert CP.resolve_slack_token(allow_file=True) == "xoxb-fromfile"
    # env always wins over the file
    monkeypatch.setenv("MURMURENT_SLACK_TOKEN", "xoxb-fromenv")
    assert CP.resolve_slack_token(allow_file=True) == "xoxb-fromenv"


def test_provision_centre_slack_invites_the_mayor(world, monkeypatch):
    # The bot creates the private #murmurent-ops → the human mayor must be invited
    # or they can't see it.
    CI.update_centre({"join_email": "tbrowne@demo.edu"})
    monkeypatch.setenv("MURMURENT_SLACK_TOKEN", "xoxb-x")
    monkeypatch.setattr(CP, "slack_create_channel",
        lambda name, **k: CP.SlackChannelResult(ok=True, channel_id="C0OPS", channel_name=name))
    seen = {}
    def fake_invite(cid, handles, *, member_email_map=None, member_slack_map=None):
        seen.update(cid=cid, handles=handles, map=member_email_map)
        return {"invited": handles, "already_in": [], "unresolved": []}
    monkeypatch.setattr("murmurent.dashboard.slack_notify.invite_members_to_channel", fake_invite)

    probes = CP.provision_centre_slack(channel_resolver=lambda n: "C0GEN")
    inv = next(p for p in probes if p.name == "mayor-invite")
    assert inv.status == "ok" and "tbrowne" in inv.detail
    assert seen["cid"] == "C0OPS"
    assert seen["map"] == {"tbrowne": "tbrowne@demo.edu"}


def test_provision_centre_slack_mayor_email_override(world, monkeypatch):
    # --mayor-email must win over the centre join_email for the invite lookup.
    CI.update_centre({"join_email": "public@demo.edu"})
    monkeypatch.setenv("MURMURENT_SLACK_TOKEN", "xoxb-x")
    monkeypatch.setattr(CP, "slack_create_channel",
        lambda name, **k: CP.SlackChannelResult(ok=True, channel_id="C0OPS", channel_name=name))
    seen = {}
    def fake_invite(cid, handles, *, member_email_map=None, member_slack_map=None):
        seen["map"] = member_email_map
        return {"invited": handles, "already_in": [], "unresolved": []}
    monkeypatch.setattr("murmurent.dashboard.slack_notify.invite_members_to_channel", fake_invite)
    CP.provision_centre_slack(channel_resolver=lambda n: "C0GEN", mayor_email="real@slack.edu")
    assert seen["map"] == {"tbrowne": "real@slack.edu"}     # override beats join_email


def test_provision_centre_slack_warns_when_no_mayor_email(world, monkeypatch):
    monkeypatch.setenv("MURMURENT_SLACK_TOKEN", "xoxb-x")
    monkeypatch.setattr(CP, "slack_create_channel",
        lambda name, **k: CP.SlackChannelResult(ok=True, channel_id="C0OPS", channel_name=name))
    probes = CP.provision_centre_slack(channel_resolver=lambda n: "C0GEN")
    inv = next(p for p in probes if p.name == "mayor-invite")
    assert inv.status == "warn" and "email" in inv.detail.lower()


def test_provision_member_to_group_invites(world, monkeypatch):
    R.create_lab(name="dcis", display_name="dcis", pi_handle="@allie", pi_email="a@x")
    R.set_group_slack_channel("dcis", "C0DCIS")
    monkeypatch.setattr("murmurent.dashboard.slack_notify.invite_members_to_channel",
        lambda cid, handles, *, member_email_map=None, member_slack_map=None:
            {"invited": handles, "already_in": [], "unresolved": []})
    probes = CP.provision_member_to_group("dcis", handle="@bob", email="bob@x", token="xoxb-x")
    assert probes[0].status == "ok" and "C0DCIS" in probes[0].detail


def test_provision_member_defers_with_invite_link_when_not_in_workspace(world, monkeypatch):
    R.create_lab(name="dcis", display_name="dcis", pi_handle="@allie", pi_email="a@x")
    R.set_group_slack_channel("dcis", "C0DCIS")
    CI.update_centre({"slack_invite_url": "https://join.slack/xyz"})
    monkeypatch.setattr("murmurent.dashboard.slack_notify.invite_members_to_channel",
        lambda cid, handles, *, member_email_map=None, member_slack_map=None:
            {"invited": [], "already_in": [],
             "unresolved": [{"handle": handles[0], "reason": "no slack account"}]})
    probes = CP.provision_member_to_group("dcis", handle="@bob", email="bob@x", token="xoxb-x")
    assert probes[0].status == "warn" and "join.slack/xyz" in probes[0].detail


def test_provision_centre_slack_needs_workspace(world):
    CI.update_centre({"slack_workspace": ""})
    probes = CP.provision_centre_slack()
    assert len(probes) == 1 and probes[0].status == "warn"
    assert "slack_workspace" in probes[0].detail


# ---- #188: #lab-<group> naming + sync_group_slack_channel ---------------

def test_channel_name_is_lab_dash_group():
    assert SC.channel_name_for("mh") == "lab-mh"
    assert SC.channel_name_for("biocore") == "lab-biocore"
    assert SC.channel_name_for("lab_mh") == "lab-mh"       # no lab-lab_mh
    assert SC.channel_name_for("MH") == "lab-mh"
    assert len(SC.channel_name_for("x" * 100)) == 80
    assert SC.channel_name_for("") is None


def _ok(name, cid="C0NEW"):
    return CP.SlackChannelResult(ok=True, channel_id=cid, channel_name=name,
                                 detail="created (HTTP 200)")


def test_sync_creates_records_and_invites(world):
    R.create_lab(name="mh", display_name="MH", pi_handle="@harry",
                 pi_email="harry@demo.edu")
    made, invited = [], []
    probe = CP.sync_group_slack_channel(
        "mh", token="xoxb-test",
        creator=lambda n: (made.append(n), _ok(n))[1],
        inviter=lambda cid, hs, member_email_map: (invited.append((cid, hs)),
                                                   {"invited": hs})[1])
    assert made == ["lab-mh"]
    assert invited == [("C0NEW", ["harry"])]
    assert probe.status == "ok" and "created channel C0NEW" in probe.detail
    lab = next(l for l in R.read_registry().labs if l.name == "mh")
    assert lab.slack_channel_id == "C0NEW"


def test_sync_keeps_an_existing_channel(world):
    """A group named under the old scheme keeps its channel: no second one."""
    R.create_lab(name="mh", display_name="MH", pi_handle="@harry",
                 pi_email="harry@demo.edu")
    R.set_group_slack_channel("mh", "C0OLD")
    made = []
    probe = CP.sync_group_slack_channel(
        "mh", token="xoxb-test", creator=lambda n: made.append(n),
        inviter=lambda cid, hs, member_email_map: {"already_in": hs})
    assert made == []
    assert "using channel C0OLD" in probe.detail


def test_sync_reuses_a_taken_name(world, monkeypatch):
    from murmurent.dashboard import slack_notify as _sn
    R.create_lab(name="mh", display_name="MH", pi_handle="@harry")
    monkeypatch.setattr(_sn, "_lookup_channel_id_by_name",
                        lambda name, token=None: "C0TAKEN" if name == "lab-mh" else None)
    taken = CP.SlackChannelResult(ok=False, channel_name="lab-mh",
                                  error="name_taken", detail="exists")
    CP.sync_group_slack_channel("mh", token="xoxb-test", creator=lambda n: taken,
                                inviter=lambda *a, **k: {})
    lab = next(l for l in R.read_registry().labs if l.name == "mh")
    assert lab.slack_channel_id == "C0TAKEN"


def test_sync_without_token_does_nothing(world):
    R.create_lab(name="mh", display_name="MH", pi_handle="@harry")
    probe = CP.sync_group_slack_channel(
        "mh", token="", creator=lambda n: pytest.fail("must not create"))
    assert probe.status == "warn" and "not set up" in probe.detail


def test_remove_member_from_group_channel(world):
    R.create_lab(name="mh", display_name="MH", pi_handle="@harry")
    R.set_group_slack_channel("mh", "C0LAB")
    kicked = []
    probe = CP.remove_member_from_group_channel(
        "mh", handle="@bob", email="bob@demo.edu", token="",
        kicker=lambda cid, em: (kicked.append((cid, em)), (True, "kicked"))[1])
    assert kicked == [("C0LAB", "bob@demo.edu")] and probe.status == "ok"
    no_email = CP.remove_member_from_group_channel(
        "mh", handle="bob", email="", token="xoxb-test")
    assert no_email.status == "warn" and "no email" in no_email.detail
