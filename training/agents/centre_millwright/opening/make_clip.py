#!/usr/bin/env python3
"""
Purpose: The centre millwright's six-second opening. From agents/centre_millwright.md,
         "Personality": the colleague who notices the new postdoc was added to the project but
         never invited to the Slack channel, and silently fixes it before the daily standup;
         writes tickets, not essays; "Reconciled ...: 2 ACL grants, 1 Slack invite. 0
         unresolved." The gag, literally that: 8:57, the desired-versus-actual screen has one
         red cell, a wrench cursor flips it green, a ticket lands on the board, and at 9:00 the
         standup walks in and nobody looks at the screen.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../centre_millwright_narrated.mp4.
Usage: python3 training/agents/centre_millwright/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import lib.opening as O  # noqa: E402
from lib.draw import TEAL  # noqa: E402
from lib.opening import SR, W, H, Opening, add, chime, click, clock, font, noise_burst, stick_figure, text_centered, tone  # noqa: E402

F_TITLE = font("Impact.ttf", 112)
F_CELL = font("Verdana Bold.ttf", 20)
F_HEAD = font("Verdana Bold.ttf", 16)
F_TICKET = font("Menlo.ttc", 19)
ROWS = [("@bob", (1, 1, 1)), ("@carla", (1, 1, 1)), ("@alice", (1, 0, 1)), ("@dmitri", (1, 1, 1))]
COLS = ["project", "slack", "github"]
MOVE = (0.7, 1.6)                        # the wrench goes to the red cell
FIX = 1.7                                # and flips it
TICKET = 2.3                             # the ticket lands on the board
WALK = (3.3, 4.3)                        # the standup walks in
NINE = 4.3                               # 9:00
SCREEN = (70, 80, 760, 520)
FLOOR = 640
RED, GREEN = (220, 70, 70), (70, 200, 110)


class CentreMillwright(Opening):
    agent = "centre_millwright"
    title = "THE CENTRE MILLWRIGHT"
    tagline = "fixed before the standup noticed"
    prompt_line = "ask the centre millwright to reconcile the project's access"
    title_at, tagline_at, prompt_at = 2.7, 3.2, 4.6
    title_colours = ((8, (10, 50, 45, 255)), (4, (52, 190, 170, 255)), (0, (235, 250, 245, 255)))
    tagline_colour, tagline_shadow = (200, 240, 230), (10, 40, 36)
    footer_colour = (200, 240, 230)
    fireworks_schedule = []          # nothing to celebrate; it was never a problem
    seed = 9

    def titles(self, frame, t):
        old = O.F_BIG
        O.F_BIG = F_TITLE                # the name is long; a smaller face keeps it on the screen
        try:
            return super().titles(frame, t)
        finally:
            O.F_BIG = old

    def background(self, t):
        img = Image.new("RGB", (W, H), (40, 48, 70))
        d = ImageDraw.Draw(img)
        d.rectangle((0, FLOOR, W, H), fill=(60, 66, 86))
        d.rectangle((1190, 200, 1280, FLOOR), fill=(90, 70, 50))             # the door
        d.ellipse((1200, 420, 1212, 432), fill=(220, 200, 120))
        return img

    def cell(self, k):
        x = SCREEN[0] + 250 + k * 150
        return x

    def mark(self, d, x, y, ok, col):
        if ok:
            d.line((x - 12, y, x - 3, y + 10, x + 14, y - 10), fill=col, width=5)
        else:
            d.line((x - 10, y - 10, x + 10, y + 10), fill=col, width=5)
            d.line((x - 10, y + 10, x + 10, y - 10), fill=col, width=5)

    def screen(self, d, t):
        d.rounded_rectangle(SCREEN, radius=10, fill=(16, 22, 36), outline=(90, 100, 130), width=4)
        d.text((SCREEN[0] + 24, SCREEN[1] + 18), "desired vs actual  ·  lab_alpha × dcis_imaging", font=F_HEAD, fill=(160, 180, 200))
        for k, c in enumerate(COLS):
            d.text((self.cell(k) - 30, SCREEN[1] + 60), c, font=F_HEAD, fill=(160, 180, 200))
        for r, (who, cells) in enumerate(ROWS):
            y = SCREEN[1] + 130 + r * 85
            d.text((SCREEN[0] + 40, y - 12), who, font=F_CELL, fill=(230, 235, 240))
            for k, ok in enumerate(cells):
                fixed = not ok and t >= FIX
                col = GREEN if (ok or fixed) else RED
                self.mark(d, self.cell(k), y, ok or fixed, col)
                if fixed and t < FIX + 0.4:
                    r2 = 20 + 60 * (t - FIX) / 0.4
                    d.ellipse((self.cell(k) - r2, y - r2, self.cell(k) + r2, y + r2), outline=GREEN, width=3)
        # the wrench cursor
        if t < FIX + 0.5:
            k = min(1.0, max(0.0, (t - MOVE[0]) / (MOVE[1] - MOVE[0])))
            k = 1 - (1 - k) ** 2
            x = 900 + (self.cell(1) + 20 - 900) * k
            y = 600 + (SCREEN[1] + 130 + 2 * 85 + 20 - 600) * k
            d.line((x, y, x + 40, y + 40), fill=(220, 220, 230), width=10)
            d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(220, 220, 230))
            d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(16, 22, 36))

    def board(self, d, t):
        d.rectangle((820, 80, 1160, 400), fill=(150, 110, 70), outline=(100, 70, 40), width=6)
        if t >= TICKET:
            k = min(1.0, (t - TICKET) / 0.3)
            y = -80 + (120 + 80) * (1 - (1 - k) ** 2)
            d.rectangle((850, y, 1130, y + 150), fill=(250, 248, 235))
            d.ellipse((985, y - 6, 997, y + 6), fill=(200, 40, 40))
            for j, line in enumerate(("Reconciled lab_alpha ×", "dcis_imaging:", "1 Slack invite.", "0 unresolved.")):
                d.text((865, y + 14 + j * 30), line, font=F_TICKET, fill=(40, 40, 50))

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.screen(d, t)
        self.board(d, t)
        hour = 8 + 57 / 60 + (3 / 60) * min(1.0, t / NINE)
        clock(d, 1235, 130, 44, hour)
        if t >= WALK[0]:
            k = min(1.0, (t - WALK[0]) / (WALK[1] - WALK[0]))
            for j, (shirt, hair) in enumerate(((TEAL, (60, 40, 30)), ((200, 120, 80), (30, 30, 30)), ((120, 120, 180), (160, 120, 60)))):
                x = 1300 + j * 110 - (330 - j * 20) * k
                bob = 4 * math.sin(t * 16 + j) if k < 1 else 0
                leg = 8 * math.sin(t * 16 + j) if k < 1 else 0
                stick_figure(d, x, FLOOR, shirt=shirt, hair=hair, bob=bob, leg=leg, arm_r=(0.9, 60), arm_l=(2.3, 60), scale=0.9)
        if t >= NINE:
            text_centered(d, FLOOR - 230, "standup. nobody looks at the screen.", F_HEAD, (200, 240, 230), x_centre=1040)
        return frame

    def audio(self, left, right):
        for k in range(12):
            c = click(0.02)
            add(left, int(k * 0.5 * SR), c, 0.18)
            add(right, int(k * 0.5 * SR), c, 0.14)
        ding = tone(1046.5, 0.5, decay=6)
        add(left, int(FIX * SR), ding, 0.6)
        add(right, int(FIX * SR), ding, 0.6)
        land = noise_burst(0.25, cutoff=2500, decay=12)
        add(left, int((TICKET + 0.3) * SR), land, 0.4)
        add(right, int((TICKET + 0.3) * SR), land, 0.4)
        murmur = noise_burst(1.6, cutoff=500, decay=0.8, attack=0.4)
        add(left, int(WALK[0] * SR), murmur, 0.25)
        add(right, int(WALK[0] * SR), murmur, 0.25)
        for k in range(8):
            c = click(0.03)
            add(left, int((WALK[0] + k * 0.12) * SR), c, 0.25)
            add(right, int((WALK[0] + k * 0.12) * SR), c, 0.25)
        ch = chime((523.3, 659.3, 784.0), spacing=0.12, length=1.6)
        add(left, int(2.7 * SR), ch, 0.7)
        add(right, int(2.7 * SR), ch, 0.7)


if __name__ == "__main__":
    CentreMillwright().main()
