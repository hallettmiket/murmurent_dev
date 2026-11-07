"""
Purpose: The standard short movie for one commons agent (issue #288): what it
         does, what it will not do, one real example end to end, and how to
         use it through Claude Code. Each movie is a scene file
         (training/agents/<agent>/scenes.py) holding the narration, the quotes
         and the example, plus transcript.md with the agent's real replies.
         Quotes are checked against agents/<agent>.md at render time, so a
         change to the agent is visibly a change to the movie; the renderer
         refuses a quote that is no longer in the file.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-07
Input: an AgentSpec (see scenes.py of any agent), transcript.md beside it,
       agents/<agent>.md at the repository root.
Output: <folder>/<agent>.mp4 and .srt (silent, captions burned in), then
        <folder>/<agent>_narrated.mp4 through narrate.py; the movie's entry in
        training/index.yaml (version, date, agent file hash, chapters).
Usage: python3 training/agents/<agent>/make.py [--stills DIR] [--no-voice]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from PIL import ImageDraw

from .draw import (AMBER, BG, CHARS_PER_SECOND, DIM, F_BIG, F_BODY, F_H, F_LABEL, F_MONO_S, F_SMALL, F_SUB,
                   F_TINY, LAV, MUTED, PANEL, PANEL2, RED, TEAL, TERM_BG, TEXT, W, P, appear, eback,
                   badge, font, glow, heading, icon, mono_block, paste_c, rrect, text_c, tw, wrap)
from . import scene as scene_mod
from .scene import EM_DASH, Scene, mmss, render

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
INDEX = ROOT / "training" / "index.yaml"
MAX_SECONDS = 180

# Each agent's glyph, as the seminar slides mark them (blacksmith ⚒, bookworm 📚, artist 🎨,
# adversary ⚔), extended to the rest of the commons. The member is a scientist.
GLYPHS = {"oracle": "🔮", "lab_oracle": "📜", "bookworm": "📚", "blacksmith": "⚒️", "adversary": "⚔️",
          "artist": "🎨", "teacher": "🎓", "conscience": "🧭", "scribe": "✒️", "docent": "🗺️",
          "lawyer": "⚖️", "millwright": "🔧", "centre_millwright": "🏗️", "judge": "🧮",
          "registrar": "🗂️", "security_guard": "🛡️"}
MEMBER_GLYPH = "🧑‍🔬"


def glyph_of(agent: str) -> str:
    return GLYPHS.get(agent, "🤖")
MIN_SECONDS = 90


def murmurent_version() -> str:
    text = (ROOT / "src" / "murmurent" / "__init__.py").read_text()
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else "unknown"


@dataclass
class Quote:
    """A phrase taken verbatim from agents/<agent>.md, and the narration words it appears on."""
    text: str
    cue: str | None = None


@dataclass
class Exchange:
    """One real exchange from transcript.md: its key there, the narration over it, the chips
    (what the agent did while working: (label, done-with-a-tick))."""
    key: str
    narration: list[str]
    chips: list[tuple[str, bool]] = field(default_factory=list)
    who: str = "Member"


@dataclass
class AgentSpec:
    agent: str                       # file name in agents/, e.g. "oracle"
    title: str                       # "The oracle"
    tagline: str                     # one line under the title
    colour: tuple                    # the agent's colour in the palette
    icon: str                        # an icon name from draw.ICONS
    intro: list[str]                 # narration over the title
    does: list[Quote]
    does_narration: list[str]
    refuses: list[Quote]
    refuses_narration: list[str]
    examples: list[Exchange]
    prompt: str                      # what a member types to Claude Code
    give: str                        # what to give it
    verdicts: str                    # its verdict vocabulary, e.g. "Found / Not found / Unsure"
    howto_narration: list[str]
    kind: str = "bot"                # sprite kind for the agent
    docs: list[str] = field(default_factory=list)   # extra files to name at the end


# --------------------------------------------------------------------------- #
# Checking the quotes against the agent's own file
# --------------------------------------------------------------------------- #


def _norm(s: str) -> str:
    s = s.replace("**", "").replace("`", "").replace("*", "")
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)     # markdown links keep their text
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def check_quotes(spec: AgentSpec) -> str:
    """Every quote must appear verbatim in agents/<agent>.md. Returns the file's sha256."""
    path = AGENTS / f"{spec.agent}.md"
    raw = path.read_bytes()
    text = _norm(raw.decode())
    for q in spec.does + spec.refuses:
        if EM_DASH in q.text:
            raise ValueError(f"{spec.agent}: a quote carries an em dash; pick a fragment without one: {q.text!r}")
        if _norm(q.text) not in text:
            raise ValueError(f"{spec.agent}: not in agents/{spec.agent}.md any more: {q.text!r}")
    return hashlib.sha256(raw).hexdigest()


def load_transcript(folder: Path) -> dict[str, tuple[str, str, list[str]]]:
    """Sections `## <key>`: first line `<who>: <question>`, then the reply lines."""
    text = (folder / "transcript.md").read_text()
    out: dict[str, tuple[str, str, list[str]]] = {}
    for m in re.finditer(r"^## (\S+)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        body = m.group(2).strip("\n").split("\n")
        who, _, question = body[0].partition(": ")
        reply = body[1:]
        while reply and not reply[0].strip():
            reply.pop(0)
        while reply and not reply[-1].strip():
            reply.pop()
        out[m.group(1)] = (who, question, reply)
    return out


# --------------------------------------------------------------------------- #
# The five scenes
# --------------------------------------------------------------------------- #


def s_title(img, t, sc, spec: AgentSpec, version: str):
    col = spec.colour
    def head(d):
        d.text((70, 170), spec.title, font=F_BIG, fill=TEXT)
        y = 250
        for line in wrap(spec.tagline, F_SUB, 640):
            d.text((72, y), line, font=F_SUB, fill=col)
            y += 38
        d.text((72, y + 24), "One of the commons agents of Murmurent", font=F_SMALL, fill=MUTED)
        d.text((72, y + 54), f"Murmurent {version}", font=F_SMALL, fill=MUTED)
    appear(img, t, 0.3, head, 0.9, 24)
    cx, cy = 980, 330
    p = P(t, 0.6, 0.7)
    if p > 0:
        glow(img, cx, cy, 90, col, 0.3 * p)
        badge(img, glyph_of(spec.agent), col, cx, cy + 10, 260, eback(p), min(1.0, p * 3))


def _quote_cards(img, t, sc, spec, quotes, narration, colour, mark):
    d = ImageDraw.Draw(img)
    f = F_BODY
    x, w = 70, 1140
    y = 118
    n = max(len(quotes), 1)
    span = max(sc.seconds - sc.lead - sc.tail - 1.0, 1.0)
    for i, q in enumerate(quotes):
        t0 = sc.when(q.cue) if q.cue else sc.lead + i * span / n
        lines = wrap(q.text, f, w - 100)
        h = 22 + len(lines) * (f.size + 7) + F_MONO_S.size + 10
        def card(d, y=y, lines=lines, h=h):
            rrect(d, (x, y, x + w, y + h), PANEL, None, 12, 0)
            d.rectangle([x, y + 4, x + 6, y + h - 4], fill=colour)
            yy = y + 12
            for ln in lines:
                d.text((x + 66, yy), ln, font=f, fill=TEXT)
                yy += f.size + 7
            d.text((x + w - 16 - tw(f"agents/{spec.agent}.md", F_MONO_S), y + h - 10 - F_MONO_S.size),
                   f"agents/{spec.agent}.md", font=F_MONO_S, fill=DIM)
        appear(img, t, t0, card, 0.5, 14)
        if t > t0:
            icon(img, mark, x + 36, y + 24, 30, colour, colour, eback(P(t, t0 + 0.2, 0.4)))
        y += h + 12


def s_does(img, t, sc, spec):
    heading(img, t, "What it does")
    _quote_cards(img, t, sc, spec, spec.does, spec.does_narration, TEAL, "tick")


def s_refuses(img, t, sc, spec):
    heading(img, t, "What it will not do")
    _quote_cards(img, t, sc, spec, spec.refuses, spec.refuses_narration, RED, "cross")


def _who(img, t, t0, cx, cy, colour, glyph, label):
    p = P(t, t0, 0.5)
    if p <= 0:
        return
    badge(img, glyph, colour, cx, cy, 110, eback(p), min(1.0, p * 3))
    appear(img, t, t0 + 0.25, lambda d: text_c(d, cx, cy + 64, label, F_LABEL, colour), 0.4, 8)


def chat_duration(question: str, chips, reply) -> float:
    return 0.8 + len(question) / CHARS_PER_SECOND + 0.5 + len(chips) * 0.55 + 0.7 + len(reply) * 0.28 + 1.5


def s_chat(img, t, sc, spec: AgentSpec, who: str, question: str, reply: list[str], chips):
    col = spec.colour
    heading(img, t, f"In Claude Code, with the {spec.title.split(' ', 1)[-1]}", 28)
    _who(img, t, 0.3, 100, 200, AMBER, MEMBER_GLYPH, who)
    _who(img, t, 0.5, 100, 420, col, glyph_of(spec.agent), spec.agent)
    q0 = 0.8
    q_dur = len(question) / CHARS_PER_SECOND
    n = int(len(question) * P(t, q0, q_dur))
    d = ImageDraw.Draw(img)
    ql = wrap(question[:n] + ("|" if n < len(question) else ""), F_SMALL, 980)
    qh = 40 + 26 * min(len(wrap(question, F_SMALL, 980)), 3)
    rrect(d, (200, 92, 1225, 92 + qh), PANEL, AMBER, 16, 3)
    d.text((218, 100), who, font=F_TINY, fill=AMBER)
    for i, l in enumerate(ql[:3]):
        d.text((218, 122 + i * 26), l, font=F_SMALL, fill=TEXT)
    t_c = q0 + q_dur + 0.5
    cy = 92 + qh + 14
    cw = 1025 / max(len(chips), 1)
    for i, (txt, ok) in enumerate(chips):
        tt = t_c + i * 0.55
        if t < tt:
            continue
        x = 200 + i * cw
        done = t > tt + 0.5
        c = (TEAL if ok else MUTED) if done else col
        def f(d, x=x, txt=txt, c=c):
            rrect(d, (x, cy, x + cw - 10, cy + 36), BG, c, 18, 2)
            d.text((x + 34, cy + 8), txt, font=F_TINY, fill=TEXT)
        appear(img, t, tt, f, 0.3, 6)
        if done:
            icon(img, "tick" if ok else "cross", x + 18, cy + 18, 18, TEAL if ok else DIM, TEAL, eback(P(t, tt + 0.5, 0.3)))
        else:
            ang = (t - tt) * 10
            d.arc([x + 8, cy + 8, x + 28, cy + 28], ang * 57, ang * 57 + 250, fill=col, width=3)
    t_r = t_c + len(chips) * 0.55 + 0.7
    k = int(max(t - t_r, 0) / 0.28)
    items = []
    first_blank = next((i for i, l in enumerate(reply) if not l.strip()), len(reply))
    for i, l in enumerate(reply[:k]):
        items.append((l, col if i < first_blank else TEXT))
    top = cy + (50 if chips else 0)
    mono_block(img, items, 200, top, 1025, 600 - top, f=font(17, mono=True), title=spec.agent)
    if 0 < t - t_r < 0.6:
        glow(img, 190, 470, 14, col, 0.6)


def s_howto(img, t, sc, spec: AgentSpec, version: str):
    col = spec.colour
    heading(img, t, "How to use it, through Claude Code")
    d = ImageDraw.Draw(img)
    t_p = sc.when("type") if "type" in " ".join(spec.howto_narration) else sc.lead
    def panel(d):
        rrect(d, (70, 120, 1210, 232), TERM_BG, (58, 70, 104), 12, 2)
        d.text((88, 128), "Claude Code", font=F_TINY, fill=MUTED)
    appear(img, t, t_p - 0.2, panel, 0.5, 10)
    prompt = spec.prompt
    n = int(len(prompt) * P(t, t_p, len(prompt) / CHARS_PER_SECOND))
    if t >= t_p:
        lines = wrap("> " + prompt[:n] + ("▌" if n < len(prompt) else ""), F_BODY, 1100)
        for i, l in enumerate(lines[:2]):
            d.text((88, 158 + i * 32), l, font=F_BODY, fill=AMBER)
    t_done = t_p + len(prompt) / CHARS_PER_SECOND + 0.3
    # Claude Code hands it to the agent
    a = P(t, t_done, 0.6)
    if a > 0:
        badge(img, glyph_of(spec.agent), col, 160, 320, 120, eback(a))
        appear(img, t, t_done + 0.3, lambda d: text_c(d, 160, 392, spec.agent, F_LABEL, col), 0.4, 6)
        appear(img, t, t_done + 0.3, lambda d: d.text((240, 300), "Claude Code reads agents/" + spec.agent + ".md and hands it the task.",
                                                      font=F_SMALL, fill=MUTED), 0.5, 6)
    cards = [("Give it", spec.give, "give it"), ("The first line is the verdict", spec.verdicts, "verdict"),
             ("Then the detail", "Locations, numbers and what it could not do; read it before you act.", "detail")]
    narr = " ".join(spec.howto_narration)
    for i, (title, body, cue) in enumerate(cards):
        t0 = sc.when(cue) if cue in narr else t_done + 1.0 + i * 1.2
        x = 240 + i * 330
        def f(d, x=x, title=title, body=body, i=i):
            rrect(d, (x, 340, x + 310, 540), PANEL, col if i == 1 else TEAL, 14, 3)
            d.text((x + 16, 352), title, font=F_LABEL, fill=col if i == 1 else TEAL)
            yy = 384
            for ln in wrap(body, F_TINY, 278):
                d.text((x + 16, yy), ln, font=F_TINY, fill=TEXT)
                yy += F_TINY.size + 5
        appear(img, t, t0, f, 0.5, 12)
    t_e = sc.seconds - sc.tail - 2.5
    def foot(d):
        names = [f"agents/{spec.agent}.md"] + spec.docs
        d.text((70, 565), "   ".join(names), font=F_MONO_S, fill=AMBER)
        d.text((70, 592), f"Checked against Murmurent {version}, {date.today().isoformat()}.", font=F_TINY, fill=MUTED)
    appear(img, t, t_e, foot, 0.6, 8)


# --------------------------------------------------------------------------- #
# Building and rendering
# --------------------------------------------------------------------------- #


def build_scenes(spec: AgentSpec, folder: Path, version: str) -> list[Scene]:
    exchanges = load_transcript(folder)
    sc: list[Scene] = []
    sc.append(Scene("title", spec.intro, lambda img, t, s: s_title(img, t, s, spec, version), "Welcome"))
    sc.append(Scene("does", spec.does_narration, lambda img, t, s: s_does(img, t, s, spec), "What it does", tail=1.6))
    sc.append(Scene("refuses", spec.refuses_narration, lambda img, t, s: s_refuses(img, t, s, spec),
                    "What it will not do", tail=1.6))
    for i, ex in enumerate(spec.examples):
        who, q, reply = exchanges[ex.key]
        who = ex.who or who
        sc.append(Scene(f"example{ex.key}", ex.narration,
                        lambda img, t, s, who=who, q=q, reply=reply, ex=ex: s_chat(img, t, s, spec, who, q, reply, ex.chips),
                        "A real example" if i == 0 else None, min_anim=chat_duration(q, ex.chips, reply), tail=1.2))
    sc.append(Scene("howto", spec.howto_narration, lambda img, t, s: s_howto(img, t, s, spec, version),
                    "How to use it", tail=2.5))
    return sc


def update_index(spec: AgentSpec, folder: Path, version: str, sha: str, seconds: float,
                 chapters: list[tuple[float, str]]) -> None:
    """One entry per movie in training/index.yaml, written by hand so there is no yaml dependency
    at render time (the hook reads it with the murmurent package's yaml)."""
    entry = [f"- agent: {spec.agent}",
             f"  title: {spec.title}",
             f"  version: {version}",
             f"  date: {date.today().isoformat()}",
             f"  agent_sha256: {sha}",
             f"  file: training/agents/{spec.agent}/{spec.agent}_narrated.mp4",
             f"  make: python3 training/agents/{spec.agent}/make.py",
             f"  seconds: {int(round(seconds))}",
             "  chapters:"]
    for t, name in chapters:
        entry.append(f"    - [\"{mmss(t)}\", \"{name}\"]")
    block = "\n".join(entry) + "\n"
    head = ("# One entry per script-rendered training movie: which agent, which version and\n"
            "# date it was checked against, the hash of the agent file at that moment, and\n"
            "# its chapters. Written by training/lib/agent_movie.py on every render; read by\n"
            "# the agent_movie hook, which prompts to re-render when agents/<x>.md changes.\n"
            "movies:\n")
    text = INDEX.read_text() if INDEX.exists() else head
    if not text.startswith("#"):
        text = head + text
    pat = re.compile(rf"^- agent: {re.escape(spec.agent)}\n(?:  .*\n|    .*\n)*", re.M)
    if pat.search(text):
        text = pat.sub(block, text, count=1)
    else:
        text = text.rstrip("\n") + "\n" + block
    INDEX.write_text(text)


def main(spec: AgentSpec, folder: Path, argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=f"Render the {spec.title} movie.")
    ap.add_argument("--stills", default=None, help="save a PNG every five seconds here instead of encoding")
    ap.add_argument("--no-voice", action="store_true", help="render the silent movie only")
    ap.add_argument("--voice", default="Matilda")
    args = ap.parse_args(argv)
    version = murmurent_version()
    sha = check_quotes(spec)
    from .narrate import clip_durations
    texts = spec.intro + spec.does_narration + spec.refuses_narration + spec.howto_narration
    for ex in spec.examples:
        texts += ex.narration
    scene_mod.DURATIONS.update(clip_durations(folder, texts, args.voice))
    if scene_mod.DURATIONS:
        print(f"timed {len(scene_mod.DURATIONS)} of {len(texts)} sentences from their voice clips")
    scenes = build_scenes(spec, folder, version)
    total = sum(s.seconds for s in scenes)
    if total > MAX_SECONDS:
        sys.exit(f"{spec.agent}: {total:.0f} s is over the {MAX_SECONDS} s limit; shorten the narration.")
    if total < MIN_SECONDS:
        print(f"note: {spec.agent} runs {total:.0f} s, under the usual {MIN_SECONDS} s", file=sys.stderr)
    seconds, chapters = render(scenes, folder, spec.agent, stills=Path(args.stills) if args.stills else None)
    if args.stills:
        return
    update_index(spec, folder, version, sha, seconds, chapters)
    if not args.no_voice:
        from .narrate import voice
        voice(folder, spec.agent, args.voice)


def parse_index_titles() -> dict[str, dict[str, str]]:
    """The entries of training/index.yaml by agent (the same small parser the hook uses)."""
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from murmurent.hooks.agent_movie import parse_index
    return parse_index(INDEX.read_text()) if INDEX.exists() else {}
