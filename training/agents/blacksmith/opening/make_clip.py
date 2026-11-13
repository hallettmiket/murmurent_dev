#!/usr/bin/env python3
"""
Purpose: The blacksmith's six-second opening, the loud one. From agents/blacksmith.md,
         "Your personality": workmanlike and precise; "You do not promise; you measure."
         The gag: at the forge, three ringing hammer blows on a white-hot bar, sparks on
         every one, the fourth so hard the sparks go up as fireworks; then, with the whole
         sky still banging, the blacksmith calmly holds a caliper to the bar and the reading
         comes up: measured, not promised.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../blacksmith_narrated.mp4.
Usage: python3 training/agents/blacksmith/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import AMBER  # noqa: E402  (the movie's own colour)
from lib.opening import (F_MID, F_TAG, H, SR, W, Opening, add, anvil, bang, clink, fanfare,  # noqa: E402
                         hum, lowpass, text_centered)

GROUND = 580
ANVIL = (640, 470)                 # the anvil's top face, where the bar lies
HITS = [0.8, 1.4, 2.0]             # the three ringing blows
BIG = 2.45                         # the fourth, the one that sends the sparks up
MEASURE = 3.6                      # the caliper comes down
READ = 4.1                         # the reading shows


class Blacksmith(Opening):
    agent = "blacksmith"
    title = "THE BLACKSMITH"
    tagline = "does not promise; it measures"
    prompt_line = "ask the blacksmith to train the classifier on our data and show me the code"
    title_at, tagline_at, prompt_at = 2.65, 3.1, 4.6
    title_colours = ((8, (90, 30, 0, 255)), (4, (255, 120, 20, 255)), (0, (255, 240, 200, 255)))
    tagline_colour, tagline_shadow = (255, 220, 150), (60, 20, 0)
    # the sparks of the big blow come down as fireworks, all at once, big, loud
    fireworks_schedule = [
        (BIG, 640, 110, 5, 1.8, "ring"), (BIG + 0.05, 300, 160, 1, 1.4, "peony"), (BIG + 0.1, 980, 150, 0, 1.4, "peony"),
        (BIG + 0.5, 180, 220, 5, 1.0, "willow"), (BIG + 0.55, 1100, 220, 1, 1.0, "willow"),
        (BIG + 0.9, 500, 130, 0, 1.2, "peony"), (BIG + 0.95, 780, 130, 5, 1.2, "peony"),
        (BIG + 1.5, 640, 90, 1, 2.0, "peony"), (BIG + 1.9, 330, 200, 0, 0.9, "ring"), (BIG + 1.95, 950, 200, 5, 0.9, "ring"),
        (BIG + 2.5, 220, 170, 1, 1.1, "peony"), (BIG + 2.55, 1060, 170, 0, 1.1, "peony"),
    ]
    shakes = [(h, 1.2) for h in HITS] + [(BIG, 4.0)]

    def setup(self):
        self.sparks = []       # live sparks: x, y, vx, vy, born

    def background(self, t):
        img = Image.new("RGB", (W, H), (22, 14, 12))
        d = ImageDraw.Draw(img)
        # stone wall
        rs = random.Random(5)
        for row in range(0, GROUND, 46):
            off = 0 if (row // 46) % 2 == 0 else 50
            for x in range(-50 + off, W, 100):
                c = 38 + rs.randint(-8, 8)
                d.rounded_rectangle((x + 2, row + 2, x + 96, row + 44), radius=6, fill=(c + 6, c, c - 2))
        # the furnace, left, its mouth flickering
        d.rounded_rectangle((60, 250, 330, GROUND), radius=18, fill=(50, 40, 38))
        fl = 0.8 + 0.2 * math.sin(t * 23) + 0.1 * math.sin(t * 41)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((110 - 90 * fl, 330 - 60 * fl, 280 + 90 * fl, 560 + 60 * fl), fill=(255, 120, 20, int(90 * fl)))
        glow = glow.filter(ImageFilter.GaussianBlur(30))
        img.paste(glow, (0, 0), glow)
        d.rounded_rectangle((120, 330, 270, 520), radius=40, fill=(int(255 * fl), int(150 * fl), 30))
        d.rounded_rectangle((140, 380, 250, 520), radius=30, fill=(255, int(220 * fl), int(120 * fl)))
        # hanging tools
        for x, kind in ((900, "tongs"), (980, "hammer"), (1060, "file")):
            d.line((x, 0, x, 120), fill=(120, 110, 100), width=3)
            d.rectangle((x - 8, 120, x + 8, 230), fill=(80, 60, 40))
            if kind == "hammer":
                d.rectangle((x - 34, 120, x + 34, 150), fill=(150, 150, 160))
            elif kind == "tongs":
                d.line((x - 10, 120, x - 16, 230), fill=(110, 110, 120), width=6)
                d.line((x + 10, 120, x + 16, 230), fill=(110, 110, 120), width=6)
        # floor and the anvil on its stump
        d.rectangle((0, GROUND, W, H), fill=(44, 36, 34))
        d.rectangle((590, 500, 690, GROUND), fill=(80, 55, 30))
        ax, ay = ANVIL
        d.polygon([(ax - 120, ay), (ax + 100, ay), (ax + 150, ay + 8), (ax + 100, ay + 22), (ax + 40, ay + 22),
                   (ax + 40, ay + 36), (ax - 60, ay + 36), (ax - 60, ay + 22), (ax - 120, ay + 22)], fill=(70, 72, 82))
        d.polygon([(ax - 120, ay), (ax + 100, ay), (ax + 150, ay + 8), (ax - 110, ay + 8)], fill=(110, 112, 124))
        return img

    def bar(self, d, t):
        """The bar on the anvil: white hot, flattening a little with each blow."""
        ax, ay = ANVIL
        flat = sum(1 for h in HITS + [BIG] if t >= h)
        hgt = 26 - 4 * flat
        half = 70 + 10 * flat
        heat = max(0.35, 1 - 0.1 * t)
        col = (255, int(200 * heat + 40), int(120 * heat))
        d.rounded_rectangle((ax - half, ay - hgt, ax + half, ay), radius=6, fill=col)
        d.rounded_rectangle((ax - half + 10, ay - hgt + 4, ax + half - 10, ay - hgt + 10), radius=3, fill=(255, 255, 230))

    def smith(self, d, t):
        """Big, square, leather apron over the amber shirt; the hammer arm swings; the other arm holds the tongs."""
        x, y = 820, GROUND
        skin, shirt, apron = (225, 180, 140), AMBER, (95, 62, 35)
        # legs
        d.line((x - 16, y - 80, x - 24, y), fill=(45, 40, 55), width=18)
        d.line((x + 16, y - 80, x + 24, y), fill=(45, 40, 55), width=18)
        d.rectangle((x - 40, y - 6, x - 8, y + 4), fill=(30, 20, 15))
        d.rectangle((x + 8, y - 6, x + 40, y + 4), fill=(30, 20, 15))
        # torso: shirt, then apron
        d.rounded_rectangle((x - 48, y - 180, x + 48, y - 70), radius=16, fill=shirt)
        d.rounded_rectangle((x - 36, y - 150, x + 36, y - 60), radius=10, fill=apron)
        d.line((x - 30, y - 150, x - 14, y - 178), fill=apron, width=6)
        d.line((x + 30, y - 150, x + 14, y - 178), fill=apron, width=6)
        # head: bald, big beard, bushy brows, safety glasses
        d.ellipse((x - 30, y - 244, x + 30, y - 180), fill=skin)
        d.ellipse((x - 30, y - 210, x + 30, y - 160), fill=(90, 55, 30))
        d.ellipse((x - 10, y - 214, x + 10, y - 202), fill=skin)
        d.rectangle((x - 26, y - 226, x - 6, y - 214), fill=(190, 220, 240), outline=(30, 30, 30), width=2)
        d.rectangle((x + 6, y - 226, x + 26, y - 214), fill=(190, 220, 240), outline=(30, 30, 30), width=2)
        d.line((x - 26, y - 232, x - 8, y - 230), fill=(90, 55, 30), width=5)
        d.line((x + 8, y - 230, x + 26, y - 232), fill=(90, 55, 30), width=5)
        # left arm with tongs holding the bar
        sx, sy = x - 44, y - 160
        ax, ay = ANVIL
        d.line((sx, sy, ax + 80, ay - 10), fill=shirt, width=16)
        d.line((ax + 80, ay - 10, ax + 60, ay - 6), fill=(110, 110, 120), width=6)
        d.ellipse((ax + 72, ay - 20, ax + 92, ay), fill=skin)
        # hammer arm: (shoulder angle, hammer angle) keyframes; rest up, a wind-up, the snap down onto the bar
        rest, wind, strike = (-2.0, -1.1), (-1.6, -0.8), (-3.3, -3.1)
        ang, ha = rest
        for h in HITS + [BIG]:
            w = 0.45 if h != BIG else 0.6
            if h - w <= t < h:
                k = (t - (h - w)) / w
                ang, ha = rest[0] + (wind[0] - rest[0]) * k, rest[1] + (wind[1] - rest[1]) * k
            elif h <= t < h + 0.08:
                k = (t - h) / 0.08
                ang, ha = wind[0] + (strike[0] - wind[0]) * k, wind[1] + (strike[1] - wind[1]) * k
            elif h + 0.08 <= t < h + 0.45:
                k = (t - h - 0.08) / 0.37
                ang, ha = strike[0] + (rest[0] - strike[0]) * k, strike[1] + (rest[1] - strike[1]) * k
        if t >= MEASURE:
            ang = -2.6
        sx, sy = x + 44, y - 160
        L = 110
        ex, ey = sx + L * math.cos(ang), sy + L * math.sin(ang)
        d.line((sx, sy, ex, ey), fill=shirt, width=18)
        d.ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=skin)
        # the hammer, held perpendicular to the forearm, or set down when measuring
        if t < MEASURE:
            hl = 120
            hx, hy = ex + hl * math.cos(ha), ey + hl * math.sin(ha)
            d.line((ex, ey, hx, hy), fill=(120, 80, 40), width=12)
            px, py = math.cos(ha + math.pi / 2), math.sin(ha + math.pi / 2)
            d.polygon([(hx - 36 * px - 16 * math.cos(ha), hy - 36 * py - 16 * math.sin(ha)),
                       (hx + 36 * px - 16 * math.cos(ha), hy + 36 * py - 16 * math.sin(ha)),
                       (hx + 36 * px + 16 * math.cos(ha), hy + 36 * py + 16 * math.sin(ha)),
                       (hx - 36 * px + 16 * math.cos(ha), hy - 36 * py + 16 * math.sin(ha))], fill=(150, 152, 165))
        else:
            # the caliper, lowered onto the bar
            k = min(1.0, (t - MEASURE) / 0.4)
            cx, cy = ANVIL[0] - 20, ANVIL[1] - 200 + 160 * (1 - (1 - k) ** 2)
            d.line((ex, ey, cx + 40, cy - 40), fill=(150, 152, 165), width=6)
            d.rectangle((cx - 90, cy - 50, cx + 90, cy - 36), fill=(200, 205, 215))
            d.rectangle((cx - 86, cy - 36, cx - 70, cy + 14), fill=(200, 205, 215))
            d.rectangle((cx + 70, cy - 36, cx + 86, cy + 14), fill=(200, 205, 215))
            for i in range(0, 170, 10):
                d.line((cx - 80 + i, cy - 50, cx - 80 + i, cy - 44 if i % 50 else cy - 40), fill=(40, 40, 50), width=1)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.bar(d, t)
        # sparks from each blow
        for h, n in [(h, 40) for h in HITS] + [(BIG, 160)]:
            if h <= t < h + dt:
                rs = random.Random(int(h * 100))
                big = h == BIG
                for _ in range(n):
                    a = rs.uniform(-3.0, -0.1)
                    s = rs.uniform(300, 900) if big else rs.uniform(150, 500)
                    self.sparks.append([ANVIL[0], ANVIL[1] - 20, s * math.cos(a), s * math.sin(a), t])
        live = []
        for p in self.sparks:
            p[3] += 700 * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            age = t - p[4]
            if age < 0.7 and p[1] < GROUND:
                live.append(p)
                f = 1 - age / 0.7
                d.line((p[0], p[1], p[0] - p[2] * 0.02, p[1] - p[3] * 0.02), fill=(255, int(230 * f), int(120 * f)), width=3)
        self.sparks = live
        self.smith(d, t)
        # a flash on the big blow
        if BIG <= t < BIG + 0.2:
            frame = Image.blend(frame, Image.new("RGB", (W, H), (255, 240, 200)), 1 - (t - BIG) / 0.2)
        return frame

    def overlay(self, frame, t, dt):
        if t >= READ:
            d = ImageDraw.Draw(frame)
            a = min(1.0, (t - READ) / 0.2)
            txt = "bar: 42.0 mm, measured"
            bb = d.textbbox((0, 0), txt, font=F_TAG)
            tw = bb[2] - bb[0]
            x, y = ANVIL[0] - tw / 2 - 20, ANVIL[1] - 150
            box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(box).rounded_rectangle((x - 12, y - 8, x + tw + 12, y + 34), radius=8, fill=(0, 0, 0, int(210 * a)))
            frame.paste(box, (0, 0), box)
            d.text((x, y), txt, font=F_TAG, fill=(int(255 * a), int(230 * a), int(150 * a)))
        return frame

    def audio(self, left, right):
        n = SR * 6
        # the forge roars under everything
        roar = lowpass(np.random.randn(n), 90) * 3.0
        left[:n] += roar
        right[:n] += roar
        add(left, 0, hum(6.0, 50.0, 0.3), 1.0)
        add(right, 0, hum(6.0, 50.0, 0.3), 1.0)
        for h in HITS:
            a = anvil()
            add(left, int(h * SR), a, 1.3)
            add(right, int(h * SR), a, 1.6)
        big = anvil()
        add(left, int(BIG * SR), big, 2.2)
        add(right, int(BIG * SR), big, 2.4)
        b = bang(2.5)
        add(left, int(BIG * SR), b, 1.2)
        add(right, int(BIG * SR), b, 1.2)
        fanfare(2.65, left, 0.4)
        fanfare(2.65, right, 0.4)
        # the caliper's small click and the reading's ding, under all the noise
        c = clink(((3500, 40), (5200, 60)), length=0.12)
        add(left, int((MEASURE + 0.4) * SR), c, 0.8)
        add(right, int((MEASURE + 0.4) * SR), c, 0.8)
        ding = clink(((2093, 4), (4186, 8)), length=1.0)
        add(left, int(READ * SR), ding, 0.9)
        add(right, int(READ * SR), ding, 0.9)


if __name__ == "__main__":
    Blacksmith().main()
