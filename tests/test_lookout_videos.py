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
