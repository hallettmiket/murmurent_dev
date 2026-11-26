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
       python3 scripts/lookout_videos.py transcript <video id> [<video id>...] [--out DIR]
       A computer YouTube refuses can fetch through another: --via <ssh host>, or set
       MURMURENT_LOOKOUT_VIA; the script is sent over ssh and the host needs only uv.
       Transcripts are refused from cloud machines; /murmurent-lookout-videos runs this on a
       member's own computer instead (docs/lookout.md, "Video from your own computer").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
UA = "Mozilla/5.0 (compatible; murmurent lookout)"
# A YouTube video id. Ids come from strangers' feeds and may reach a shell on another machine,
# so anything else is refused before it is fetched or sent.
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


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


def fetch_here(vids: list[str]) -> dict[str, tuple[bool, str]]:
    """{video id: (ok, transcript text or the reason it failed)}, fetched from this computer."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except ImportError:
        why = ("the youtube-transcript-api package is not installed "
               "(pip install youtube-transcript-api); the listing still works without it")
        return {v: (False, why) for v in vids}
    api = YouTubeTranscriptApi()
    got = {}
    for vid in vids:
        try:
            text = " ".join(s.text for s in api.fetch(vid))
            got[vid] = (True, re.sub(r"\s+", " ", text).strip())
        except Exception as e:  # noqa: BLE001 - one video down must not stop the rest
            got[vid] = (False, f"{type(e).__name__}: {str(e).strip()[:120]}")
    return got


def fetch_via(host: str, vids: list[str]) -> dict[str, tuple[bool, str]]:
    """The same fetch, run on another machine over ssh. This script is sent on stdin and the
    machine needs only uv, so nothing is installed there and nothing of murmurent is read."""
    remote = ("PATH=$HOME/.local/bin:$PATH uv run -q --no-project --with youtube-transcript-api "
              "python3 - transcript --jsonl " + " ".join(shlex.quote(v) for v in vids))
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, remote],
                           input=Path(__file__).read_text(), capture_output=True, text=True,
                           timeout=60 + 20 * len(vids))
    except Exception as e:  # noqa: BLE001
        return {v: (False, f"ssh {host} failed: {type(e).__name__}") for v in vids}
    got = {}
    for line in r.stdout.splitlines():
        if line.startswith("{"):
            d = json.loads(line)
            got[d["id"]] = (d["ok"], d["text"])
    why = (r.stderr.strip().splitlines() or ["no answer"])[-1][:120]
    return {v: got.get(v, (False, f"ssh {host}: {why}")) for v in vids}


def cmd_transcript(args: argparse.Namespace) -> int:
    bad = [v for v in args.video_id if not VIDEO_ID.match(v)]
    for v in bad:
        print(f"REFUSED  {v!r}: not a YouTube video id (11 letters, digits, - or _)")
    vids = [v for v in dict.fromkeys(args.video_id) if VIDEO_ID.match(v)]
    if not vids:
        return 1 if bad else 0
    got = fetch_here(vids)
    if args.jsonl:  # the form fetch_via reads back from the other machine
        for v in vids:
            print(json.dumps({"id": v, "ok": got[v][0], "text": got[v][1]}))
        return 0
    where = {v: "this computer" for v in vids if got[v][0]}
    refused = [v for v in vids if not got[v][0]]
    if refused and args.via:
        for v, res in fetch_via(args.via, refused).items():
            if res[0]:
                got[v], where[v] = res, args.via
            else:
                got[v] = (False, f"here: {got[v][1][:60]}; {args.via}: {res[1]}")
    out = Path(args.out) if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    for v in vids:
        ok, text = got[v]
        url = f"https://www.youtube.com/watch?v={v}"
        if not ok:
            print(f"UNRESOLVED  {v}: no transcript ({text})")
        elif out:
            (out / f"{v}.txt").write_text(f"{url}\n\n{text}\n")
            print(f"read  {v}  {len(text.split())} words, from {where[v]}  {out / (v + '.txt')}")
        else:
            print(f"==== {v}  {url}  (from {where[v]})\n{text}\n")
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
    p.add_argument("--out", help="write each transcript to <dir>/<video id>.txt and print one line per video")
    p.add_argument("--via", default=os.environ.get("MURMURENT_LOOKOUT_VIA"),
                   help="ssh host to fetch through when this computer is refused "
                        "(default: $MURMURENT_LOOKOUT_VIA)")
    p.add_argument("--jsonl", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_transcript)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
