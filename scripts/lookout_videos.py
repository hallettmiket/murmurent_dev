#!/usr/bin/env python3
"""
Purpose: The lookout's video reader. Lists what the YouTube channels on the watch list
         (docs/watch.md, section "Video: the channels") uploaded since a date, from each
         channel's own feed, and prints the transcript of the videos it is asked for, so the
         lookout reads what was said rather than what the title promises. The YouTube results
         page loads empty for a plain client; the channel feeds and the caption tracks do not.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-26
Input: docs/watch.md (the channel ids), the network. Transcripts need the youtube-transcript-api
       package (pip install youtube-transcript-api); without it the listing still works and the
       transcript step says what to install.
Output: `list`: one line per upload since the date: date, video id, channel, title.
        `transcript <video id>...`: the transcript text of each video, or UNRESOLVED with why.
Usage: python3 scripts/lookout_videos.py list [--since YYYY-MM-DD] [--watch docs/watch.md]
       python3 scripts/lookout_videos.py transcript <video id> [<video id>...]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
UA = "Mozilla/5.0 (compatible; murmurent lookout)"


def channels(watch: Path) -> list[tuple[str, str]]:
    """(channel name, channel id) for every row of the video channels table."""
    text = watch.read_text()
    start = text.find("## Video: the channels")
    if start < 0:
        sys.exit(f"{watch}: no 'Video: the channels' section")
    end = text.find("\n## ", start + 1)
    block = text[start:end if end > 0 else None]
    out = []
    for line in block.splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|[^|]*channel_id=([A-Za-z0-9_-]{24})", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def uploads(channel_id: str) -> list[tuple[str, str, str]]:
    """(published date, video id, title) from the channel's feed, newest first."""
    xml = fetch(FEED.format(channel_id))
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
    out = []
    for e in entries:
        vid = re.search(r"<yt:videoId>([^<]+)", e)
        title = re.search(r"<title>([^<]+)", e)
        pub = re.search(r"<published>([^<]+)", e)
        if vid and title and pub:
            out.append((pub.group(1)[:10], vid.group(1), title.group(1)))
    return sorted(out, reverse=True)


def cmd_list(args: argparse.Namespace) -> int:
    since = args.since or (date.today() - timedelta(days=4)).isoformat()
    rows = channels(Path(args.watch))
    if not rows:
        sys.exit(f"{args.watch}: no channel rows with a channel_id")
    for name, cid in rows:
        try:
            ups = uploads(cid)
        except Exception as e:  # noqa: BLE001 - one channel down must not stop the rest
            print(f"UNRESOLVED  {name}: feed not read ({type(e).__name__})")
            continue
        recent = [u for u in ups if u[0] >= since]
        if not recent:
            print(f"nothing since {since}  {name}")
        for pub, vid, title in recent:
            print(f"{pub}  {vid}  {name}  {title}")
    return 0


def cmd_transcript(args: argparse.Namespace) -> int:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except ImportError:
        sys.exit("UNRESOLVED: the youtube-transcript-api package is not installed "
                 "(pip install youtube-transcript-api); the listing still works without it")
    api = YouTubeTranscriptApi()
    for vid in args.video_id:
        print(f"==== {vid}  https://www.youtube.com/watch?v={vid}")
        try:
            text = " ".join(s.text for s in api.fetch(vid))
            print(re.sub(r"\s+", " ", text).strip())
        except Exception as e:  # noqa: BLE001
            print(f"UNRESOLVED: no transcript ({type(e).__name__}: {str(e)[:120]})")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="uploads since a date, from the channel feeds")
    p.add_argument("--since", help="YYYY-MM-DD; default four days ago")
    p.add_argument("--watch", default="docs/watch.md")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("transcript", help="the transcript of each video")
    p.add_argument("video_id", nargs="+")
    p.set_defaults(fn=cmd_transcript)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
