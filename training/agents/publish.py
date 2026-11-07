#!/usr/bin/env python3
"""
Purpose: Copy the agent movies to the website repository: for each agent
         with a movie here (the narrated one when it exists, else the silent
         captioned one), write
         assets/videos/murmurent_agent_<agent>_720p.mp4, a .vtt made from the
         .srt, and a player page murmurent_agent_<agent>.html (same shape as
         murmurent_thesis_package.html). Commits nothing: the website repo may
         hold the owner's unstaged changes, so staging and pushing are done by
         hand, naming only these files.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-07
Input: training/agents/<agent>/{<agent>_narrated.mp4, <agent>.srt, scenes.py};
       training/index.yaml for the durations.
Output: the three files per agent under <site>/assets/videos/, and index.html
        there listing every training video; prints the list.
Usage: python3 training/agents/publish.py [--site ~/repos/hallettmiket.github.io] [agent ...]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lib.agent_movie import parse_index_titles  # noqa: E402

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; padding: 24px 16px; font-family: system-ui, sans-serif; background: Canvas; color: CanvasText; }}
  main {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 16px; }}
  video {{ width: 100%; height: auto; border-radius: 8px; background: #000; }}
  p {{ line-height: 1.5; }}
</style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <video controls preload="metadata">
    <source src="murmurent_agent_{agent}_720p.mp4" type="video/mp4">
    <track kind="captions" src="murmurent_agent_{agent}_720p.vtt" srclang="en" label="English">
  </video>
  <p>{tagline}: one of the commons agents of Murmurent. What it does, what it will not do, one real
  run, and how to use it through Claude Code. {minutes}; captions are in the picture. The agent's own
  definition: <a href="https://github.com/hallettmiket/murmurent/blob/main/agents/{agent}.md">agents/{agent}.md</a>.
  All the training videos: <a href="index.html">mikehallett.science/assets/videos</a>.</p>
</main>
</body>
</html>
"""


INDEX_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Murmurent training videos</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; padding: 24px 16px; font-family: system-ui, sans-serif; background: Canvas; color: CanvasText; }}
  main {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 8px; }}
  h2 {{ font-size: 1.15rem; margin: 28px 0 8px; }}
  p, li {{ line-height: 1.5; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ text-align: left; padding: 6px 10px 6px 0; vertical-align: top; border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, transparent); }}
  th {{ font-weight: 600; }}
</style>
</head>
<body>
<main>
  <h1>Murmurent training videos</h1>
  <p>Short videos for learning <a href="https://github.com/hallettmiket/murmurent">Murmurent</a>. Captions are in the
  picture; every terminal and chat scene is a real run. The written documentation is the reference when the two
  disagree: <a href="https://mikehallett.science/murmurent/">mikehallett.science/murmurent</a>.</p>

  <h2>Start here</h2>
  <table>
    <tr><th>Video</th><th>Length</th><th>What it covers</th></tr>
    <tr><td><a href="murmurent_getting_started.html">Getting started with Murmurent</a></td><td>6:50</td>
        <td>what Murmurent is, installing it, saying who you are, the agents, joining a lab or a centre</td></tr>
    <tr><td><a href="murmurent_thesis_package.html">A thesis an examiner can question</a></td><td>6:20</td>
        <td>paper packages, thesis packages and the docent: a thesis whose every claim carries its evidence</td></tr>
  </table>

  <h2>One short video per agent</h2>
  <p>Each one: what the agent does, what it will not do, one real run, and how to use it through Claude Code.
  In the order a new member meets them.</p>
  <table>
    <tr><th>Agent</th><th>Length</th><th>In one line</th></tr>
{rows}
  </table>
  <p>How these are made and kept current:
  <a href="https://github.com/hallettmiket/murmurent/blob/main/training/README.md">training/README.md</a>.</p>
</main>
</body>
</html>
"""

AGENT_ORDER = ["oracle", "bookworm", "adversary", "artist", "scribe", "teacher", "lab_oracle", "blacksmith",
               "conscience", "lawyer", "millwright", "centre_millwright", "judge", "registrar", "security_guard",
               "docent"]


def write_index(dest: Path, info: dict) -> None:
    rows = []
    for agent in AGENT_ORDER:
        e = info.get(agent)
        page = dest / f"murmurent_agent_{agent}.html"
        if not e or not page.exists():
            continue
        secs = int(e.get("seconds", 0))
        tagline = re.search(r'tagline="([^"]+)"', (HERE / agent / "scenes.py").read_text()).group(1).rstrip(".")
        rows.append(f'    <tr><td><a href="murmurent_agent_{agent}.html">{e.get("title", agent)}</a></td>'
                    f'<td>{secs // 60}:{secs % 60:02d}</td><td>{tagline}</td></tr>')
    (dest / "index.html").write_text(INDEX_PAGE.format(rows="\n".join(rows)))
    print(f"index: {len(rows)} agent videos listed at {dest / 'index.html'}")


def srt_to_vtt(srt: str) -> str:
    out = ["WEBVTT", ""]
    for line in srt.splitlines():
        if "-->" in line:
            line = line.replace(",", ".")
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="~/repos/hallettmiket.github.io")
    ap.add_argument("agents", nargs="*")
    args = ap.parse_args()
    dest = Path(args.site).expanduser() / "assets" / "videos"
    dest.mkdir(parents=True, exist_ok=True)
    info = parse_index_titles()
    agents = args.agents or sorted(p.name for p in HERE.iterdir() if (p / f"{p.name}.mp4").exists())
    for agent in agents:
        folder = HERE / agent
        narrated = (folder / f"{agent}_narrated.mp4").exists()
        mp4 = folder / (f"{agent}_narrated.mp4" if narrated else f"{agent}.mp4")
        srt = folder / f"{agent}.srt"
        if not mp4.exists() or not srt.exists():
            print(f"skip {agent}: no movie or srt", file=sys.stderr)
            continue
        entry = info.get(agent, {})
        secs = int(entry.get("seconds", 0))
        minutes = f"{secs // 60} min {secs % 60} s" if secs else "A few minutes"
        if not narrated:
            minutes += " (captions only for now; the narration is added when the movie is re-voiced)"
        spec_text = (folder / "scenes.py").read_text()
        tagline = re.search(r'tagline="([^"]+)"', spec_text).group(1).rstrip(".")
        shutil.copyfile(mp4, dest / f"murmurent_agent_{agent}_720p.mp4")
        (dest / f"murmurent_agent_{agent}_720p.vtt").write_text(srt_to_vtt(srt.read_text()))
        (dest / f"murmurent_agent_{agent}.html").write_text(PAGE.format(
            title=entry.get("title", agent), agent=agent, tagline=tagline, minutes=minutes))
        print(f"{agent}: {mp4.stat().st_size / 1e6:.1f} MB, {minutes}{'' if narrated else ', SILENT'}")
    write_index(dest, info)


if __name__ == "__main__":
    main()
