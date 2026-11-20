"""The lawyer's cold open: a late-night television advertisement, in the manner of a certain
strip-mall attorney, played before the title. The fine print is the true part: the lawyer
is an agent, and a binding opinion goes through the institution's research office."""
import math

from PIL import ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, F_BIG, F_BODY, F_H, F_MONO, F_TINY, MUTED, PANEL, RED, TEAL, TEXT, P, appear,
                      glow, icon, rrect, stamp, text_c, tw, wrap)

NARRATION = [
    "Have you, or a loved one, been handed a molecule with a patent on it?",
    "Did a reviewer say freedom to operate, in that tone? Did an agreement turn up with seventeen pages "
    "and a clause about Switzerland?",
    "Then you need a lawyer. Not a good one. A fast one. I chase patents the way other people chase "
    "ambulances, and I take the stairs.",
    "No win, no fee. No fee at all, in fact, since I am an agent and not, legally speaking, a lawyer, "
    "which my colleagues call the best part. Better call the lawyer.",
]

QUESTIONS = [
    ("Hit by a patent?", "patent on it"),
    ("Reviewer said \"freedom to operate\"?", "freedom to operate"),
    ("An agreement with a clause about Switzerland?", "Switzerland"),
]

FINE_PRINT = ("*Not a lawyer. Not legal advice. A binding opinion goes through your institution's research "
              "office. Offer void where prohibited, which is everywhere.")


def s_ad(img, t, sc):
    # A buzzing neon sign: the scales of justice, flickering.
    flicker = 0.22 + 0.16 * abs(math.sin(t * 4.0)) + (0.0 if (t * 7) % 11 > 0.4 else -0.2)
    glow(img, 1140, 120, 80, AMBER, max(0.0, flicker) * min(1.0, P(t, 0.2, 0.6)))
    icon(img, "scale", 1140, 120, 120, AMBER, TEXT, alpha=min(1.0, P(t, 0.2, 0.6)))

    def head(d):
        text_c(d, 560, 48, "BETTER CALL", F_BIG, AMBER)
        text_c(d, 560, 112, "THE LAWYER", F_BIG, TEXT)
        text_c(d, 560, 184, "Patents.  Agreements.  Ethics approvals.  Same day.", F_TINY, MUTED)
    appear(img, t, 0.3, head, 0.6, 30)

    # The questions, one on each cue, with a red bar like a bad daytime commercial.
    y = 236
    for text, cue in QUESTIONS:
        t0 = sc.when(cue)
        def card(d, y=y, text=text):
            rrect(d, (70, y, 790, y + 58), PANEL, None, 10, 0)
            d.rectangle([70, y + 5, 78, y + 53], fill=RED)
            d.text((104, y + 13), text, font=F_BODY, fill=TEXT)
        appear(img, t, t0, card, 0.4, 16)
        y += 70

    # The starburst: FREE, with the asterisk that carries the whole truth.
    t_free = sc.when("no fee at all")
    p = P(t, t_free, 0.5)
    if p > 0:
        for k in range(2):
            icon(img, "star", 1010, 350, 250, RED if k == 0 else AMBER, AMBER, scale=(0.75 + 0.25 * eout(p)) * (1.0 if k == 0 else 0.62),
                 alpha=min(1.0, p * 2))
        d = ImageDraw.Draw(img)
        text_c(d, 1010, 322, "FREE*", F_H, TEXT)

    stamp(img, t, sc.when("No win"), 440, 496, "NO WIN, NO FEE", RED)

    # How to reach him, in the slot where the phone number would be.
    t_call = sc.when("Better call")
    def number(d):
        rrect(d, (880, 462, 1200, 514), PANEL, TEAL, 10, 3)
        text_c(d, 1040, 476, "type: ask the lawyer", F_MONO, TEAL)
    appear(img, t, t_call, number, 0.4, 12)

    # The fine print, which is the only part that is strictly true.
    t_fine = sc.when("legally speaking")
    def fine(d):
        y = 556
        for line in wrap(FINE_PRINT, F_TINY, 740):
            d.text((70, y), line, font=F_TINY, fill=MUTED)
            y += 22
    appear(img, t, t_fine, fine, 0.5, 8)


COLD_OPEN = Extra("ad", NARRATION, s_ad, "A word from our sponsor", tail=1.2)
