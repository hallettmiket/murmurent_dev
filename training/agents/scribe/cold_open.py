"""The scribe's cold open: Ernest Hemingway, named on screen and in the first line, takes a forty-one-word
sentence apart on a typewriter page. The passive voice is mounted on the wall like a marlin.
The glass stays full until the figure legend is done, and the legend is never done. The one
true thing: every number and citation is kept, and the house style, which says do not go
choppy, wins in the end. Played before the title."""
from PIL import ImageDraw

from lib.agent_movie import Extra
from lib.draw import (AMBER, DIM, F_BODY, F_LABEL, F_MONO, F_MONO_S, F_TINY, MUTED, PANEL, RED, SAND, TEAL, TEXT,
                      P, appear, rrect, text_c, tw, wrap)

NARRATION = [
    "I write the way Ernest Hemingway wrote. Short sentences. True sentences. I was in the lab. The data "
    "were good and true. The sentence was not. It was forty-one words long and it began with it should "
    "be noted that. I shot it.",
    "I fished the verb out of the passive voice. It was a big verb. I let the adjectives go. They "
    "were not good adjectives. Decisively. Critically. Gone.",
    "I keep every number. I keep every citation. I do not touch the glass until the figure legend "
    "is done. The legend is never done.",
    "The house style says do not go choppy. Twenty-three to twenty-seven words to a sentence. I can "
    "do that. I do not enjoy it. Revised.",
]

# The sentence, word by word, with the cue on which each word is struck (None: it stays).
SENTENCE = [
    ("It", "shot it"), ("should", "shot it"), ("be", "shot it"), ("noted", "shot it"), ("that", "shot it"),
    ("tumour", None), ("growth", None), ("was", None), ("observed", "big verb"), ("to", "big verb"), ("be", "big verb"),
    ("decisively", "Decisively"), ("reduced", None), ("by", "big verb"), ("the", None), ("drug,", None),
    ("and", None), ("survival", None), ("was", None), ("critically", "Critically"), ("improved,", None),
    ("in", None), ("the", None), ("treated", None), ("mice,", None), ("in", None), ("all", None), ("three", None),
    ("cohorts", None), ("that", "big verb"), ("were", "big verb"), ("followed", None), ("by", "big verb"),
    ("us.", "big verb"),
]
REVISED = ("The drug halved tumour growth in the treated mice, and the treated mice lived longer than "
           "the controls, in each of the three cohorts we followed.")       # 26 words, as the house style asks

PAPER = (244, 238, 222)
INK = (40, 36, 34)
WOOD = (92, 58, 36)


def _fish(d, x, y, w, colour):
    """A marlin on a plaque, pointing left."""
    h = w * 0.28
    d.polygon([(x, y), (x + w * 0.62, y - h * 0.55), (x + w * 0.78, y - h * 0.2), (x + w, y - h * 0.9),
               (x + w * 0.9, y), (x + w, y + h * 0.9), (x + w * 0.78, y + h * 0.2), (x + w * 0.62, y + h * 0.55)],
              fill=colour)
    d.polygon([(x + w * 0.3, y - h * 0.4), (x + w * 0.45, y - h * 1.1), (x + w * 0.6, y - h * 0.5)], fill=colour)
    d.line([(x, y), (x - w * 0.22, y - h * 0.05)], fill=colour, width=4)
    d.ellipse([x + w * 0.2, y - h * 0.25, x + w * 0.27, y - h * 0.1], fill=PAPER)


def s_desk(img, t, sc):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 540, 1280, 640], fill=WOOD)
    d.rectangle([0, 540, 1280, 546], fill=(130, 90, 58))

    # The trophy: the passive voice, landed.
    rrect(d, (40, 80, 300, 250), (70, 44, 28), (130, 90, 58), 10, 3)
    _fish(d, 90, 150, 170, (150, 160, 180))
    text_c(d, 170, 196, "PASSIVE VOICE", F_LABEL, SAND)
    text_c(d, 170, 220, "1,200 lb  ·  Key West  ·  2026", F_TINY, MUTED)

    # Whose manner this is, said plainly, for anyone who has not read him.
    def who(d):
        rrect(d, (1000, 80, 1240, 196), PANEL, SAND, 10, 3)
        text_c(d, 1120, 92, "in the manner of", F_TINY, MUTED)
        text_c(d, 1120, 114, "ERNEST", F_LABEL, SAND)
        text_c(d, 1120, 138, "HEMINGWAY", F_LABEL, SAND)
        text_c(d, 1120, 168, "\"one true sentence\"", F_TINY, TEXT)
    appear(img, t, sc.when("Hemingway"), who, 0.5, 10)

    # The glass. It stays full.
    d.rectangle([1080, 420, 1180, 540], outline=(200, 200, 210), width=3)
    d.rectangle([1083, 460, 1177, 537], fill=(196, 120, 40))
    d.rectangle([1083, 460, 1177, 466], fill=(230, 170, 90))
    appear(img, t, sc.when("never done"), lambda d: text_c(d, 1130, 395, "still full", F_TINY, MUTED), 0.4, 6)

    # The page, and the sentence, word by word.
    d = ImageDraw.Draw(img)
    rrect(d, (330, 60, 970, 530), PAPER, None, 4, 0)
    d.text((360, 80), "Results, draft 3", font=F_TINY, fill=(120, 110, 100))
    f = F_MONO
    x, y, x0, xmax = 360, 118, 360, 940
    for word, cue in SENTENCE:
        w = tw(word, f)
        if x + w > xmax:
            x, y = x0, y + f.size + 10
        struck = cue is not None and t > sc.when(cue)
        d.text((x, y), word, font=f, fill=(150, 140, 130) if struck else INK)
        if struck:
            d.line([(x - 2, y + f.size * 0.55), (x + w + 2, y + f.size * 0.55)], fill=RED, width=3)
        x += w + tw(" ", f)
    y_rev = y + f.size + 36

    # What is left, in the house style: one result per sentence, not choppy.
    t_rev = sc.when("I can do that")
    def revised(d):
        yy = y_rev
        d.line([(360, yy - 12), (940, yy - 12)], fill=DIM, width=1)
        for ln in wrap(REVISED, F_MONO_S, 570):
            d.text((360, yy), ln, font=F_MONO_S, fill=INK)
            yy += F_MONO_S.size + 8
        d.text((360, yy + 6), "26 words. Every number kept.", font=F_TINY, fill=TEAL)
    appear(img, t, t_rev, revised, 0.5, 8)

    # The verdict and the list of changes, each with its rule.
    def card(d):
        rrect(d, (360, 404, 940, 506), (232, 226, 208), TEAL, 10, 3)
        d.text((380, 412), "Revised", font=F_LABEL, fill=TEAL)
        yy = 440
        for ln in wrap("9 changes, each with its rule: cut what explains yourself (rule 1), say it literally (2), "
                       "turn the volume down (3), one result per sentence (4).", F_TINY, 540):
            d.text((380, yy), ln, font=F_TINY, fill=INK)
            yy += F_TINY.size + 5
    appear(img, t, sc.when("Revised."), card, 0.5, 10)


COLD_OPEN = Extra("desk", NARRATION, s_desk, "A clean, well-lighted sentence", tail=1.2)
