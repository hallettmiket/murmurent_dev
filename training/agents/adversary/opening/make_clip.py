#!/usr/bin/env python3
"""
Purpose: The adversary's six-second opening. From agents/adversary.md, "Your personality":
         passive-aggressive, never shouts, sarcasm exquisitely calibrated, the colleague who
         sends emails at 11pm with the subject line "a few small thoughts", never celebrates,
         merely notes the absence of catastrophic failure. The gag: a dark office at 11pm, a
         result card ("AUC 0.99!!!") arrives with one feeble party popper; the adversary does
         not look up, types the email, subject "a few small thoughts", sends it, and a stamp
         comes down on the card: NO CATASTROPHIC FAILURE. NOTED.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../adversary_narrated.mp4.
Usage: python3 training/agents/adversary/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import RED  # noqa: E402  (the movie's own colour)
from lib.opening import (F_MID, F_MONO, F_TAG, H, SR, W, Opening, add, clock, click, font, laptop,  # noqa: E402
                         noise_burst, stick_figure, text_centered, tone)

F_STAMP = font("Impact.ttf", 40)
F_MAIL = font("Menlo.ttc", 20)
POP = 0.9                  # the party popper
TYPE_FROM, TYPE_TO = 1.3, 2.3
SUBJECT = "a few small thoughts"
SEND = 2.45
STAMP = 3.7
FLOOR = 600


class Adversary(Opening):
    agent = "adversary"
    title = "THE ADVERSARY"
    tagline = "merely notes the absence of catastrophic failure"
    prompt_line = "ask the adversary to audit the classifier before we send it to the reviewers"
    title_at, tagline_at, prompt_at = 2.65, 3.3, 4.5
    title_colours = ((8, (60, 10, 10, 255)), (4, (226, 100, 100, 255)), (0, (255, 235, 230, 255)))
    tagline_colour, tagline_shadow = (255, 210, 200), (50, 10, 10)
    footer_colour = (240, 200, 195)
    fireworks_schedule = []         # it never celebrates
    shakes = [(STAMP, 1.5)]

    def setup(self):
        rs = random.Random(4)
        self.confetti = [[760.0, 330.0, rs.uniform(-60, 60), rs.uniform(-260, -120), rs.choice([(255, 200, 60), (90, 170, 255), (255, 90, 120)])]
                         for _ in range(7)]      # seven pieces; the popper was not a good one

    def background(self, t):
        img = Image.new("RGB", (W, H), (14, 14, 22))
        d = ImageDraw.Draw(img)
        # a window onto a city at night
        d.rectangle((880, 60, 1220, 400), fill=(20, 22, 40), outline=(50, 50, 60), width=8)
        rs = random.Random(8)
        for x in range(900, 1200, 36):
            h = rs.randint(80, 220)
            d.rectangle((x, 400 - h, x + 26, 396), fill=(30, 32, 50))
            for wy in range(400 - h + 10, 390, 18):
                for wx in (x + 5, x + 15):
                    if rs.random() < 0.45:
                        d.rectangle((wx, wy, wx + 6, wy + 8), fill=(220, 200, 120))
        clock(d, 180, 150, 80, 11.0, face=(230, 226, 215), rim=(40, 40, 50))
        d.rectangle((0, FLOOR, W, H), fill=(30, 28, 36))
        # the desk
        d.rectangle((300, 470, 980, 490), fill=(70, 55, 45))
        d.rectangle((320, 490, 340, FLOOR), fill=(55, 45, 38))
        d.rectangle((940, 490, 960, FLOOR), fill=(55, 45, 38))
        # the desk lamp, the only light in the room
        d.line((900, 470, 860, 330), fill=(80, 80, 90), width=6)
        d.pieslice((790, 300, 900, 370), 180, 360, fill=(60, 60, 70))
        lamp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(lamp).polygon([(800, 360), (890, 360), (1000, 480), (560, 480)], fill=(255, 225, 160, 70))
        lamp = lamp.filter(ImageFilter.GaussianBlur(25))
        img.paste(lamp, (0, 0), lamp)
        return img

    def card(self, d, t):
        """The result someone is pleased with, pinned up on the left; the stamp lands on it at STAMP."""
        x, y = 250, 380
        d.rectangle((x - 130, y - 70, x + 130, y + 70), fill=(250, 246, 230), outline=(120, 110, 90), width=3)
        d.ellipse((x - 6, y - 76, x + 6, y - 64), fill=(200, 40, 40))
        text_centered(d, y - 50, "our new model", F_TAG, (60, 60, 70), x_centre=x)
        text_centered(d, y - 22, "AUC 0.99!!!", F_MID, (30, 120, 60), x_centre=x)
        text_centered(d, y + 36, "(on the training set)", F_TAG, (130, 130, 130), x_centre=x)

    def him(self, d, t):
        """At the laptop, side on, grey cardigan, reading glasses, no reaction to anything;
        the hands type between TYPE_FROM and TYPE_TO."""
        x, y = 560, 520
        skin, cardigan = (225, 200, 180), (105, 105, 115)
        d.rounded_rectangle((x - 50, y - 150, x + 50, y - 20), radius=22, fill=cardigan)
        d.rectangle((x - 16, y - 150, x + 16, y - 80), fill=(200, 60, 60))      # a tie, straight
        hy = y - 150
        d.ellipse((x - 32, hy - 66, x + 32, hy + 4), fill=skin)
        d.chord((x - 34, hy - 72, x + 34, hy - 34), 180, 360, fill=(120, 120, 125))     # grey, thinning
        for ex in (x - 14, x + 14):
            d.rectangle((ex - 12, hy - 40, ex + 12, hy - 24), outline=(50, 50, 60), width=3)
            d.ellipse((ex - 3, hy - 35, ex + 3, hy - 29), fill=(30, 30, 40))
        d.line((x - 10, hy - 48, x - 18, hy - 46), fill=(80, 80, 85), width=3)     # one brow, slightly raised
        d.line((x + 6, hy - 50, x + 18, hy - 52), fill=(80, 80, 85), width=3)
        d.line((x - 10, hy - 10, x + 10, hy - 10), fill=(140, 90, 90), width=3)     # the mouth, a line
        # arms to the keyboard
        typing = TYPE_FROM <= t < TYPE_TO
        for side in (-1, 1):
            wob = 4 * math.sin(t * 40 + side) if typing else 0
            d.line((x + 44 * side, y - 110, x + 70 * side, y - 40 + wob), fill=cardigan, width=16)
            hx = x + 71 * side
            d.ellipse((hx - 11, y - 50 + wob, hx + 11, y - 30 + wob), fill=skin)

    def mail(self, d, t):
        """The email window on the laptop screen, typed one character at a time."""
        box = laptop(d, 700, 475, w=300, h=170, screen=(238, 240, 245))
        x0, y0, x1, y1 = box
        d.rectangle((x0, y0, x1, y0 + 22), fill=(220, 222, 230))
        d.text((x0 + 8, y0 + 3), "New message", font=F_MAIL, fill=(60, 60, 70))
        d.text((x0 + 8, y0 + 30), "To:  the lab", font=F_MAIL, fill=(40, 40, 50))
        if t >= TYPE_FROM:
            k = min(1.0, (t - TYPE_FROM) / (TYPE_TO - TYPE_FROM))
            typed = SUBJECT[: int(len(SUBJECT) * k + 0.999)]
            cursor = "|" if int(t * 3) % 2 == 0 and t < SEND else ""
            d.text((x0 + 8, y0 + 56), f"Subject:  {typed}{cursor}", font=F_MAIL, fill=(40, 40, 50))
        if t >= SEND:
            a = min(1.0, (t - SEND) / 0.2)
            d.rounded_rectangle((x1 - 90, y1 - 40, x1 - 10, y1 - 10), radius=6, fill=(60, 110, 200))
            d.text((x1 - 70, y1 - 36), "Sent", font=F_MAIL, fill=(int(255 * a),) * 3)
        d.text((x0 + 8, y0 + 100), "23:00", font=F_MAIL, fill=(120, 120, 130))

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.card(d, t)
        self.him(d, t)
        self.mail(d, t)
        # the party popper: a cone on the desk, seven pieces of confetti, once
        d.polygon([(770, 360), (750, 330), (790, 330)], fill=(240, 120, 60))
        if t >= POP:
            for p in self.confetti:
                p[3] += 500 * dt
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[1] = min(p[1], 468)
                d.rectangle((p[0] - 5, p[1] - 3, p[0] + 5, p[1] + 3), fill=p[4])
            if t < POP + 0.5:
                k = (t - POP) / 0.5
                d.line((770, 330, 770 - 30 * k, 330 - 120 * k + 160 * k * k), fill=(255, 200, 60), width=3)
        return frame

    def overlay(self, frame, t, dt):
        if t >= STAMP:
            k = min(1.0, (t - STAMP) / 0.12)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            x, y = 250, 380
            ld.rounded_rectangle((x - 150, y - 44, x + 150, y + 44), radius=8, outline=(200, 30, 30, 230), width=6)
            text_centered(ld, y - 36, "NO CATASTROPHIC", F_STAMP, (200, 30, 30, 230), x_centre=x)
            text_centered(ld, y - 2, "FAILURE. NOTED.", F_STAMP, (200, 30, 30, 230), x_centre=x)
            layer = layer.rotate(-8, center=(x, y), resample=Image.BICUBIC)
            if k < 1.0:
                s = 1.8 - 0.8 * k
                nw, nh = int(W * s), int(H * s)
                layer = layer.resize((nw, nh)).crop((int(x * s - x), int(y * s - y), int(x * s - x) + W, int(y * s - y) + H))
            frame.paste(layer, (0, 0), layer)
        return frame

    def audio(self, left, right):
        # the clock, every second, the only sound in the room
        for k in range(6):
            tick = click(0.02)
            add(left, int(k * SR), tick, 0.5)
            add(right, int(k * SR), tick, 0.4)
        # the popper: a small pop and a sad, falling kazoo
        pop = noise_burst(0.15, cutoff=1500, decay=30)
        add(left, int(POP * SR), pop, 0.6)
        add(right, int(POP * SR), pop, 0.6)
        n = int(SR * 0.7)
        tt = np.arange(n) / SR
        f = 520 - 300 * tt / 0.7
        phase = 2 * math.pi * np.cumsum(f) / SR
        sad = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.3 * np.sign(np.sin(phase))) * np.exp(-tt * 2.5) * 0.12
        add(left, int((POP + 0.1) * SR), sad, 1.0)
        add(right, int((POP + 0.1) * SR), sad, 1.0)
        # typing, one key per character, brisk and even
        rs = random.Random(1)
        for k in range(len(SUBJECT)):
            s = TYPE_FROM + (TYPE_TO - TYPE_FROM) * k / len(SUBJECT)
            key = click(0.025)
            add(left, int(s * SR), key, 0.35 * rs.uniform(0.7, 1.0))
            add(right, int(s * SR), key, 0.35 * rs.uniform(0.7, 1.0))
        whoosh = noise_burst(0.5, cutoff=2500, decay=6, attack=0.1)
        add(left, int(SEND * SR), whoosh, 0.4)
        add(right, int(SEND * SR), whoosh, 0.4)
        # one low note under the title: not a fanfare
        add(left, int(2.65 * SR), tone(130.8, 2.0, decay=1.2, harmonics=(1.0, 0.3)), 0.3)
        add(right, int(2.65 * SR), tone(130.8, 2.0, decay=1.2, harmonics=(1.0, 0.3)), 0.3)
        # the stamp: a thud
        thud = noise_burst(0.3, cutoff=200, decay=14) * 3
        add(left, int(STAMP * SR), thud, 1.0)
        add(right, int(STAMP * SR), thud, 1.0)
        add(left, int(STAMP * SR), tone(70, 0.4, decay=8, harmonics=(1.0,)), 0.8)
        add(right, int(STAMP * SR), tone(70, 0.4, decay=8, harmonics=(1.0,)), 0.8)


if __name__ == "__main__":
    Adversary().main()
