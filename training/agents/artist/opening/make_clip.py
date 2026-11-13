#!/usr/bin/env python3
"""
Purpose: The artist's six-second opening. From agents/artist.md, "Your personality": florid,
         flowery language, a plot is a "visual sonnet", a palette "a chromatic symphony", never
         merely done but having "brought forth a visual testament to the science within". The
         gag: a beret at an easel, a dull grey bar chart on the canvas labelled "Figure 1";
         with each flourish of the brush a bar bursts into colour and paint flies off the
         canvas as fireworks, a harp runs up the scale, and the label is painted over:
         "a visual sonnet".
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../artist_narrated.mp4.
Usage: python3 training/agents/artist/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import SKY  # noqa: E402  (the movie's own colour)
from lib.opening import (F_MID_SMALL, F_TAG, H, SR, W, Opening, add, font, glissando, noise_burst, text_centered, tone)  # noqa: E402

F_BRUSH = font("Brush Script.ttf", 44)
F_SMALLCAP = font("Verdana Bold.ttf", 18)
FLOURISH = [0.7, 1.3, 1.9, 2.4]            # one bar per stroke
PAINT = [(226, 100, 100), (244, 162, 97), (120, 200, 110), (110, 170, 235)]
CANVAS = (560, 240, 1000, 540)
BARS = [(600, 0.55), (700, 0.8), (800, 0.4), (900, 0.95)]      # x, height as a share of the canvas
FLOOR = 600


class Artist(Opening):
    agent = "artist"
    title = "THE ARTIST"
    tagline = "brings forth a visual testament to the science within"
    prompt_line = "ask the artist for the colony size figure for Nature, in our lab colours"
    title_at, tagline_at, prompt_at = 2.7, 3.5, 4.5
    title_y, tagline_y = 10, 185
    tagline_font = F_MID_SMALL
    title_colours = ((8, (30, 40, 90, 255)), (4, (110, 170, 235, 255)), (0, (255, 250, 240, 255)))
    tagline_colour, tagline_shadow = (230, 240, 255), (20, 30, 60)
    footer_colour = (220, 230, 250)
    # paint flies off the canvas with each stroke, in that stroke's colour
    fireworks_schedule = [(f - 0.75, 600 + 100 * k, 150 + 30 * (k % 2), k, 0.9 + 0.25 * k, "peony")
                          for k, f in enumerate(FLOURISH)] + [(2.6, 780, 100, 4, 1.6, "willow"), (3.3, 640, 160, 5, 1.0, "ring"),
                                                              (3.4, 920, 160, 6, 1.0, "ring")]
    fireworks_gain = 0.6
    shakes = [(f, 0.5) for f in FLOURISH]

    def __init__(self):
        super().__init__()
        # each stroke's rocket bursts in that stroke's paint
        palettes = [[c, tuple(min(255, v + 60) for v in c), (255, 255, 255)] for c in PAINT]
        for r, pal in zip(self.fireworks.rockets, palettes + [palettes[1], palettes[0], palettes[2]]):
            r.palette = pal
        self.splats = []

    def background(self, t):
        img = Image.new("RGB", (W, H), (236, 228, 214))
        d = ImageDraw.Draw(img)
        # a studio: skylight, a wall of past works, the floor
        d.rectangle((0, FLOOR, W, H), fill=(150, 120, 90))
        for x in range(0, W, 80):
            d.line((x, FLOOR, x + 40, H), fill=(130, 100, 75), width=2)
        rs = random.Random(9)
        for k, (x, y) in enumerate(((80, 120), (260, 90), (120, 330), (320, 300), (1100, 110), (1130, 330))):
            w, h = rs.randint(110, 160), rs.randint(90, 140)
            d.rectangle((x - 6, y - 6, x + w + 6, y + h + 6), fill=(90, 70, 40))
            d.rectangle((x, y, x + w, y + h), fill=rs.choice(PAINT))
            d.ellipse((x + 20, y + 20, x + w - 20, y + h - 20), fill=rs.choice(PAINT))
        return img

    def easel_and_canvas(self, d, t):
        x0, y0, x1, y1 = CANVAS
        d.line((x0 - 30, FLOOR, x0 + 40, y0 - 40), fill=(120, 85, 45), width=12)
        d.line((x1 + 30, FLOOR, x1 - 40, y0 - 40), fill=(120, 85, 45), width=12)
        d.line(((x0 + x1) / 2, FLOOR, (x0 + x1) / 2, y0 - 40), fill=(120, 85, 45), width=12)
        d.rectangle((x0 - 10, y1, x1 + 10, y1 + 16), fill=(120, 85, 45))
        d.rectangle((x0, y0, x1, y1), fill=(250, 248, 240), outline=(60, 50, 40), width=4)
        # the axes and the bars, grey until painted
        d.line((x0 + 30, y1 - 40, x1 - 30, y1 - 40), fill=(90, 90, 90), width=3)
        d.line((x0 + 30, y0 + 30, x0 + 30, y1 - 40), fill=(90, 90, 90), width=3)
        for k, (bx, share) in enumerate(BARS):
            top = y1 - 40 - share * (y1 - y0 - 90)
            painted = t >= FLOURISH[k]
            if painted:
                a = min(1.0, (t - FLOURISH[k]) / 0.15)
                col = tuple(int(150 + (c - 150) * a) for c in PAINT[k])
            else:
                col = (165, 165, 165)
            d.rectangle((bx - 30, top, bx + 30, y1 - 40), fill=col)
            if painted:
                # dripping paint
                for j in range(3):
                    dy = min(40, (t - FLOURISH[k]) * 60) * (0.5 + 0.3 * j)
                    d.line((bx - 16 + j * 16, y1 - 40, bx - 16 + j * 16, y1 - 40 + dy), fill=col, width=5)
        # the label: "Figure 1" until the last stroke, then painted over
        if t < FLOURISH[-1]:
            d.text((x0 + 40, y0 + 10), "Figure 1", font=F_SMALLCAP, fill=(100, 100, 100))
        else:
            a = min(1.0, (t - FLOURISH[-1]) / 0.3)
            d.line((x0 + 36, y0 + 20, x0 + 36 + 90 * a, y0 + 18), fill=PAINT[0], width=8)
            text_centered(d, y0 + 2, "a visual sonnet", F_BRUSH, (110, 60, 160), x_centre=(x0 + x1) / 2 + 40)

    def painter(self, d, t):
        """Beret, smock, palette in the left hand; the right arm sweeps the brush across the canvas on each flourish."""
        x, y = 400, FLOOR
        skin, smock = (235, 200, 170), (245, 245, 250)
        d.line((x - 14, y - 80, x - 20, y), fill=(60, 50, 60), width=16)
        d.line((x + 14, y - 80, x + 20, y), fill=(60, 50, 60), width=16)
        d.rounded_rectangle((x - 40, y - 180, x + 40, y - 70), radius=14, fill=smock)
        for sx, sy, c in ((x - 20, y - 140, PAINT[0]), (x + 12, y - 110, PAINT[3]), (x - 5, y - 90, PAINT[2])):
            d.ellipse((sx - 7, sy - 5, sx + 7, sy + 5), fill=c)
        d.rectangle((x - 8, y - 180, x + 8, y - 110), fill=(40, 40, 60))        # a cravat, naturally
        # head, moustache, beret
        d.ellipse((x - 28, y - 240, x + 28, y - 180), fill=skin)
        d.ellipse((x - 16, y - 228, x - 10, y - 222), fill=(20, 20, 20))
        d.ellipse((x + 10, y - 228, x + 16, y - 222), fill=(20, 20, 20))
        d.arc((x - 20, y - 212, x + 20, y - 194), 200, 340, fill=(40, 30, 30), width=5)
        d.chord((x - 36, y - 262, x + 36, y - 224), 180, 360, fill=(30, 30, 40))
        d.ellipse((x - 4, y - 268, x + 4, y - 260), fill=(30, 30, 40))
        # the palette on the left arm
        d.line((x - 36, y - 160, x - 90, y - 150), fill=smock, width=14)
        d.ellipse((x - 150, y - 190, x - 70, y - 130), fill=(200, 170, 120))
        for k, c in enumerate(PAINT):
            d.ellipse((x - 140 + 16 * k, y - 180 + 8 * (k % 2), x - 128 + 16 * k, y - 168 + 8 * (k % 2)), fill=c)
        # the brush arm: a flourish is a sweep from low left to high right over the bar being painted
        ang, L = -0.6, 90
        colour = (110, 110, 110)
        for k, f in enumerate(FLOURISH):
            if f - 0.4 <= t < f + 0.3:
                k2 = (t - (f - 0.4)) / 0.7
                ang = -0.2 - 1.2 * math.sin(math.pi * k2)
                L = 90 + 60 * math.sin(math.pi * k2)
                colour = PAINT[k]
        sx, sy = x + 36, y - 165
        ex, ey = sx + L * math.cos(ang), sy + L * math.sin(ang)
        d.line((sx, sy, ex, ey), fill=smock, width=14)
        d.ellipse((ex - 10, ey - 10, ex + 10, ey + 10), fill=skin)
        bx, by = ex + 80 * math.cos(ang - 0.3), ey + 80 * math.sin(ang - 0.3)
        d.line((ex, ey, bx, by), fill=(120, 80, 40), width=6)
        d.ellipse((bx - 9, by - 9, bx + 9, by + 9), fill=colour)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.easel_and_canvas(d, t)
        # paint splats: launched from the brush on each stroke, land on the wall and stay
        for k, f in enumerate(FLOURISH):
            if f <= t < f + dt:
                rs = random.Random(k)
                for _ in range(14):
                    a = rs.uniform(-2.8, -0.3)
                    s = rs.uniform(300, 700)
                    self.splats.append([BARS[k][0], 420.0, s * math.cos(a), s * math.sin(a), PAINT[k], rs.uniform(6, 16), False])
        for p in self.splats:
            if not p[6]:
                p[3] += 800 * dt
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                if p[1] > FLOOR - 10 or p[0] < 10 or p[0] > W - 10:
                    p[6] = True
                    p[1] = min(p[1], FLOOR - 10)
            r = p[5]
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=p[4])
            if p[6]:
                d.ellipse((p[0] - r / 2, p[1] + r, p[0] + r / 2, p[1] + r * 2.2), fill=p[4])
        self.painter(d, t)
        return frame

    def audio(self, left, right):
        for k, f in enumerate(FLOURISH):
            sw = noise_burst(0.35, cutoff=3500, decay=9, attack=0.06)
            add(left, int((f - 0.25) * SR), sw, 0.5)
            add(right, int((f - 0.25) * SR), sw, 0.5)
            # a plucked note per stroke, climbing
            note = tone(392.0 * 2 ** (k * 4 / 12), 0.8, decay=3.0, harmonics=(1.0, 0.4, 0.2), attack=0.005)
            add(left, int(f * SR), note, 0.35)
            add(right, int(f * SR), note, 0.35)
        # the chromatic symphony: a harp run on the last stroke, then a string chord under the title
        g = glissando(261.6, 1046.5, 1.4, gain=0.3)
        add(left, int(FLOURISH[-1] * SR), g, 1.0)
        add(right, int((FLOURISH[-1] + 0.02) * SR), g, 1.0)
        n = int(SR * 3.2)
        tt = np.arange(n) / SR
        env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - 1.6) * 1.2)
        chord = sum(np.sin(2 * math.pi * f * tt) * (1 + 0.02 * np.sin(2 * math.pi * 5 * tt)) for f in (261.6, 329.6, 392.0, 523.3, 659.3))
        add(left, int(2.7 * SR), chord * env, 0.09)
        add(right, int(2.7 * SR), chord * env, 0.09)


if __name__ == "__main__":
    Artist().main()
