"""The security guard's cold open: a head-up display from a certain kind of 1980s film. Red
scanlines, a reticle, a readout that finds an API key, a date of birth and a sandwich in the
change you are about to push, a countdown it is very good at waiting through, and the verdict
it actually gives: Clear. Played before the title."""
import math

from PIL import Image, ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, DIM, F_BIG, F_LABEL, F_MONO, F_MONO_S, F_TINY, H, MUTED, PANEL, RED, TEAL, TEXT, W,
                      P, appear, emoji_sprite, eout, paste_c, rrect, stamp, text_c)

NARRATION = [
    "Halt. Identify yourself. You are attempting to push to the repository.",
    "Scanning. Line forty-two: an API key. Line ninety: a patient's date of birth. Line one hundred "
    "and three: a sandwich. The sandwich may proceed.",
    "You have twenty seconds to comply. Remove the key. Remove the date of birth. I will wait. I am "
    "very good at waiting.",
    "Hasta la vista, token. Clear. I will be back. At the next pull request.",
]

DIFF = [
    (" 40", "model: opus", None),
    (" 41", "endpoint: https://api.example.org", None),
    (" 42", "api_key: sk-live-9f3a7c21e0b4...", "threat"),
    (" 43", "timeout: 30", None),
    ("   ", "...", None),
    (" 89", "patient_id: P-0417", None),
    (" 90", "dob: 1961-04-17", "threat"),
    (" 91", "visit: 2026-11-03", None),
    ("   ", "...", None),
    ("102", "notes: ran the pipeline again", None),
    ("103", "lunch: sandwich", "fine"),
    ("104", "status: done", None),
]

READOUT = [
    ("SCAN MODE", "PUSH", None),
    ("TARGET", "exp/7/config.yaml", None),
    ("L42", "API KEY", "forty-two"),
    ("L90", "DATE OF BIRTH", "ninety"),
    ("L103", "SANDWICH", "sandwich"),
]

DIRECTIVES = ["1. PROTECT THE PATIENTS", "2. KEEP THE SECRETS", "3. CLEAR, OR SAY WHERE", "4. [CLASSIFIED]"]


def _hud(img, t):
    """Red tint and scanlines over everything drawn so far."""
    tint = Image.new("RGB", (W, H), (120, 20, 24))
    img.paste(Image.blend(img, tint, 0.16))
    lines = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lines)
    off = int(t * 40) % 4
    for y in range(off, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, 110), width=1)
    img.paste(lines, (0, 0), lines)


def _reticle(d, cx, cy, r, colour, spin):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=3)
    d.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], outline=colour, width=2)
    for k in range(4):
        a = spin + k * math.pi / 2
        d.line([(cx + math.cos(a) * r * 0.7, cy + math.sin(a) * r * 0.7),
                (cx + math.cos(a) * r * 1.25, cy + math.sin(a) * r * 1.25)], fill=colour, width=3)


def s_hud(img, t, sc):
    d = ImageDraw.Draw(img)
    # The camera view: the change about to be pushed.
    rrect(d, (490, 70, 900, 560), (10, 10, 14), DIM, 6, 2)
    d.text((506, 78), "diff  (what you are about to push)", font=F_TINY, fill=MUTED)
    y = 108
    rows = {}
    for n, line, kind in DIFF:
        d.text((506, y), n, font=F_MONO_S, fill=MUTED)
        d.text((548, y), line, font=F_MONO_S, fill=TEXT)
        rows[n.strip()] = y
        y += 36

    # The readout, line by line, on the narration.
    rrect(d, (60, 70, 460, 400), (10, 10, 14), RED, 6, 2)
    d.text((76, 78), "SECURITY GUARD  v2026.11", font=F_TINY, fill=RED)
    yy = 112
    for key, val, cue in READOUT:
        t0 = 0.3 if cue is None else sc.when(cue)
        def row(d, yy=yy, key=key, val=val, cue=cue):
            d.text((76, yy), key, font=F_MONO, fill=MUTED)
            d.text((200, yy), val, font=F_MONO, fill=RED if cue in ("forty-two", "ninety") else TEXT)
            if cue in ("forty-two", "ninety"):
                d.text((76, yy + 26), "        THREAT DETECTED", font=F_TINY, fill=RED)
            elif cue == "sandwich":
                d.text((76, yy + 26), "        MAY PROCEED", font=F_TINY, fill=TEAL)
        appear(img, t, t0, row, 0.25, 6)
        d = ImageDraw.Draw(img)
        yy += 56 if cue else 36

    # The boxes on the lines, as they are named, and the sandwich itself.
    for n, cue, colour in (("42", "forty-two", RED), ("90", "ninety", RED), ("103", "sandwich", TEAL)):
        t0 = sc.when(cue)
        if t > t0:
            p = eout(P(t, t0, 0.3))
            ry = rows[n]
            d.rectangle([540, ry - 4, 540 + 350 * p, ry + 26], outline=colour, width=3)
    if t > sc.when("sandwich") + 0.3:
        paste_c(img, emoji_sprite("🥪", 48), 850, rows["103"] + 12, 1.0, 1.0)

    # The reticle: roams, then locks onto each line in turn.
    targets = [(sc.when("forty-two"), rows["42"] + 12), (sc.when("ninety"), rows["90"] + 12),
               (sc.when("sandwich"), rows["103"] + 12), (sc.when("Hasta"), rows["42"] + 12)]
    cx, cy = 695 + 120 * math.sin(t * 0.9), 320 + 150 * math.sin(t * 0.6)
    for t0, ty in targets:
        if t > t0:
            k = eout(P(t, t0, 0.4))
            cx, cy = cx + (700 - cx) * k, cy + (ty - cy) * k
    _reticle(ImageDraw.Draw(img), cx, cy, 44, RED, t * 1.5)

    # The directives, top right.
    rrect(d := ImageDraw.Draw(img), (930, 70, 1220, 250), (10, 10, 14), DIM, 6, 2)
    d.text((946, 78), "PRIME DIRECTIVES", font=F_TINY, fill=MUTED)
    for i, line in enumerate(DIRECTIVES):
        d.text((946, 108 + i * 32), line, font=F_LABEL, fill=TEXT if i < 3 else DIM)

    # The countdown. It is very good at waiting.
    t_count = sc.when("twenty seconds")
    if t > t_count:
        n = max(20 - int(t - t_count), 0)
        d.text((946, 290), "TIME TO COMPLY", font=F_TINY, fill=MUTED)
        text_c(d, 1075, 310, f"{n:02d}", F_BIG, RED if n > 3 else AMBER)
        if t > sc.when("very good at waiting"):
            text_c(d, 1075, 392, "(still waiting)", F_TINY, MUTED)

    # The token is terminated, and the verdict follows.
    t_bye = sc.when("Hasta")
    if t > t_bye:
        ry = rows["42"]
        p = eout(P(t, t_bye, 0.5))
        d.line([(548, ry + 12), (548 + 330 * p, ry + 12)], fill=RED, width=4)
        appear(img, t, t_bye + 0.3, lambda d: d.text((946, 440), "TOKEN: TERMINATED", font=F_MONO, fill=RED), 0.3, 6)
    stamp(img, t, sc.when("Clear."), 1075, 510, "CLEAR", TEAL, angle=-6)

    _hud(img, t)


COLD_OPEN = Extra("hud", NARRATION, s_hud, "Halt", tail=1.0)
