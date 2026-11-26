"""The lookout's video reader (scripts/lookout_videos.py): the channel rows are read from the
watch list's video section and nowhere else, and a channel feed is parsed entry by entry so a
title never pairs with another entry's date. No network: the feed is a string here."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lookout_videos.py"


def _mod():
    spec = importlib.util.spec_from_file_location("lookout_videos", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["lookout_videos"] = m
    spec.loader.exec_module(m)
    return m


def test_channels_come_from_the_video_section_only(tmp_path):
    watch = tmp_path / "watch.md"
    watch.write_text(
        "# The watch list\n\n## Anthropic\n\n"
        "| Source | Page |\n|---|---|\n"
        "| decoy | <https://www.youtube.com/feeds/videos.xml?channel_id=UCdecoydecoydecoydecoyAA> |\n\n"
        "## Video: the channels\n\n"
        "| Channel | Address | What it covers | Yield | Read |\n|---|---|---|---|---|\n"
        "| Chase AI | <https://www.youtube.com/feeds/videos.xml?channel_id=UCoy6cTJ7Tg0dqS-DI-_REsA> | x | none yet | 2026-11-26 |\n"
        "| Anthropic | <https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA> | y | none yet | 2026-11-26 |\n\n"
        "## Searches\n\n| Terms | For |\n|---|---|\n| agent memory | the oracle |\n"
    )
    m = _mod()
    assert m.channels(watch) == [
        ("Chase AI", "UCoy6cTJ7Tg0dqS-DI-_REsA"),
        ("Anthropic", "UCrDwWp7EBBv4NwvScIpBDOA"),
    ]


def test_the_real_watch_list_names_channels():
    m = _mod()
    rows = m.channels(ROOT / "docs" / "watch.md")
    names = [n for n, _ in rows]
    assert "Chase AI" in names and "Anthropic" in names
    assert all(len(cid) == 24 for _, cid in rows)


def test_feed_entries_keep_their_own_dates(monkeypatch):
    m = _mod()
    xml = (
        "<feed><title>Channel</title>"
        "<entry><yt:videoId>aaa</yt:videoId><title>Old one</title><published>2024-10-18T00:00:00+00:00</published></entry>"
        "<entry><yt:videoId>bbb</yt:videoId><title>New one</title><published>2026-11-26T09:00:00+00:00</published></entry>"
        "</feed>"
    )
    monkeypatch.setattr(m, "fetch", lambda url: xml)
    assert m.uploads("UCxxxxxxxxxxxxxxxxxxxxxx") == [
        ("2026-11-26", "bbb", "New one"),
        ("2024-10-18", "aaa", "Old one"),
    ]


def test_a_string_that_is_not_a_video_id_is_never_fetched_or_sent(monkeypatch, capsys):
    """Ids come from strangers' feeds and may reach a shell on another machine."""
    m = _mod()
    seen = []
    monkeypatch.setattr(m, "fetch_here", lambda vids: seen.extend(vids) or {v: (False, "x") for v in vids})
    monkeypatch.setattr(m, "fetch_via", lambda host, vids: seen.extend(vids) or {v: (False, "x") for v in vids})
    m.main(["transcript", "abc;rm -rf ~", "$(id)xxxxxx", "reRtVTuXbNc", "--via", "server"])
    assert seen == ["reRtVTuXbNc", "reRtVTuXbNc"]
    out = capsys.readouterr().out
    assert out.count("REFUSED") == 2


def test_a_refused_video_is_fetched_through_the_other_machine(monkeypatch, tmp_path, capsys):
    m = _mod()
    monkeypatch.setattr(m, "fetch_here", lambda vids: {v: (False, "IpBlocked") for v in vids})
    monkeypatch.setattr(m, "fetch_via", lambda host, vids: {v: (True, "what was said") for v in vids})
    m.main(["transcript", "reRtVTuXbNc", "--via", "server", "--out", str(tmp_path)])
    assert (tmp_path / "reRtVTuXbNc.txt").read_text().endswith("what was said\n")
    assert "from server" in capsys.readouterr().out


def test_without_a_via_host_a_refusal_is_unresolved(monkeypatch, capsys):
    m = _mod()
    monkeypatch.delenv("MURMURENT_LOOKOUT_VIA", raising=False)
    monkeypatch.setattr(m, "fetch_here", lambda vids: {v: (False, "IpBlocked") for v in vids})
    m.main(["transcript", "reRtVTuXbNc"])
    assert "UNRESOLVED  reRtVTuXbNc" in capsys.readouterr().out
