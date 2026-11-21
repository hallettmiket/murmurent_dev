"""The detective's cold open: a case file from a certain 1950s police procedural, read in the
flat voice of an officer who has seen it all and will say none of it. A citation has gone
missing; the registries are canvassed; a DOI stands in a line-up; the stamp comes down. The
fine print is the true part: no person is the subject of a finding. Played before the title."""
import math

from PIL import ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, DIM, F_BIG, F_H, F_LABEL, F_MONO, F_MONO_S, F_TINY, MUTED, PANEL, RED, TEAL, TEXT, P,
                      appear, eout, icon, rrect, stamp, text_c, tw, wrap)

NARRATION = [
    "The report you are about to read is true. Only the accession numbers have been changed, to "
    "protect the innocent.",
    "Monday. Nine fourteen a.m. Day watch, manuscript detail. A citation had gone missing. I had a DOI, "
    "and no paper to go with it.",
    "I ran it through the registries. Crossref had never heard of it. Neither had DataCite. Neither had "
    "doi dot org. That is not an opinion. That is a record.",
    "Just the facts. Not who. Not why. The manuscript names a paper that does not exist. Proven. "
    "Case file closed.",
]

LINEUP = [
    ("10.1038/348699a0", "Basset, 1990", TEAL, "MATCH"),
    ("10.9999/does.not.exist", "nobody, never", RED, "NO RECORD"),
    ("10.1016/j.cell.2011.02.013", "Hanahan, 2011", TEAL, "MATCH"),
]

REGISTRIES = [("Crossref", "Crossref had"), ("DataCite", "DataCite"), ("doi.org", "doi dot org")]

FINE_PRINT = ("No person is the subject of a finding. The subject is the manuscript. A registry's answer is "
              "quoted, never paraphrased. Whether it was a mistake is not the detective's to say.")


def _typed(d, x, y, text, t, t0, f=F_MONO, fill=TEXT, cps=28):
    """A line typed out from t0 at cps characters a second, with a cursor while it types."""
    n = int(max(0.0, t - t0) * cps)
    shown = text[:n]
    d.text((x, y), shown, font=f, fill=fill)
    if 0 < n < len(text) and int(t * 6) % 2 == 0:
        d.rectangle([x + tw(shown, f) + 2, y + 2, x + tw(shown, f) + 12, y + f.size], fill=fill)


def s_case(img, t, sc):
    d = ImageDraw.Draw(img)
    # The case file: a manila folder with a typed label, the one prop the scene owns.
    p = P(t, 0.0, 0.6)
    fold_y = 60 + int(16 * (1 - eout(p)))
    rrect(d, (70, fold_y, 1210, 650), (46, 54, 74), (90, 98, 120), 14, 3)
    d.rectangle([70, fold_y, 420, fold_y + 34], fill=(90, 98, 120))
    d.text((88, fold_y + 6), "CASE FILE 341  ·  MANUSCRIPT DETAIL", font=F_MONO_S, fill=TEXT)
    d.text((940, fold_y + 8), "DAY WATCH", font=F_MONO_S, fill=MUTED)

    # The scene-setting line, typed.
    t_mon = sc.when("Monday")
    _typed(d, 110, fold_y + 70, "MON  09:14  DAY WATCH  ·  MANUSCRIPT DETAIL", t, t_mon, F_MONO, MUTED)
    t_miss = sc.when("gone missing")
    _typed(d, 110, fold_y + 104, "COMPLAINT:  one citation, missing.  DOI in hand.  No paper.", t, t_miss, F_MONO, TEXT)

    # The line-up: three DOIs against the height marks, the middle one not looking at the camera.
    t_run = sc.when("ran it through")
    pl = P(t, t_run, 0.5)
    if pl > 0:
        x0, y0, w, h = 110, fold_y + 160, 1060, 250
        d.rectangle([x0, y0, x0 + w, y0 + h], fill=(30, 36, 54))
        for k in range(6):
            yy = y0 + 30 + k * 38
            d.line([x0, yy, x0 + w, yy], fill=(52, 60, 84), width=1)
            d.text((x0 + 8, yy - 18), f"{6 - k}'", font=F_MONO_S, fill=DIM)
        for i, (doi, who, colour, verdict) in enumerate(LINEUP):
            cx = x0 + 200 + i * 330
            pp = P(t, t_run + 0.15 * i, 0.4)
            if pp <= 0:
                continue
            top = y0 + 40 + int(20 * (1 - eout(pp)))
            # A paper, standing up, with a number plate.
            rrect(d, (cx - 70, top, cx + 70, top + 150), PANEL, colour, 8, 3)
            for j in range(5):
                d.line([cx - 50, top + 30 + j * 20, cx + 50, top + 30 + j * 20], fill=DIM, width=3)
            rrect(d, (cx - 22, top + 118, cx + 22, top + 142), (20, 24, 36), None, 4, 0)
            text_c(d, cx, top + 121, str(i + 1), F_MONO_S, TEXT)
            text_c(d, cx, top + 162, doi, F_MONO_S, TEXT)
            text_c(d, cx, top + 184, who, F_TINY, MUTED)
            if i == 1:
                # The registries answer one by one, each on its cue.
                for k, (name, cue) in enumerate(REGISTRIES):
                    tk = sc.when(cue)
                    pk = P(t, tk, 0.3)
                    if pk > 0:
                        yy = top + 206 + k * 22
                        d.text((cx - 118, yy), f"{name}:", font=F_MONO_S, fill=MUTED)
                        d.text((cx + 8, yy), "no record", font=F_MONO_S, fill=RED)
            else:
                pk = P(t, t_run + 0.6, 0.3)
                if pk > 0:
                    text_c(d, cx, top + 206, verdict, F_MONO_S, colour)

    # "That is a record": a magnifying glass settles on the middle one.
    t_rec = sc.when("That is a record")
    pr = P(t, t_rec, 0.5)
    if pr > 0:
        icon(img, "mag", 110 + 200 + 330 + 95, fold_y + 160 + 60, 96, AMBER, TEXT, scale=1.4 - 0.4 * eout(pr), alpha=pr)
        d = ImageDraw.Draw(img)

    # The stamp.
    stamp(img, t, sc.when("Proven"), 640, fold_y + 285, "PROVEN", RED)

    # The fine print, which is the only part that is strictly the rules.
    t_fine = sc.when("Not who")
    def fine(dd):
        y = 548
        for line in wrap(FINE_PRINT, F_TINY, 1000):
            dd.text((110, y), line, font=F_TINY, fill=MUTED)
            y += 22
    appear(img, t, t_fine, fine, 0.5, 8)

    # The badge in the corner, from the first word.
    pb = P(t, 0.3, 0.6)
    if pb > 0:
        icon(img, "check", 1120, fold_y + 90, 70, TEAL, TEXT, alpha=pb)
        d = ImageDraw.Draw(img)
        text_c(d, 1120, fold_y + 132, "BADGE 341", F_TINY, MUTED)


COLD_OPEN = Extra("case", NARRATION, s_case, "The report you are about to read", tail=1.2)
