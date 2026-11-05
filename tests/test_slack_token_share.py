"""
Purpose: tests for sharing the lab's Slack bot token with certified members
         through the lab records (``core/slack_token_share``): the PI seals it
         to each member's attested card key, a member's machine opens it with
         its own key, and ``murmurent project note`` finds it.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-05
Input: temporary folders and freshly generated keys. No network, no git remote.
Output: pass or fail.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from murmurent.core import cert_projects as cp
from murmurent.core import group_reconcile as gr
from murmurent.core import idkeys as k
from murmurent.core import registrar as R
from murmurent.core import slack_routing as sr
from murmurent.core import slack_token_share as sts


def _pub(priv: Ed25519PrivateKey) -> str:
    return k.encode_public(priv.public_key())


# ---- the box itself --------------------------------------------------------

def test_seal_opens_for_every_recipient_and_nobody_else():
    a, b, c = (Ed25519PrivateKey.generate() for _ in range(3))
    box = sts.seal("xoxb-secret", {"alice": _pub(a), "bob": _pub(b)}, group="mh",
                   sealed_by="@pi")
    assert sts.open_box(box, a) == "xoxb-secret"
    assert sts.open_box(box, b) == "xoxb-secret"
    with pytest.raises(sts.SealError, match="not among the recipients"):
        sts.open_box(box, c)
    assert {s["handle"] for s in box["recipients"]} == {"alice", "bob"}
    assert box["sealed_by"] == "pi" and box["group"] == "mh"


def test_box_survives_json_and_refuses_tampering():
    a = Ed25519PrivateKey.generate()
    box = json.loads(json.dumps(sts.seal("xoxb-1", {"a": _pub(a)})))
    assert sts.open_box(box, a) == "xoxb-1"
    bad = dict(box)
    bad["ciphertext"] = box["ciphertext"][:-4] + ("AAAA" if box["ciphertext"][-4:] != "AAAA" else "BBBB")
    with pytest.raises(sts.SealError):
        sts.open_box(bad, a)


def test_seal_refuses_empty_token_and_no_recipients():
    a = Ed25519PrivateKey.generate()
    with pytest.raises(sts.SealError, match="empty"):
        sts.seal("   ", {"a": _pub(a)})
    with pytest.raises(sts.SealError, match="no recipients"):
        sts.seal("xoxb-1", {})


def test_x25519_twins_agree():
    """The private-side and public-side conversions must land on the same
    X25519 key, or no slot would ever open."""
    for _ in range(8):
        priv = Ed25519PrivateKey.generate()
        via_priv = sts._x25519_private_from_ed25519(priv).public_key().public_bytes_raw()
        via_pub = sts._x25519_public_from_ed25519(priv.public_key()).public_bytes_raw()
        assert via_priv == via_pub


# ---- a small lab: PI machine and member machine ----------------------------

@pytest.fixture
def lab(monkeypatch, tmp_path):
    """One records repository, one registry, two machines (PI + member),
    each with its own ``MURMURENT_HOME`` and key."""
    repos = tmp_path / "repos"
    records = repos / "murmurent_lab_mgmt_mh"
    (records / "members").mkdir(parents=True)
    homes = {"pi": tmp_path / "home_pi", "member": tmp_path / "home_member"}
    keys = {}
    for who, home in homes.items():
        home.mkdir()
        monkeypatch.setenv("MURMURENT_HOME", str(home))
        k.generate_keypair()
        keys[who] = k.load_private()
    # the roster: the PI, a member with an attested key, one without
    def roster(handle, pub=""):
        meta = {"handle": f"@{handle}", "full_name": handle, "role": "staff",
                "status": "active", "email": f"{handle}@x.org"}
        if pub:
            meta["pubkey"] = pub
        (records / "members" / f"{handle}.md").write_text(
            "---\n" + yaml.safe_dump(meta) + "---\n")
    roster("pi", _pub(keys["pi"]))
    roster("tyler", _pub(keys["member"]))
    roster("nokey")
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(records))
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.delenv("MURMURENT_GROUP_SLACK_TOKEN", raising=False)
    # the per-machine token file lives under a fake ~/.config per machine
    token_files: dict[str, Path] = {}

    def use(who: str):
        monkeypatch.setenv("MURMURENT_HOME", str(homes[who]))
        monkeypatch.setenv("MURMURENT_USER", who if who == "pi" else "tyler")
        R.write_registry(R.Registry(labs=[R.LabEntry(name="mh", pi="@pi",
                                                    lab_mgmt_path=str(records))]))
        monkeypatch.setattr(gr, "_group_slack_token_path",
                            lambda group, _w=who: homes[_w] / "config" / group / "slack-token")
        token_files[who] = homes[who] / "config" / "mh" / "slack-token"
        card = {"version": 1, "netname": who, "centre": "c",
                "roles": [{"kind": "lab_pi", "group": "mh", "pi": "@pi"} if who == "pi"
                          else {"kind": "member", "group": "mh", "pi": "@pi"}]}
        (homes[who] / "identity.yaml").write_text(yaml.safe_dump(card))
        return token_files[who]

    return {"records": records, "use": use, "keys": keys, "token_files": token_files}


def test_pi_shares_and_member_unlocks(lab):
    pi_token = lab["use"]("pi")
    gr.write_group_slack_token("mh", "xoxb-lab")
    assert pi_token.read_text().strip() == "xoxb-lab"
    rep = sts.share_group_token("mh", push=False)
    assert rep.ok, rep.error
    assert rep.sealed_for == ["pi", "tyler"]
    assert rep.without_key == ["nokey"]
    assert rep.path == lab["records"] / "security" / "slack_bot_token.sealed.json"
    assert rep.path.is_file()

    member_token = lab["use"]("member")
    assert not member_token.exists()
    rep2 = sts.unlock_group_token("mh")
    assert rep2.ok, rep2.error
    assert rep2.token == "xoxb-lab"
    assert member_token.read_text().strip() == "xoxb-lab"
    assert (member_token.stat().st_mode & 0o777) == 0o600


def test_share_without_a_token_says_to_set_it_up(lab):
    lab["use"]("pi")
    rep = sts.share_group_token("mh", push=False)
    assert not rep.ok and "group-slack-setup mh" in rep.error


def test_unlock_explains_each_missing_piece(lab, monkeypatch):
    lab["use"]("member")
    # no box yet: the PI has to share
    rep = sts.unlock_group_token("mh")
    assert not rep.ok and "group-slack-share mh" in rep.fix
    # a box the member's key cannot open: pull, or the PI shares again
    stranger = Ed25519PrivateKey.generate()
    box = sts.seal("xoxb-lab", {"someone": _pub(stranger)}, group="mh")
    p = lab["records"] / sts.BOX_RELPATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(box))
    rep = sts.unlock_group_token("mh")
    assert not rep.ok and "not among the recipients" in rep.error
    assert "group-slack-share mh" in rep.fix
    # no records clone at all: the clone hint
    monkeypatch.setattr(sts, "records_repo", lambda g, env=None: Path("/nowhere/at/all"))
    rep = sts.unlock_group_token("mh")
    assert not rep.ok and "not on this machine" in rep.error and rep.fix


def test_resolver_falls_back_to_the_shared_box_and_caches_it(lab):
    lab["use"]("pi")
    gr.write_group_slack_token("mh", "xoxb-lab")
    assert sts.share_group_token("mh", push=False).ok
    member_token = lab["use"]("member")
    assert gr.resolve_group_slack_token("mh") == "xoxb-lab"
    assert member_token.read_text().strip() == "xoxb-lab"
    assert gr.resolve_group_slack_token("mh", allow_shared=False) == "xoxb-lab"


def test_project_note_posts_from_a_member_machine(lab, monkeypatch):
    lab["use"]("pi")
    gr.write_group_slack_token("mh", "xoxb-lab")
    assert sts.share_group_token("mh", push=False).ok
    lab["use"]("member")
    repo = Path(lab["records"]).parent / "faraday"
    repo.mkdir()
    (repo / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    cp.upsert("faraday", lab="mh", slack_channel_id="CFARADAY",
              repos=[cp.RepoRef(name="faraday", path=str(repo))])
    seen = {}

    def poster(channel, text, token=None):
        seen.update(channel=channel, text=text, token=token)
        return True
    ok, route, detail = sr.post_note("pushed", start=repo, poster=poster)
    assert ok, detail
    assert seen == {"channel": "CFARADAY", "text": "pushed", "token": "xoxb-lab"}


def test_project_note_names_the_member_command_when_nothing_is_shared(lab):
    lab["use"]("member")
    repo = Path(lab["records"]).parent / "faraday"
    repo.mkdir()
    (repo / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\n")
    cp.upsert("faraday", lab="mh", slack_channel_id="CFARADAY",
              repos=[cp.RepoRef(name="faraday", path=str(repo))])
    ok, _route, detail = sr.post_note("pushed", start=repo, poster=lambda *a, **k: True)
    assert not ok
    assert "no Slack bot token on this machine for project 'faraday'" in detail
    assert "run `murmurent group-slack-unlock mh` here once" in detail


def test_missing_token_hint_depends_on_who_owns_the_machine(lab):
    lab["use"]("pi")
    assert "group-slack-setup mh" in sts.missing_token_hint("mh")
    lab["use"]("member")
    assert "group-slack-unlock mh" in sts.missing_token_hint("mh")


# ---- the two commands --------------------------------------------------------

def test_cli_share_then_unlock(lab):
    from murmurent.commands.centre_cmd import group_slack_share, group_slack_unlock
    lab["use"]("pi")
    gr.write_group_slack_token("mh", "xoxb-lab")
    res = CliRunner().invoke(group_slack_share, ["mh", "--no-push"])
    assert res.exit_code == 0, res.output
    assert "@pi, @tyler" in res.output and "@nokey" in res.output
    member_token = lab["use"]("member")
    res = CliRunner().invoke(group_slack_unlock, ["mh", "--check"])
    assert res.exit_code == 0, res.output
    assert "can open" in res.output and not member_token.exists()
    res = CliRunner().invoke(group_slack_unlock, ["mh"])
    assert res.exit_code == 0, res.output
    assert member_token.read_text().strip() == "xoxb-lab"


def test_cli_unlock_fails_with_the_next_step(lab):
    from murmurent.commands.centre_cmd import group_slack_unlock
    lab["use"]("member")
    res = CliRunner().invoke(group_slack_unlock, ["mh"])
    assert res.exit_code == 1
    assert "Next: ask the PI to run `murmurent group-slack-share mh`" in res.output
