"""The conscience's cold open: it reviews the three cold opens that came before it. The lawyer's
advertisement, the clerk's window and the guard's countdown each get a sticky note with a located
finding and its source, and the footnotes pile up at the bottom of the frame. The humour is at
the thoroughness, never at anyone: the conscience has no persona and speaks for no one. Each
thumbnail is the other movie's own opening, drawn by its own file at a late moment."""
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, F_BODY, F_LABEL, F_SMALL, F_TINY, MUTED, PANEL, SAND, TEAL, TEXT, P, appear, background,
                      eout, rrect, text_c, tw, wrap)
from lib.scene import Scene

NARRATION = [
    "I reviewed the three cold opens before mine. I have notes.",
    "The lawyer: who counts as a loved one? The clerk: a queue assumes you can stand in it. The counter "
    "has no chair.",
    "The guard: twenty seconds to comply. Not everyone reads at that speed. Three flags, each located, "
    "each with its source. No lecture.",
    "I never speak for anyone. I point to who does. Now, your draft.",
]

# (agent, label, the cue its note appears on, the note, the footnote)
REVIEWS = [
    ("lawyer", "The lawyer", "loved one",
     "\"a loved one\": who counts as one? Family status.",
     "[1] Western University, Inclusive Language Guide (2025), Marital and Family Status."),
    ("clerk", "The clerk", "stand in it",
     "A queue you must stand in. The counter has no chair.",
     "[2] Accessibility for Ontarians with Disabilities Act, 2005; O. Reg. 191/11, Design of Public Spaces."),
    ("security_guard", "The guard", "twenty seconds",
     "20 seconds to comply: not everyone reads at that speed.",
     "[3] O. Reg. 191/11, Information and Communication Standard: accessible formats, on request."),
]

_THUMBS: dict[str, Image.Image] = {}
AGENTS = Path(__file__).resolve().parents[1]


def _thumb(agent: str) -> Image.Image:
    """The other movie's opening, drawn by its own cold_open.py near its end, shrunk to a card."""
    if agent not in _THUMBS:
        spec = importlib.util.spec_from_file_location(f"cold_open_{agent}", AGENTS / agent / "cold_open.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        ex = mod.COLD_OPEN
        sc = Scene(ex.name, ex.narration, ex.draw)
        img = background()
        ex.draw(img, sc.seconds - 1.6, sc)
        _THUMBS[agent] = img.resize((340, 191), Image.LANCZOS)
    return _THUMBS[agent]


def _sticky(img, t, t0, cx, cy, text, angle):
    p = P(t, t0, 0.4)
    if p <= 0:
        return
    f = F_SMALL
    lines = wrap(text, f, 250)
    w, h = 290, 26 + len(lines) * (f.size + 6)
    layer = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle((12, 14, w + 8, h + 12), fill=(0, 0, 0, 70))
    d.rectangle((8, 8, w + 4, h + 4), fill=(250, 220, 110, 255))
    y = 20
    for ln in lines:
        d.text((22, y), ln, font=f, fill=(50, 40, 20))
        y += f.size + 6
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    layer.putalpha(layer.getchannel("A").point(lambda v: int(v * eout(p))))
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2 - 14 * (1 - eout(p)))), layer)


def s_review(img, t, sc):
    d = ImageDraw.Draw(img)
    d.text((64, 34), "Reviewed before release", font=F_LABEL, fill=SAND)
    for i, (agent, label, cue, note, foot) in enumerate(REVIEWS):
        x = 70 + i * 400
        p = P(t, 0.3 + i * 0.25, 0.5)
        if p > 0:
            thumb = _thumb(agent)
            rrect(d, (x - 4, 86, x + 344, 281), PANEL, None, 8, 0)
            tmp = thumb.copy()
            tmp.putalpha(int(255 * eout(p)))
            img.paste(tmp, (x, 90), tmp)
            d = ImageDraw.Draw(img)
            text_c(d, x + 170, 292, label, F_LABEL, MUTED)
        t0 = sc.when(cue)
        _sticky(img, t, t0, x + 170, 215, note, (-5, 4, -3)[i])
        d = ImageDraw.Draw(img)
        # The footnotes pile up at the bottom.
        appear(img, t, t0 + 0.3, lambda d, i=i, foot=foot: d.text((70, 470 + i * 26), foot, font=F_TINY, fill=MUTED), 0.4, 8)
        d = ImageDraw.Draw(img)

    def tally(d):
        rrect(d, (70, 348, 1210, 400), PANEL, TEAL, 10, 3)
        text_c(d, 640, 362, "3 flags  ·  3 sources  ·  0 lectures  ·  0 communities spoken for", F_BODY, TEAL)
    appear(img, t, sc.when("Three flags"), tally, 0.5, 10)

    def draft(d):
        s = "Now: your draft."
        w = tw(s, F_BODY) + 60
        rrect(d, (640 - w / 2, 408, 640 + w / 2, 456), SAND, None, 10, 0)
        text_c(d, 640, 418, s, F_BODY, (40, 34, 24))
    appear(img, t, sc.when("your draft"), draft, 0.5, 10)


COLD_OPEN = Extra("review", NARRATION, s_review, "Reviewed before release", tail=1.0)
