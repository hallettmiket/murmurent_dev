"""The lookout's cold open: the crow's nest of a tall ship, a spyglass sweeping the horizon,
and the ship's bell. Three sightings are called down, each rung by how much it matters: a new
hook in a changelog, three bells, adopt; a memory paper, two bells, consider; a video that will
change everything, one bell, watch, from the transcript, not watched. The true part is the last
line: the lookout rings the bell and does not steer the ship. Played before the title."""
import math

from PIL import Image, ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, DIM, F_H, F_LABEL, F_MONO, F_MONO_S, F_TINY, H, MUTED, PANEL, RED, TEAL, TEXT, W,
                      P, appear, eout, rrect, stamp, text_c, tw, wrap)

NARRATION = [
    "Crow's nest. Dawn watch. Horizon clear, bow to stern. Nothing new. Wait.",
    "Sighting, two points off the bow. A changelog. A hook that can refuse a push. Three bells: adopt.",
    "Sighting, dead ahead. A paper on agent memory. Read in full. Two bells: consider.",
    "Sighting, astern. A video. It will change everything, it says. From the transcript; I did not "
    "watch it. One bell: watch.",
    "Ten sightings at most, each with where it goes. I ring the bell. I do not steer the ship.",
]

SIGHTINGS = [
    # (cue, where it appears on the horizon, label, what it is, bells, verdict, colour)
    ("two points off the bow", 260, "CHANGELOG", "a hook that refuses a push", 3, "ADOPT", TEAL),
    ("dead ahead", 560, "arXiv", "agent memory, read in full", 2, "CONSIDER", AMBER),
    ("astern", 860, "VIDEO", "from the transcript", 1, "WATCH", MUTED),
]

FINE_PRINT = ("Everything reported was read today on its own page. A video is reported from its description "
              "and transcript. The lookout installs nothing and edits nothing: the PI decides, the blacksmith "
              "builds.")

SEA = (22, 46, 78)
SKY_DAWN = (62, 48, 86)
SKY_LOW = (214, 140, 90)
HORIZON = 250
RAIL = 470


def _sky(d):
    for y in range(0, HORIZON):
        k = y / HORIZON
        d.line([0, y, W, y], fill=tuple(int(a + (b - a) * k) for a, b in zip(SKY_DAWN, SKY_LOW)))
    d.rectangle([0, HORIZON, W, H], fill=SEA)
    for k in range(8):
        y = HORIZON + 24 + k * 22
        d.line([0, y, W, y], fill=(30, 58, 94), width=2)


def _nest(d, t):
    # The mast, the crow's nest and its rail, from below, so the sightings sit above the rail.
    d.rectangle([1100, RAIL, 1140, H], fill=(70, 50, 34))
    rrect(d, (980, RAIL, 1260, RAIL + 70), (88, 62, 40), (120, 90, 60), 10, 3)
    for x in range(1000, 1260, 40):
        d.line([x, RAIL, x, RAIL + 70], fill=(70, 50, 34), width=3)
    # The lookout: a head and shoulders above the rail, and the spyglass sweeping until a sighting.
    d.ellipse([1090, RAIL - 86, 1150, RAIL - 26], fill=(235, 190, 150))
    d.rectangle([1076, RAIL - 30, 1164, RAIL], fill=(40, 60, 110))
    d.rectangle([1086, RAIL - 100, 1154, RAIL - 80], fill=(30, 30, 40))


def _spyglass(d, t, angle):
    cx, cy = 1120, RAIL - 60
    L = 150
    ex, ey = cx + L * math.cos(angle), cy - L * math.sin(angle)
    d.line([cx, cy, ex, ey], fill=(140, 110, 60), width=14)
    d.line([cx, cy, ex, ey], fill=(200, 170, 90), width=8)
    d.ellipse([ex - 10, ey - 10, ex + 10, ey + 10], fill=(40, 40, 60), outline=(200, 170, 90), width=3)


def _ship(d, x, y, colour, scale=1.0):
    w, h = int(70 * scale), int(26 * scale)
    d.polygon([(x - w, y), (x + w, y), (x + w - 14, y + h), (x - w + 10, y + h)], fill=colour)
    d.line([x, y, x, y - int(60 * scale)], fill=colour, width=3)
    d.polygon([(x + 2, y - int(58 * scale)), (x + int(44 * scale), y - int(14 * scale)), (x + 2, y - int(12 * scale))], fill=colour)


def _bell(img, t, t0, n):
    """The ship's bell, rung n times from t0."""
    d = ImageDraw.Draw(img)
    cx, cy = 1120, 150
    swing = 0.0
    for k in range(n):
        tk = t0 + k * 0.28
        if tk <= t < tk + 0.28:
            swing = 0.5 * math.sin((t - tk) / 0.28 * math.pi)
    d.line([cx, 60, cx, cy - 40], fill=(120, 100, 70), width=6)
    ox = int(36 * math.sin(swing))
    d.polygon([(cx - 30 + ox, cy + 10), (cx + 30 + ox, cy + 10), (cx + 18 + ox // 2, cy - 40), (cx - 18 + ox // 2, cy - 40)],
              fill=(214, 170, 60), outline=(120, 90, 30))
    d.ellipse([cx - 8 + ox, cy + 4, cx + 8 + ox, cy + 20], fill=(90, 70, 30))
    for k in range(n):
        tk = t0 + k * 0.28
        pk = P(t, tk, 0.5)
        if 0 < pk < 1:
            r = int(30 + 60 * pk)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 230, 150), width=max(1, int(4 * (1 - pk))))


def s_nest(img, t, sc):
    d = ImageDraw.Draw(img)
    _sky(d)

    # The horizon log in the corner, typed as the watch is called.
    t_dawn = sc.when("Dawn watch")
    pl = P(t, t_dawn, 0.4)
    if pl > 0:
        rrect(d, (40, 40, 420, 128), (20, 28, 48), DIM, 10, 2)
        d.text((56, 50), "CROW'S NEST  ·  DAWN WATCH", font=F_MONO_S, fill=MUTED)
        d.text((56, 74), "horizon: clear, bow to stern", font=F_MONO_S, fill=TEXT)
        t_wait = sc.when("Wait")
        if t >= t_wait:
            d.text((56, 98), "sighting" + "." * (int(t * 4) % 4), font=F_MONO_S, fill=AMBER)

    # The sightings come over the horizon on their cues, each with its ship, label and bells.
    cues = [sc.when(cue) for cue, *_ in SIGHTINGS]
    for (cue, x, label, what, bells, verdict, colour), t0 in zip(SIGHTINGS, cues):
        p = P(t, t0, 0.9)
        if p <= 0:
            continue
        rise = int(40 * (1 - eout(p)))
        _ship(d, x, HORIZON + 6 + rise, colour, scale=0.9)
        pb = P(t, t0 + 0.6, 0.4)
        if pb > 0:
            y = HORIZON + 50 + int(10 * (1 - eout(pb)))
            rrect(d, (x - 110, y, x + 110, y + 78), PANEL, colour, 10, 2)
            text_c(d, x, y + 8, label, F_LABEL, colour)
            text_c(d, x, y + 36, what, F_TINY, TEXT)
            text_c(d, x, y + 56, f"{bells} bell" + ("s" if bells > 1 else ""), F_TINY, AMBER)
        _bell(img, t, t0 + 0.9, bells)
        d = ImageDraw.Draw(img)
        stamp(img, t, sc.when(verdict.lower()) if verdict != "WATCH" else sc.when("One bell"), x, HORIZON + 170, verdict, colour, angle=-6)
        d = ImageDraw.Draw(img)

    # The nest, the lookout and the spyglass, sweeping until the first sighting, then fixed on each.
    _nest(d, t)
    fixed = [(t0, x) for (cue, x, *_), t0 in zip(SIGHTINGS, cues) if t >= t0]
    if fixed:
        _, x = fixed[-1]
        angle = math.atan2(RAIL - 60 - HORIZON - 20, x + 40 - 1120)
    else:
        angle = math.pi / 2 + 0.9 * math.sin(t * 1.6)
    _spyglass(d, t, angle)

    # The whole report, and the true part.
    t_rep = sc.when("Ten sightings")
    def fine(dd):
        y = 500
        for line in wrap(FINE_PRINT, F_TINY, 860):
            dd.text((60, y), line, font=F_TINY, fill=MUTED)
            y += 22
    appear(img, t, t_rep, fine, 0.5, 8)
    t_ring = sc.when("I ring the bell")
    pr = P(t, t_ring, 0.5)
    if pr > 0:
        d = ImageDraw.Draw(img)
        text_c(d, 480, 556, "rings the bell; does not steer the ship", F_H, TEXT)


COLD_OPEN = Extra("nest", NARRATION, s_nest, "Crow's nest", tail=1.2)
