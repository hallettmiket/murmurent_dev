"""
Purpose: A short movie that is not about one agent (issue #290): working
         through Claude Code, a skill, the mayor's tools. The same renderer as
         the agent movies, with a scene list the movie script composes from a
         few scene kinds: a title, quote cards checked against a file, a typed
         terminal, a real chat exchange, bullets, and a how-to. Each movie
         lives under training/skills/<name>/ as scenes.py (the spec),
         transcript.md (real exchanges) and make.py.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-07
Input: a Movie spec; transcript.md beside it; the files its quotes come from.
Output: <folder>/<key>.mp4 and .srt, then <key>_narrated.mp4 through
        narrate.py; the movie's entry in training/index.yaml under videos:
        (title, date, version, seconds, chapters, and the hash of each file it
        quotes, so the hook can tell when one changed).
Usage: python3 training/skills/<name>/make.py [--stills DIR] [--no-voice]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from PIL import ImageDraw

from . import scene as scene_mod
from .agent_movie import (INDEX, MAX_SECONDS, ROOT, _norm, chat_duration, load_transcript, murmurent_version,
                          s_chat, _quote_cards)
from .draw import (AMBER, DIM, F_BIG, F_BODY, F_LABEL, F_MONO, F_MONO_S, F_SMALL, F_SUB, F_TINY, MUTED, PANEL,
                   RED, TEAL, TERM_BG, TEXT, CHARS_PER_SECOND, P, Term, appear, badge, eback, heading, icon,
                   mono_block, rrect, text_c, wrap)
from .scene import EM_DASH, Scene, mmss, render


@dataclass
class Quote:
    text: str
    cue: str | None = None


@dataclass
class Part:
    """One scene. kind: title | cards | terminal | chat | bullets | howto."""
    kind: str
    narration: list[str]
    chapter: str | None = None
    heading: str = ""
    quotes: list[Quote] = field(default_factory=list)   # cards: from `source`
    source: str = ""                                      # cards: repo-relative file the quotes come from
    colour: tuple = TEAL
    mark: str = "tick"
    transcript: str = ""                                  # terminal: lines; `$ ` lines are typed
    title: str = ""                                       # terminal panel title
    notes: list[tuple[str, str]] = field(default_factory=list)   # terminal/bullets: (text, cue)
    key: str = ""                                         # chat: section of transcript.md
    chips: list[tuple[str, bool]] = field(default_factory=list)
    who: str = ""
    agent: str = ""                                       # chat: which agent answers
    glyph: str = ""
    agent_title: str = ""                                 # chat heading: "The teacher" or "/murmurent-push"
    prompt: str = ""                                      # howto
    cards: list[tuple[str, str]] = field(default_factory=list)   # howto: (title, body)
    docs: list[str] = field(default_factory=list)
    tail: float = 1.2
    note_title: str = ""                                  # obsidian: the note's name in the sidebar
    note_lines: list[str] = field(default_factory=list)   # obsidian: the note's text, as the file holds it
    sidebar: list[str] = field(default_factory=list)      # obsidian: other files in the folder


@dataclass
class Movie:
    key: str                  # file stem and index key, e.g. claude_code
    title: str
    tagline: str
    glyph: str
    colour: tuple
    summary: str              # one line for the index and the page
    parts: list[Part]
    index: bool = True        # False for a clip that is appended to another video, not listed


class _Shim:
    """What s_chat needs of an AgentSpec."""
    def __init__(self, agent, colour, title):
        self.agent, self.colour, self.title = agent, colour, title


# --------------------------------------------------------------------------- #
# Scenes
# --------------------------------------------------------------------------- #


def s_title(img, t, sc, m: Movie, version: str):
    def head(d):
        y = 150
        for line in wrap(m.title, F_BIG, 700):
            d.text((70, y), line, font=F_BIG, fill=TEXT)
            y += 70
        for line in wrap(m.tagline, F_SUB, 680):
            d.text((72, y + 10), line, font=F_SUB, fill=m.colour)
            y += 38
        d.text((72, y + 44), f"Murmurent {version}", font=F_SMALL, fill=MUTED)
    appear(img, t, 0.3, head, 0.9, 24)
    p = P(t, 0.6, 0.7)
    if p > 0:
        badge(img, m.glyph, m.colour, 1000, 330, 260, eback(p), min(1.0, p * 3))


def s_cards(img, t, sc, part: Part, source_name: str):
    heading(img, t, part.heading)
    shim = _Shim(source_name, part.colour, part.heading)
    _quote_cards(img, t, sc, shim, part.quotes, part.narration, part.colour, part.mark)


def s_terminal(img, t, sc, part: Part, term: Term):
    heading(img, t, part.heading, 28)
    mono_block(img, term.lines(t), 40, 96, 800, 500, f=F_MONO_S, title=part.title or "Terminal")
    y = 110
    for text, cue in part.notes:
        t0 = sc.when(cue) if cue else sc.lead
        lines = wrap(text, F_SMALL, 360)
        h = 22 + len(lines) * 26
        def f(d, y=y, lines=lines, h=h):
            rrect(d, (870, y, 1240, y + h), PANEL, part.colour, 12, 2)
            yy = y + 11
            for ln in lines:
                d.text((886, yy), ln, font=F_SMALL, fill=TEXT)
                yy += 26
        appear(img, t, t0, f, 0.5, 12)
        y += h + 12


def s_bullets(img, t, sc, part: Part):
    heading(img, t, part.heading)
    y = 120
    for i, (text, cue) in enumerate(part.notes):
        t0 = sc.when(cue) if cue else sc.lead + i * 2.0
        lines = wrap(text, F_BODY, 1060)
        h = 22 + len(lines) * (F_BODY.size + 7)
        def f(d, y=y, lines=lines, h=h):
            rrect(d, (70, y, 1210, y + h), PANEL, None, 12, 0)
            d.rectangle([70, y + 4, 76, y + h - 4], fill=part.colour)
            yy = y + 11
            for ln in lines:
                d.text((120, yy), ln, font=F_BODY, fill=TEXT)
                yy += F_BODY.size + 7
        appear(img, t, t0, f, 0.5, 12)
        if t > t0:
            icon(img, part.mark, 98, y + 24, 26, part.colour, part.colour, eback(P(t, t0 + 0.2, 0.4)))
        y += h + 12


def s_obsidian(img, t, sc, part: Part):
    """A note as Obsidian shows it: a file list on the left, the note on the right, its
    frontmatter as a properties block. The text is the real file; only the frame is drawn."""
    heading(img, t, part.heading, 28)
    d = ImageDraw.Draw(img)
    rrect(d, (40, 96, 1240, 600), (30, 30, 34), (70, 70, 78), 10, 2)
    d.rectangle([40, 96, 300, 600], fill=(38, 38, 43))
    d.text((60, 110), "lab-notebook", font=F_TINY, fill=(160, 160, 170))
    y = 138
    for name in part.sidebar:
        sel = name == part.note_title
        if sel:
            d.rounded_rectangle([50, y - 4, 290, y + 22], radius=6, fill=(60, 60, 72))
        d.text((64, y), name, font=F_SMALL, fill=(230, 230, 235) if sel else (170, 170, 180))
        y += 30
    d.text((330, 110), part.note_title, font=F_LABEL, fill=(235, 235, 240))
    n = int(len(part.note_lines) * P(t, sc.lead, max((sc.seconds - sc.lead - sc.tail) * 0.45, 1.0)))
    y = 146
    in_fm = False
    for i, line in enumerate(part.note_lines[:max(n, 1)]):
        if y > 580:
            break
        if line.strip() == "---":
            in_fm = (i == 0)
            d.rounded_rectangle([322, y - 2, 1230, y + 2], radius=2, fill=(60, 60, 72))
            y += 8
            continue
        if in_fm:
            k, _, v = line.partition(":")
            d.text((332, y), k.strip(), font=F_MONO_S, fill=(150, 150, 165))
            d.text((520, y), v.strip(), font=F_MONO_S, fill=(210, 210, 220))
            y += 22
            continue
        if line.startswith("## "):
            d.text((330, y + 4), line[3:], font=F_LABEL, fill=(240, 200, 120))
            y += 34
        elif line.startswith("!["):
            d.rounded_rectangle([330, y, 530, y + 70], radius=6, fill=(55, 60, 80), outline=(90, 100, 130))
            d.text((344, y + 24), line[2:line.index("]")] if "]" in line else "image", font=F_TINY, fill=(200, 205, 220))
            y += 80
        else:
            for ln in wrap(line, F_SMALL, 880):
                col = (120, 170, 230) if ("[[" in ln or "http" in ln or "](" in ln) else (220, 220, 228)
                d.text((330, y), ln, font=F_SMALL, fill=col)
                y += 26
    if n < len(part.note_lines):
        d.text((330, 575), "...", font=F_SMALL, fill=(150, 150, 165))


def s_howto(img, t, sc, part: Part, m: Movie, version: str):
    heading(img, t, part.heading or "How to use it, through Claude Code")
    d = ImageDraw.Draw(img)
    t_p = sc.lead + 0.3
    def panel(d):
        rrect(d, (70, 120, 1210, 232), TERM_BG, (58, 70, 104), 12, 2)
        d.text((88, 128), "Claude Code", font=F_TINY, fill=MUTED)
    appear(img, t, t_p - 0.2, panel, 0.5, 10)
    prompt = part.prompt
    n = int(len(prompt) * P(t, t_p, len(prompt) / CHARS_PER_SECOND))
    if t >= t_p:
        for i, l in enumerate(wrap("> " + prompt[:n] + ("▌" if n < len(prompt) else ""), F_BODY, 1100)[:2]):
            d.text((88, 158 + i * 32), l, font=F_BODY, fill=AMBER)
    t_done = t_p + len(prompt) / CHARS_PER_SECOND + 0.3
    a = P(t, t_done, 0.6)
    if a > 0:
        badge(img, m.glyph, m.colour, 160, 320, 120, eback(a))
    n_cards = max(len(part.cards), 1)
    w = int((970 - (n_cards - 1) * 20) / n_cards)
    for i, (title, body) in enumerate(part.cards):
        t0 = t_done + 0.6 + i * 1.4
        x = 240 + i * (w + 20)
        def f(d, x=x, title=title, body=body, i=i):
            col = m.colour if i == 1 else TEAL
            rrect(d, (x, 340, x + w, 540), PANEL, col, 14, 3)
            d.text((x + 16, 352), title, font=F_LABEL, fill=col)
            yy = 384
            for ln in wrap(body, F_TINY, w - 32):
                d.text((x + 16, yy), ln, font=F_TINY, fill=TEXT)
                yy += F_TINY.size + 5
        appear(img, t, t0, f, 0.5, 12)
    def foot(d):
        d.text((70, 565), "   ".join(part.docs), font=F_MONO_S, fill=AMBER)
        d.text((70, 592), f"Checked against Murmurent {version}, {date.today().isoformat()}.", font=F_TINY, fill=MUTED)
    appear(img, t, sc.seconds - sc.tail - 2.5, foot, 0.6, 8)


# --------------------------------------------------------------------------- #
# Checks, build, index
# --------------------------------------------------------------------------- #


def check_sources(m: Movie) -> dict[str, str]:
    """Every quote is in its file; returns {repo-relative path: sha256}."""
    out: dict[str, str] = {}
    for part in m.parts:
        if part.kind != "cards":
            continue
        if not part.source:
            raise ValueError(f"{m.key}: a cards part needs a source file")
        path = ROOT / part.source
        raw = path.read_bytes()
        text = _norm(raw.decode())
        for q in part.quotes:
            if EM_DASH in q.text:
                raise ValueError(f"{m.key}: a quote carries an em dash; pick a fragment without one: {q.text!r}")
            if _norm(q.text) not in text:
                raise ValueError(f"{m.key}: not in {part.source} any more: {q.text!r}")
        out[part.source] = hashlib.sha256(raw).hexdigest()
    for part in m.parts:
        for text in part.narration:
            if EM_DASH in text:
                raise ValueError(f"{m.key}: em dash in the narration: {text!r}")
    return out


def build_scenes(m: Movie, folder: Path, version: str) -> list[Scene]:
    exchanges = load_transcript(folder) if (folder / "transcript.md").exists() else {}
    scenes: list[Scene] = []
    for i, part in enumerate(m.parts):
        name = f"{part.kind}{i}"
        if part.kind == "title":
            scenes.append(Scene(name, part.narration, lambda img, t, s: s_title(img, t, s, m, version), part.chapter or "Welcome"))
        elif part.kind == "cards":
            src = part.source
            scenes.append(Scene(name, part.narration, lambda img, t, s, part=part, src=src: s_cards(img, t, s, part, src),
                                part.chapter, tail=part.tail))
        elif part.kind == "terminal":
            term = Term(part.transcript)
            scenes.append(Scene(name, part.narration, lambda img, t, s, part=part, term=term: s_terminal(img, t, s, part, term),
                                part.chapter, min_anim=term.dur + 1.0, tail=part.tail))
        elif part.kind == "chat":
            who, q, reply = exchanges[part.key]
            who = part.who or who
            shim = _Shim(part.agent, part.colour, part.agent_title or f"The {part.agent}")
            scenes.append(Scene(name, part.narration,
                                lambda img, t, s, shim=shim, who=who, q=q, reply=reply, part=part:
                                s_chat(img, t, s, shim, who, q, reply, part.chips),
                                part.chapter, min_anim=chat_duration(q, part.chips, reply), tail=part.tail))
        elif part.kind == "obsidian":
            scenes.append(Scene(name, part.narration, lambda img, t, s, part=part: s_obsidian(img, t, s, part),
                                part.chapter, tail=part.tail))
        elif part.kind == "bullets":
            scenes.append(Scene(name, part.narration, lambda img, t, s, part=part: s_bullets(img, t, s, part),
                                part.chapter, tail=part.tail))
        elif part.kind == "howto":
            scenes.append(Scene(name, part.narration, lambda img, t, s, part=part: s_howto(img, t, s, part, m, version),
                                part.chapter or "How to use it", tail=2.5))
        else:
            raise ValueError(f"unknown part kind {part.kind!r}")
    return scenes


def update_index(m: Movie, folder: Path, version: str, sources: dict[str, str], seconds: float,
                 chapters: list[tuple[float, str]]) -> None:
    """The movie's entry under videos: in training/index.yaml, replaced in place."""
    rel = folder.relative_to(ROOT)
    entry = [f"- key: {m.key}",
             f"  title: {json.dumps(m.title)}",
             f"  tagline: {json.dumps(m.tagline.rstrip('.'))}",
             f"  date: {date.today().isoformat()}",
             f"  version: {version}",
             f"  seconds: {int(round(seconds))}",
             f"  summary: {json.dumps(m.summary)}",
             f"  page: https://mikehallett.science/assets/videos/murmurent_{m.key}.html",
             f"  file: https://mikehallett.science/assets/videos/murmurent_{m.key}_720p.mp4",
             f"  transcript: {rel}/{m.key}.srt",
             f"  make: python3 {rel}/make.py",
             "  sources:"]
    for path, sha in sources.items():
        entry.append(f"    {path}: {sha}")
    entry.append("  chapters:")
    for t, name in chapters:
        entry.append(f"    - [\"{mmss(t)}\", \"{name}\"]")
    block = "\n".join(entry) + "\n"
    text = INDEX.read_text()
    pat = re.compile(rf"^- key: {re.escape(m.key)}\n(?:  .*\n|    .*\n)*", re.M)
    if pat.search(text):
        text = pat.sub(block, text, count=1)
    else:
        # append to the videos: list, which ends where the next top-level key starts
        i = text.index("\nnews:")
        text = text[:i].rstrip("\n") + "\n" + block + text[i:]
    INDEX.write_text(text)


def main(m: Movie, folder: Path, argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=f"Render the movie {m.title!r}.")
    ap.add_argument("--stills", default=None)
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--voice", default="Matilda")
    args = ap.parse_args(argv)
    version = murmurent_version()
    sources = check_sources(m)
    from .narrate import clip_durations
    texts = [s for p in m.parts for s in p.narration]
    scene_mod.DURATIONS.update(clip_durations(folder, texts, args.voice))
    scenes = build_scenes(m, folder, version)
    total = sum(s.seconds for s in scenes)
    if total > MAX_SECONDS:
        sys.exit(f"{m.key}: {total:.0f} s is over the {MAX_SECONDS} s limit; shorten the narration.")
    seconds, chapters = render(scenes, folder, m.key, stills=Path(args.stills) if args.stills else None)
    if args.stills:
        return
    if m.index:
        update_index(m, folder, version, sources, seconds, chapters)
    if not args.no_voice:
        from .narrate import voice
        voice(folder, m.key, args.voice)
