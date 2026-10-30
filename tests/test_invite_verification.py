"""Issue #246: an invite is reported done only when the member is really in the
channel. Slack answers ``ok`` to ``conversations.invite`` for a single-channel
guest and adds nobody; the reconcile used to count that as an invite."""
from __future__ import annotations

import pytest

from murmurent.dashboard import slack_notify as SN


class _Resp:
    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


@pytest.fixture
def slack(monkeypatch):
    """Fake Slack: a channel with the bot in it, an invite that always says ok,
    and user flags per id. Yields the mutable state."""
    state = {"members": [{"UBOT"}], "flags": {}, "posts": []}

    def members(channel_id, *, token=None):
        # Snapshots in order: before the invite, then after it. The last one
        # repeats once the list is used up.
        snaps = state["members"]
        return set(snaps.pop(0) if len(snaps) > 1 else snaps[0])

    def post(url, *, headers, json, timeout):
        state["posts"].append(json)
        return _Resp({"ok": True})

    def get(url, *, headers, params, timeout):
        assert url == SN._SLACK_API_USER_INFO
        return _Resp({"ok": True, "user": state["flags"].get(params["user"], {})})

    monkeypatch.setattr(SN, "_channel_member_ids", members)
    monkeypatch.setattr("httpx.post", post)
    monkeypatch.setattr("httpx.get", get)
    return state


def test_member_who_arrives_is_invited(slack):
    slack["members"] = [{"UBOT"}, {"UBOT", "U0000AAA1"}]
    out = SN.invite_members_to_channel("C1", ["ann"], member_slack_map={"ann": "U0000AAA1"}, token="x")
    assert out["invited"] == ["ann"]
    assert out["unresolved"] == []
    assert slack["posts"] == [{"channel": "C1", "users": "U0000AAA1"}]


def test_single_channel_guest_is_reported_not_invited(slack):
    slack["members"] = [{"UBOT"}, {"UBOT"}]          # invite "ok", nobody added
    slack["flags"] = {"U0000AAA1": {"is_restricted": True, "is_ultra_restricted": True}}
    out = SN.invite_members_to_channel("C1", ["owl"], member_slack_map={"owl": "U0000AAA1"}, token="x")
    assert out["invited"] == []
    assert out["error"] is None
    assert [u["handle"] for u in out["unresolved"]] == ["owl"]
    assert "single-channel guest" in out["unresolved"][0]["reason"]
    assert "admin" in out["unresolved"][0]["reason"]


def test_full_member_who_does_not_arrive_is_reported_plainly(slack):
    slack["members"] = [{"UBOT"}, {"UBOT"}]
    slack["flags"] = {"U0000AAA1": {}}
    out = SN.invite_members_to_channel("C1", ["bob"], member_slack_map={"bob": "U0000AAA1"}, token="x")
    assert out["invited"] == []
    assert out["unresolved"][0]["reason"].startswith("Slack accepted the invite")


def test_unreadable_channel_after_invite_trusts_slack(slack):
    slack["members"] = [{"UBOT"}, set()]              # re-read fails: empty set
    out = SN.invite_members_to_channel("C1", ["ann"], member_slack_map={"ann": "U0000AAA1"}, token="x")
    assert out["invited"] == ["ann"]


def test_mixed_batch_splits_arrivals_from_guests(slack):
    slack["members"] = [{"UBOT"}, {"UBOT", "U0000AAA1"}]
    slack["flags"] = {"U0000AAA2": {"is_restricted": True, "is_ultra_restricted": True}}
    out = SN.invite_members_to_channel("C1", ["ann", "owl"],
                                       member_slack_map={"ann": "U0000AAA1", "owl": "U0000AAA2"}, token="x")
    assert out["invited"] == ["ann"]
    assert [u["handle"] for u in out["unresolved"]] == ["owl"]


def test_guest_kind_reads_the_flags(monkeypatch):
    def get(url, *, headers, params, timeout):
        return _Resp({"ok": True, "user": {"is_restricted": True}})
    monkeypatch.setattr("httpx.get", get)
    assert SN._user_guest_kind("U0000AAA1", token="x") == "multi-channel guest"

    def get_fail(url, *, headers, params, timeout):
        return _Resp({"ok": False, "error": "missing_scope"})
    monkeypatch.setattr("httpx.get", get_fail)
    assert SN._user_guest_kind("U0000AAA1", token="x") is None
    assert SN._user_guest_kind("U0000AAA1", token=None) is None or SN._token() is not None
