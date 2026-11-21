#!/usr/bin/env python3
"""
Purpose: The docent's six-second opening. From agents/docent.md: a docent walks a visitor
         through a collection; it answers every question with a location, says Absent when the
         work does not address it, re-runs the code behind a claim before reporting a number,
         and logs each question, append-only; it never speaks for the work, it points at it.
         The gag: a gallery of the paper's parts; a visitor asks whether it adjusts for age,
         and the docent walks to Table 2 and points, Located; asks whether it works in
         children, and the docent walks to the empty frame, Absent; asks for the AUC, and the
         docent re-runs it before answering, 0.81. The visitors' log ticks up by three.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../docent_narrated.mp4.
Usage: python3 training/agents/docent/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import LAV  # noqa: E402
from lib.opening import SR, W, H, Opening, add, chime, click, font, laptop, noise_burst, stick_figure, text_centered, tone  # noqa: E402

F_FRAME = font("Verdana Bold.ttf", 18)
F_Q = font("Chalkboard.ttc", 26)
F_ANS = font("Verdana Bold.ttf", 22)
F_LOG = font("Menlo.ttc", 18)
Q1, WALK1, POINT1 = 0.3, (0.7, 1.4), 1.5
Q2, WALK2, POINT2 = 2.1, (2.4, 3.0), 3.1
Q3, RUN, NUM = 3.8, 4.0, 4.6
FRAMES = [(400, "Methods §2.3"), (640, "Table 2"), (880, "Fig. 4b"), (1120, "")]
FLOOR = 560
QUESTIONS = [(Q1, "Does it adjust for age?"), (Q2, "Does it work in children?"), (Q3, "And the AUC?")]


class Docent(Opening):
    agent = "docent"
    title = "THE DOCENT"
    tagline = "points at the work, never speaks for it"
    prompt_line = "ask the docent where the paper handles missing data"
    title_at, tagline_at, prompt_at = 3.9, 4.3, 4.9
    title_y, tagline_y = 20, 172
    footer = ""
    title_colours = ((8, (40, 20, 80, 255)), (4, (178, 150, 235, 255)), (0, (245, 240, 255, 255)))
    tagline_colour, tagline_shadow = (225, 210, 255), (30, 15, 60)
    tagline_font = font("Arial Black.ttf", 30)
    fireworks_schedule = []          # a gallery; a laser pointer instead
    seed = 19

    def background(self, t):
        img = Image.new("RGB", (W, H), (236, 232, 224))
        d = ImageDraw.Draw(img)
        d.rectangle((0, FLOOR, W, H), fill=(150, 130, 110))
        for x in range(0, W, 90):
            d.line((x, FLOOR, x, H), fill=(130, 112, 95), width=2)
        for x, label in FRAMES:
            d.rectangle((x - 90, 200, x + 90, 340), fill=(250, 250, 246), outline=(90, 70, 50) if label else (170, 170, 170), width=8)
            if label:
                for j in range(4):
                    d.line((x - 60, 230 + j * 25, x + 60 - (j * 17 % 40), 230 + j * 25), fill=(120, 120, 130), width=3)
                d.text((x - 80, 352), label, font=F_FRAME, fill=(60, 50, 40))
            else:
                text_centered(d, 260, "?", font("Impact.ttf", 48), (200, 200, 200), x_centre=x)
        return img

    def docent_x(self, t):
        if t < WALK1[0]:
            return 480
        if t < WALK1[1]:
            return 480 + (640 - 480) * (t - WALK1[0]) / (WALK1[1] - WALK1[0])
        if t < WALK2[0]:
            return 640
        if t < WALK2[1]:
            return 640 + (1120 - 640) * (t - WALK2[0]) / (WALK2[1] - WALK2[0])
        if t < RUN:
            return 1120
        return 1120 - 60 * min(1.0, (t - RUN) / 0.2)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        walking = WALK1[0] <= t < WALK1[1] or WALK2[0] <= t < WALK2[1]
        # the visitor, and the question
        stick_figure(d, 150, FLOOR, shirt=(70, 90, 140), hair=(40, 30, 20), arm_r=(0.6, 60), arm_l=(2.5, 60), scale=0.85)
        for when, q in QUESTIONS:
            nxt = [w for w, _ in QUESTIONS if w > when]
            if when <= t < (nxt[0] if nxt else 9):
                box = (60, 40, 60 + d.textlength(q, font=F_Q) + 40, 96)
                d.rounded_rectangle(box, radius=14, fill=(255, 255, 250), outline=(120, 110, 100), width=3)
                d.polygon([(140, 96), (160, 120), (180, 96)], fill=(255, 255, 250))
                d.text((80, 52), q, font=F_Q, fill=(50, 40, 30))
        # the docent, blazer the movie's colour, pointer in hand
        x = self.docent_x(t)
        bob = 4 * math.sin(t * 18) if walking else 0
        leg = 8 * math.sin(t * 18) if walking else 0
        pointing = POINT1 <= t < Q2 or POINT2 <= t < Q3
        arm = (-1.9, 90) if pointing else (0.4, 60)
        sh_l, sh_r = stick_figure(d, x, FLOOR, shirt=LAV, hair=(110, 80, 60), bob=bob, leg=leg, arm_r=arm, arm_l=(2.6, 60), scale=0.85)
        if pointing:
            hx, hy = sh_r[0] + 76 * math.cos(arm[0]), sh_r[1] + 76 * math.sin(arm[0])
            fx = 640 if t < Q2 else 1120
            d.line((hx, hy, fx, 270), fill=(255, 40, 40), width=2)
            d.ellipse((fx - 6, 264, fx + 6, 276), fill=(255, 40, 40))
            label, col = ("Located: Table 2, row \"age\"", (40, 120, 70)) if t < Q2 else ("Absent: the work does not address it", (110, 100, 100))
            d.text((40, 572), label, font=F_ANS, fill=col)
        # the terminal on its pedestal, for the number
        d.rectangle((940, 470, 1060, FLOOR), fill=(120, 110, 100))
        box = laptop(d, 1000, 470, w=200, h=120)
        if t >= RUN:
            d.text((box[0] + 8, box[1] + 6), "$ python exp/3_model/run_all.py", font=font("Menlo.ttc", 12), fill=(200, 230, 200))
            if t < NUM:
                d.text((box[0] + 8, box[1] + 26), "re-running" + "." * (int(t * 6) % 4), font=font("Menlo.ttc", 12), fill=(200, 200, 200))
            else:
                d.text((box[0] + 8, box[1] + 26), "AUC 0.81", font=font("Menlo.ttc", 22), fill=(255, 255, 255))
                d.text((40, 572), "AUC 0.81, re-run just now from exp/3_model", font=F_ANS, fill=(40, 120, 70))
        # the visitors' log, append-only
        n = sum(1 for w in (POINT1, POINT2, NUM) if t >= w)
        d.text((40, 688), f"queries/visitor/2026-11-21.md   +{n}", font=F_LOG, fill=(240, 235, 225))
        return frame

    def audio(self, left, right):
        for a, b in (WALK1, WALK2):
            s = a
            while s < b:
                c = click(0.03)
                add(left, int(s * SR), c, 0.3)
                add(right, int(s * SR), c, 0.25)
                s += 0.14
        for p in (POINT1, POINT2):
            c = click(0.05)
            add(left, int(p * SR), c, 0.8)
            add(right, int(p * SR), c, 0.8)
        yes = tone(880, 0.5, decay=6)
        add(left, int((POINT1 + 0.05) * SR), yes, 0.5)
        add(right, int((POINT1 + 0.05) * SR), yes, 0.5)
        for k, f in enumerate((233.1, 196.0)):
            no = tone(f, 0.5, decay=4, harmonics=(1.0, 0.5))
            add(left, int((POINT2 + 0.05 + k * 0.25) * SR), no, 0.5)
            add(right, int((POINT2 + 0.05 + k * 0.25) * SR), no, 0.5)
        for k in range(10):
            c = click(0.02)
            add(left, int((RUN + k * 0.05) * SR), c, 0.25)
            add(right, int((RUN + k * 0.05) * SR), c, 0.2)
        fan = noise_burst(0.5, cutoff=1200, decay=3, attack=0.1)
        add(left, int((RUN + 0.2) * SR), fan, 0.15)
        add(right, int((RUN + 0.2) * SR), fan, 0.15)
        ding = tone(1318.5, 0.5, decay=6)
        add(left, int(NUM * SR), ding, 0.6)
        add(right, int(NUM * SR), ding, 0.6)
        ch = chime((659.3, 784.0, 987.8), spacing=0.12, length=1.6)
        add(left, int(3.4 * SR), ch, 0.7)
        add(right, int(3.4 * SR), ch, 0.7)


if __name__ == "__main__":
    Docent().main()
