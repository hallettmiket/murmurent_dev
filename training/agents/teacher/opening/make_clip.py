#!/usr/bin/env python3
"""
Purpose: The teacher's six-second opening. From agents/teacher.md, "Your personality": allergic
         to jargon, including its own; borrowed words arrive feeling like precision when they
         are only inheritance; "What does that even mean?" is the result of an explanation, not
         an interruption to it; never mistake fluency for understanding. The gag: a blackboard
         fills with a smooth, impressive sentence; the teacher walks in, asks what it even
         means, wipes the whole board in one swipe, and draws a ball rolling down a hill:
         "it rolls downhill."
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../teacher_narrated.mp4.
Usage: python3 training/agents/teacher/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import AMBER  # noqa: E402
from lib.opening import SR, W, H, Opening, add, chime, click, font, hum, noise_burst, stick_figure, text_centered  # noqa: E402

F_JARGON = font("Times New Roman.ttf", 44)
F_CHALK = font("Chalkboard.ttc", 52)
F_BUBBLE = font("Chalkboard.ttc", 30)
JARGON = ["Heteroscedasticity-aware stochastic", "variational posterior regularisation",
          "via amortised inference over the", "latent manifold's intrinsic geometry."]
LINES = [0.15, 0.55, 0.95, 1.35]        # each line writes itself over 0.4 s
ENTER = (1.5, 2.0)                      # the teacher walks in from the right
WHAT = 2.0                              # "What does that even mean?"
WIPE = (2.5, 3.1)                       # one swipe, left to right
DRAW = (3.2, 4.6)                       # the hill, and the ball rolling down it
WORDS = 3.9
BOARD = (60, 60, 1220, 560)
FLOOR = 660


class Teacher(Opening):
    agent = "teacher"
    title = "THE TEACHER"
    tagline = "plain words, or it was never understood"
    prompt_line = "teacher debrief"
    title_at, tagline_at, prompt_at = 3.3, 4.0, 4.7
    title_y, tagline_y = 20, 186
    title_colours = ((8, (90, 40, 0, 255)), (4, (244, 162, 97, 255)), (0, (255, 245, 225, 255)))
    tagline_colour, tagline_shadow = (255, 230, 190), (60, 30, 0)
    tagline_font = font("Arial Black.ttf", 30)
    fireworks_schedule = []          # chalk dust instead
    seed = 12

    def background(self, t):
        img = Image.new("RGB", (W, H), (120, 85, 50))
        d = ImageDraw.Draw(img)
        d.rectangle((0, FLOOR, W, H), fill=(80, 60, 40))
        d.rectangle(BOARD, fill=(30, 70, 55))
        d.rectangle((BOARD[0], BOARD[3], BOARD[2], BOARD[3] + 16), fill=(150, 110, 70))   # the chalk tray
        return img

    def hill(self, k):
        """The hill's profile as points, from the top left to the bottom right."""
        pts = []
        for i in range(41):
            u = i / 40
            x = 300 + 700 * u
            y = 330 + 220 * (1 - math.cos(math.pi * u)) / 2
            pts.append((x, y))
        return pts[: max(2, int(1 + 40 * k))], pts

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        chalk = (235, 235, 225)
        wiped_to = BOARD[0]
        if t >= WIPE[0]:
            wiped_to = BOARD[0] + (BOARD[2] - BOARD[0]) * min(1.0, (t - WIPE[0]) / (WIPE[1] - WIPE[0]))
        for k, line in enumerate(JARGON):
            n = int(len(line) * min(1.0, max(0.0, (t - LINES[k]) / 0.4)))
            d.text((120, 110 + k * 80), line[:n], font=F_JARGON, fill=chalk)
        if t >= WIPE[0]:
            d.rectangle((BOARD[0], BOARD[1], wiped_to, BOARD[3]), fill=(32, 74, 58))
            if t < WIPE[1]:
                ex = wiped_to
                d.rounded_rectangle((ex - 30, 200, ex + 30, 400), radius=8, fill=(60, 60, 70))
                rs = random.Random(int(t * 60))
                for _ in range(40):
                    px, py = ex + rs.randint(-70, 30), rs.randint(180, 430)
                    d.ellipse((px, py, px + 3, py + 3), fill=(220, 220, 215))
        if t >= DRAW[0]:
            k = min(1.0, (t - DRAW[0]) / (DRAW[1] - DRAW[0]))
            drawn, full = self.hill(k)
            d.line(drawn, fill=chalk, width=5)
            d.line((300, 550, 1000, 550), fill=chalk, width=4)
            if k > 0.25:                        # the ball rolls once the slope is there
                kb = min(1.0, (k - 0.25) / 0.7)
                i = int(kb ** 1.7 * 40)
                bx, by = full[min(i, 40)]
                d.ellipse((bx - 18, by - 36, bx + 18, by), outline=chalk, width=4)
                d.line((bx, by - 18, bx + 14 * math.cos(kb * 20), by - 18 + 14 * math.sin(kb * 20)), fill=chalk, width=3)
        if t >= WORDS:
            a = min(1.0, (t - WORDS) / 0.3)
            text_centered(d, 245, "it rolls downhill.", F_CHALK, (int(235 * a), int(235 * a), int(225 * a)), x_centre=760)
        # the teacher, from the right, chalk in hand
        if t >= ENTER[0]:
            k = min(1.0, (t - ENTER[0]) / (ENTER[1] - ENTER[0]))
            x = 1340 - 260 * k
            bob = 4 * math.sin(t * 18) if k < 1 else 0
            leg = 8 * math.sin(t * 18) if k < 1 else 0
            arm = (-2.3, 90) if WIPE[0] <= t < WIPE[1] or DRAW[0] <= t else (-0.9, 70)
            stick_figure(d, x, FLOOR, shirt=AMBER, hair=(90, 70, 60), bob=bob, leg=leg, arm_r=arm, arm_l=(2.5, 60))
        if WHAT <= t < WIPE[0] + 0.2:
            box = (700, 440, 1210, 500)
            d.rounded_rectangle(box, radius=16, fill=(255, 250, 235))
            d.polygon([(1150, 500), (1180, 530), (1120, 500)], fill=(255, 250, 235))
            text_centered(d, 452, "What does that even mean?", F_BUBBLE, (60, 40, 20), x_centre=955)
        return frame

    def audio(self, left, right):
        rs = random.Random(6)
        for k, line in enumerate(JARGON):
            for j in range(0, len(line), 2):
                s = LINES[k] + 0.4 * j / len(line)
                sq = noise_burst(0.03, cutoff=5000, decay=60)
                add(left, int(s * SR), sq, 0.12 * rs.uniform(0.5, 1))
                add(right, int(s * SR), sq, 0.1)
        for k in range(4):
            c = click(0.03)
            add(left, int((ENTER[0] + k * 0.12) * SR), c, 0.3)
            add(right, int((ENTER[0] + k * 0.12) * SR), c, 0.25)
        swipe = noise_burst(0.6, cutoff=1500, decay=4, attack=0.1)
        add(left, int(WIPE[0] * SR), swipe, 0.6)
        add(right, int(WIPE[0] * SR), swipe, 0.6)
        roll = hum(1.0, freq=70, gain=0.6)
        add(left, int((DRAW[0] + 0.4) * SR), roll, 0.5)
        add(right, int((DRAW[0] + 0.4) * SR), roll, 0.5)
        ch = chime((523.3, 659.3, 784.0), spacing=0.12, length=1.6)
        add(left, int(WORDS * SR), ch, 0.8)
        add(right, int(WORDS * SR), ch, 0.8)
        c = click()
        add(left, int(4.7 * SR), c, 0.3)
        add(right, int(4.7 * SR), c, 0.3)


if __name__ == "__main__":
    Teacher().main()
