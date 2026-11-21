#!/usr/bin/env python3
"""
Purpose: The lab oracle's six-second opening. From agents/lab_oracle.md: the memory of the
         whole lab, read-only (freeze: frozen), holding only entries promoted from a personal
         oracle after the PI's or a peer's review, through `murmurent oracle publish`. The gag:
         a museum case of reviewed scrolls, frost on the glass; someone hurries in and slaps a
         sticky note reading "my hunch!!" on it; it bounces off and the READ-ONLY lamp lights.
         Then a reviewed scroll comes down the publish slot and takes its place with a chime.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../lab_oracle_narrated.mp4.
Usage: python3 training/agents/lab_oracle/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.opening import SR, W, H, Opening, add, chime, click, font, noise_burst, stick_figure, text_centered, tone  # noqa: E402

F_LABEL = font("Verdana Bold.ttf", 16)
F_HAND = font("Chalkboard.ttc", 22)
F_STAMP = font("Impact.ttf", 20)
F_SIGN = font("Verdana Bold.ttf", 22)
ARRIVE, PUSH, BOUNCE = 0.3, 1.3, 1.5
SLOT, LAND = 2.2, 3.0
CASE = (420, 150, 1000, 520)
FLOOR = 600
SCROLLS = [("chrM: use p14", 480), ("QC gate: 0.8", 630), ("batch 3: out", 780)]


class LabOracle(Opening):
    agent = "lab_oracle"
    title = "THE LAB ORACLE"
    tagline = "what the whole lab agreed, after review"
    prompt_line = "ask the lab oracle what the lab agreed on chrM"
    title_at, tagline_at, prompt_at = 3.2, 3.8, 4.6
    title_colours = ((8, (40, 20, 80, 255)), (4, (178, 150, 235, 255)), (0, (245, 240, 255, 255)))
    tagline_colour, tagline_shadow = (225, 210, 255), (30, 15, 60)
    footer_colour = (225, 210, 255)
    fireworks_schedule = []          # a museum; frost sparkles instead
    shakes = [(BOUNCE, 0.5)]
    seed = 8

    def background(self, t):
        img = Image.new("RGB", (W, H), (62, 58, 72))
        d = ImageDraw.Draw(img)
        d.rectangle((0, FLOOR, W, H), fill=(118, 112, 124))
        for x in range(0, W, 160):
            d.line((x, FLOOR, x - 60, H), fill=(100, 95, 106), width=2)
        for cx in (300, 710, 1120):          # spotlights
            d.polygon([(cx, 0), (cx - 160, FLOOR), (cx + 160, FLOOR)], fill=(72, 68, 84))
        return img

    def scroll(self, d, x, y, label, stamp=True, alpha=255):
        d.rounded_rectangle((x - 50, y - 60, x + 50, y + 60), radius=8, fill=(236, 226, 200))
        d.ellipse((x - 54, y - 70, x + 54, y - 50), fill=(200, 185, 150))
        d.ellipse((x - 54, y + 50, x + 54, y + 70), fill=(200, 185, 150))
        d.text((x - 44, y - 40), label, font=F_LABEL, fill=(60, 50, 40))
        if stamp:
            d.rectangle((x - 46, y + 10, x + 46, y + 38), outline=(190, 40, 40), width=3)
            text_centered(d, y + 12, "REVIEWED", F_STAMP, (190, 40, 40), x_centre=x)

    def case(self, d, t):
        x0, y0, x1, y1 = CASE
        d.rectangle((x0 - 20, y1, x1 + 20, FLOOR), fill=(80, 60, 48))         # the pedestal
        d.rectangle((x0, y0, x1, y1), fill=(210, 226, 240))
        for label, x in SCROLLS:
            self.scroll(d, x, 350, label)
        if t >= SLOT:                        # the reviewed scroll comes down the slot
            k = min(1.0, (t - SLOT) / (LAND - SLOT))
            y = 60 + (350 - 60) * (1 - (1 - k) ** 2)
            self.scroll(d, 930, int(y), "run 17: MMP11")
            d.text((880, int(y) - 100), "PI reviewed", font=F_LABEL, fill=(40, 120, 70))
        d.rectangle((x0, y0, x1, y1), outline=(120, 130, 150), width=6)
        d.line((x0 + 30, y1 - 30, x1 - 300, y0 + 30), fill=(240, 248, 255), width=3)   # the glass
        rs = random.Random(3)
        for _ in range(60):                  # frost in the corners: freeze: frozen
            cx = rs.choice((x0 + rs.randint(5, 90), x1 - rs.randint(5, 90)))
            cy = rs.choice((y0 + rs.randint(5, 70), y1 - rs.randint(5, 70)))
            tw = 0.6 + 0.4 * math.sin(t * 5 + cx)
            d.point((cx, cy), fill=(int(255 * tw),) * 3)
        d.rectangle((900, y0 - 40, 960, y0), fill=(70, 70, 80))                # the publish slot
        d.text((835, y0 - 66), "murmurent oracle publish", font=F_LABEL, fill=(220, 220, 230))
        plate = (x0 + 120, y1 + 16, x1 - 120, y1 + 56)
        d.rectangle(plate, fill=(200, 170, 90))
        text_centered(d, y1 + 24, "THE LAB AGREED  ·  reviewed entries", F_LABEL, (60, 40, 20), x_centre=(x0 + x1) / 2)
        on = BOUNCE <= t < BOUNCE + 1.1 and int((t - BOUNCE) * 6) % 2 == 0
        d.rounded_rectangle((x0 + 170, y0 - 110, x1 - 170, y0 - 70), radius=8, fill=(200, 40, 40) if on else (70, 30, 30))
        text_centered(d, y0 - 104, "READ-ONLY", F_SIGN, (255, 230, 230) if on else (120, 80, 80), x_centre=(x0 + x1) / 2)

    def note(self, d, t):
        if t < ARRIVE:
            return
        if t < PUSH:
            k = (t - ARRIVE) / (PUSH - ARRIVE)
            x = -60 + (300 + 60) * k
            bob, leg = 4 * math.sin(t * 18), 8 * math.sin(t * 18)
            nx, ny = x + 70, FLOOR - 160
        else:
            x, bob, leg = 300, 0, 0
            if t < BOUNCE:
                nx, ny = 370 + (CASE[0] - 370) * (t - PUSH) / (BOUNCE - PUSH), FLOOR - 170
            else:
                k = min(1.0, (t - BOUNCE) / 0.5)
                nx, ny = CASE[0] - 10 - 120 * k, FLOOR - 170 + 200 * k * k
        stick_figure(d, x, FLOOR, shirt=(150, 70, 60), hair=(40, 30, 20), bob=bob, leg=leg, arm_r=(-0.5, 70), arm_l=(2.6, 60))
        if t >= BOUNCE + 0.5:
            nx, ny = CASE[0] - 130, FLOOR + 10
        ang = 0 if t < BOUNCE else (t - BOUNCE) * 9
        pts = [(nx + 40 * math.cos(a + ang), ny + 40 * math.sin(a + ang)) for a in (0.785, 2.356, 3.927, 5.498)]
        d.polygon(pts, fill=(250, 230, 90))
        d.text((nx - 30, ny - 16), "my", font=F_HAND, fill=(70, 50, 20))
        d.text((nx - 36, ny + 4), "hunch!!", font=F_HAND, fill=(70, 50, 20))

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.case(d, t)
        self.note(d, t)
        return frame

    def audio(self, left, right):
        for k in range(7):
            s = ARRIVE + k * 0.14
            c = click(0.03)
            add(left, int(s * SR), c, 0.3)
            add(right, int(s * SR), c, 0.2)
        thud = tone(90, 0.3, decay=14, harmonics=(1.0, 0.3))
        add(left, int(BOUNCE * SR), thud, 0.9)
        add(right, int(BOUNCE * SR), thud, 0.9)
        buzz = tone(110, 0.7, decay=3, harmonics=(1.0, 0.8, 0.6, 0.4, 0.3))
        add(left, int((BOUNCE + 0.05) * SR), buzz, 0.5)
        add(right, int((BOUNCE + 0.05) * SR), buzz, 0.5)
        slide = noise_burst(0.8, cutoff=3000, decay=5, attack=0.1)
        add(left, int(SLOT * SR), slide, 0.3)
        add(right, int(SLOT * SR), slide, 0.3)
        ch = chime((659.3, 784.0, 1046.5), spacing=0.12, length=1.8)
        add(left, int(LAND * SR), ch, 0.9)
        add(right, int(LAND * SR), ch, 0.9)
        c = click()
        add(left, int(4.6 * SR), c, 0.3)
        add(right, int(4.6 * SR), c, 0.3)


if __name__ == "__main__":
    LabOracle().main()
