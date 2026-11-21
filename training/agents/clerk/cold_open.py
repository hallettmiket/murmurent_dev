"""The clerk's cold open: window four of a counter that has seen it all. A clerk who does not
love the job, a lit cigarette under a NO SMOKING sign, a NOW SERVING display that has barely
moved, and the one thing said in earnest: the answer is read off the page, named and dated,
and when the page does not say, it is Unknown. Played before the title."""
import math

from PIL import ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, DIM, F_BIG, F_H, F_LABEL, F_TINY, MUTED, PANEL, RED, SAND, TEAL, TEXT,
                      P, appear, eout, figure, rrect, smoke, stamp, text_c, tw)

NARRATION = [
    "Next.",
    "No, I do not know when your exam must be printed off the top of my head. That is what the page is for.",
    "I read it on the institution's own page, name the page and the date, and remember it, so you do "
    "not come back tomorrow. You will anyway.",
    "If the page does not say, I say Unknown. I do not guess. That is how you ended up at the wrong "
    "window. Take a number.",
]

GLASS = (36, 56, 92)
COUNTER = (70, 66, 74)
LED = (240, 70, 60)


def _led(d, x, y, w, h, label, digits, colour=LED):
    rrect(d, (x, y, x + w, y + h), (18, 14, 18), DIM, 8, 3)
    d.text((x + 14, y + 8), label, font=F_TINY, fill=MUTED)
    f = F_BIG
    d.text((x + w - tw(digits, f) - 18, y + h - f.size - 10), digits, font=f, fill=colour)


def s_counter(img, t, sc):
    d = ImageDraw.Draw(img)
    # The window, the counter, the sign.
    rrect(d, (380, 70, 900, 440), GLASS, DIM, 10, 4)
    d.rectangle([0, 430, 1280, 560], fill=COUNTER)
    d.rectangle([0, 430, 1280, 438], fill=(120, 112, 118))
    rrect(d, (560, 44, 720, 90), PANEL, SAND, 8, 3)
    text_c(d, 640, 54, "WINDOW 4", F_LABEL, SAND)
    rrect(d, (690, 110, 880, 150), (250, 246, 240), RED, 6, 3)
    text_c(d, 785, 118, "NO SMOKING", F_LABEL, RED)

    # The clerk, glasses, behind the glass. Not getting up.
    figure(img, t, 0.2, 640, 430, SAND, "", h=170, kind="glasses")

    # The ashtray and the cigarette, lit, directly under the sign.
    d = ImageDraw.Draw(img)
    d.ellipse([790, 418, 880, 446], fill=(40, 40, 46), outline=DIM, width=2)
    d.line([(808, 424), (852, 414)], fill=(240, 236, 220), width=5)
    d.line([(848, 415), (856, 413)], fill=AMBER, width=5)
    glow_p = 0.6 + 0.4 * abs(math.sin(t * 3.0))
    d.ellipse([853, 409, 860, 416], fill=(255, int(120 + 80 * glow_p), 40))
    smoke(img, t, 857, 408, 150)

    # Now serving: it ticks once, on "Next", from seven to eight.
    t_next = sc.when("Next")
    n = 8 if t > t_next + 0.4 else 7
    d = ImageDraw.Draw(img)
    _led(d, 60, 90, 290, 110, "NOW SERVING", f"{n:03d}")
    rrect(d, (60, 470, 330, 536), (250, 246, 240), None, 6, 0)
    d.text((76, 478), "CLOSED FOR LUNCH", font=F_LABEL, fill=COUNTER)
    d.text((76, 504), "11:00 to 15:00", font=F_TINY, fill=COUNTER)

    # What the clerk actually offers, on cards against the glass.
    def card(y, head, body, colour):
        def f(d):
            rrect(d, (950, y, 1220, y + 76), PANEL, colour, 10, 3)
            d.text((966, y + 10), head, font=F_LABEL, fill=colour)
            d.text((966, y + 40), body, font=F_TINY, fill=TEXT)
        return f
    appear(img, t, sc.when("the page is for"), card(90, "ASK THE PAGE", "the institution's own, read today", TEAL), 0.4, 12)
    appear(img, t, sc.when("name the page"), card(180, "NAMED AND DATED", "which page, and when", TEAL), 0.4, 12)
    appear(img, t, sc.when("remember it"), card(270, "REMEMBERED", "and re-read before it is relied on", TEAL), 0.4, 12)

    stamp(img, t, sc.when("I say Unknown"), 205, 320, "UNKNOWN", RED, angle=-7)

    # Your number. Theirs is eight.
    t_num = sc.when("Take a number")
    p = P(t, t_num, 0.5)
    if p > 0:
        x = 1010 + (1 - eout(p)) * 300
        d = ImageDraw.Draw(img)
        rrect(d, (x, 452, x + 200, 546), (250, 246, 240), None, 8, 0)
        for yy in range(458, 546, 12):
            d.rectangle([x - 2, yy, x + 2, yy + 5], fill=COUNTER)
            d.rectangle([x + 198, yy, x + 202, yy + 5], fill=COUNTER)
        text_c(d, x + 100, 458, "YOUR NUMBER", F_TINY, COUNTER)
        text_c(d, x + 100, 478, "318", F_H, COUNTER)
        text_c(d, x + 100, 522, "thank you for waiting", F_TINY, MUTED)


COLD_OPEN = Extra("counter", NARRATION, s_counter, "Window four", tail=0.8)
