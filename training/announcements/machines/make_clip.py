#!/usr/bin/env python3
"""
Purpose: A six-second announcement for `murmurent machines` and the /murmurent-machines
         skill, for the project's Slack channel. The gag: the millwright stands at a bench
         with a handheld scanner and sweeps its laser over three machines in turn, a laptop,
         the lab's server rack and a two-node cluster; each one lights up with its reading
         (cores busy, GPUs busy, space), and the laptop on the bench prints the one table.
         Title "MACHINES", tagline, and the skill to type: /murmurent-machines.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py (the openings engine, PR #321).
Output: opening.mp4 beside this file (1280x720, 30 fps, stereo, six seconds).
Usage: python3 training/announcements/machines/make_clip.py [--stills]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.draw import TEAL  # noqa: E402
from lib.opening import (F_MONO, F_TAG, H, SR, W, Opening, add, click, font, hum, laptop,  # noqa: E402
                         noise_burst, tone)

F_READ = font("Menlo.ttc", 22)
F_LABEL = font("Verdana Bold.ttf", 20)
F_NODE = font("Verdana Bold.ttf", 12)
F_TABLE = font("Menlo.ttc", 15)
FLOOR = 600
SCANS = [(0.5, 1.5), (1.5, 2.5), (2.5, 3.5)]        # the laser rests on each machine in turn
PRINT = 3.6                                         # the table prints on the bench laptop
LASER = (255, 40, 60)

# the three machines, left to right: where the beam lands and what each one says
MACHINES = [
    {"name": "laptop", "x": 300, "y": 300, "lines": ("3 of 12 cores", "643 GB of 1.8 TB")},
    {"name": "biodatsci", "x": 600, "y": 300, "lines": ("91 of 224 cores", "5 of 8 GPUs", "238 of 324 TB")},
    {"name": "dusky", "x": 890, "y": 320, "lines": ("26 of 512 cores", "3 of 8 GPUs", "scratch 84%")},
]


class Machines(Opening):
    agent = "machines"
    title = "MACHINES"
    tagline = "every machine you can reach: load and space, one table"
    tagline_font = font("Arial Black.ttf", 36)
    prompt_line = "a skill. Type:  /murmurent-machines"
    footer = "it prints the table as it is · new today"
    title_at, tagline_at, prompt_at, footer_at = 3.9, 4.3, 4.9, 5.3
    title_colours = ((8, (10, 50, 45, 255)), (4, (52, 190, 170, 255)), (0, (235, 250, 245, 255)))
    tagline_colour, tagline_shadow = (200, 240, 230), (10, 40, 36)
    footer_colour = (200, 240, 230)
    fireworks_schedule = []
    shakes = []

    # ---- helpers
    def scanning(self, t):
        """Which machine the beam is on (0, 1, 2), else None."""
        for k, (a, b) in enumerate(SCANS):
            if a <= t < b:
                return k
        return None

    def lit(self, k, t):
        return t >= SCANS[k][0] + 0.45

    def background(self, t):
        img = Image.new("RGB", (W, H), (30, 36, 48))
        d = ImageDraw.Draw(img)
        for y in range(0, FLOOR, 40):
            d.line((0, y, W, y), fill=(36, 42, 56), width=1)
        d.rectangle((0, FLOOR, W, H), fill=(54, 58, 66))
        for x in range(0, W, 60):
            d.line((x, FLOOR, x, H), fill=(48, 52, 60), width=1)
        # a shelf the three machines stand on
        d.rectangle((180, 420, 1060, 436), fill=(90, 70, 50))
        for x in (200, 640, 1040):
            d.rectangle((x - 8, 436, x + 8, FLOOR), fill=(70, 55, 40))
        return img

    def machine_laptop(self, d, m, t):
        x, y = m["x"], 420
        box = laptop(d, x, y, w=200, h=120, screen=(14, 18, 28))
        if self.lit(0, t):
            d.rectangle(box, fill=(20, 60, 50))
            d.text((box[0] + 10, box[1] + 10), "load 3.1", font=F_MONO, fill=(170, 230, 210))
        d.text((x - 36, 445), "laptop", font=F_LABEL, fill=(200, 200, 210))

    def machine_rack(self, d, m, t):
        x = m["x"]
        x0, y0, x1, y1 = x - 80, 200, x + 80, 420
        d.rectangle((x0, y0, x1, y1), fill=(40, 42, 50), outline=(90, 92, 100), width=6)
        for k in range(5):
            y = y0 + 14 + k * 40
            d.rectangle((x0 + 12, y, x1 - 12, y + 30), fill=(60, 62, 72))
            for j in range(5):
                d.rectangle((x0 + 24 + j * 22, y + 18, x0 + 38 + j * 22, y + 24), fill=(30, 30, 36))
            busy = self.lit(1, t) and k < 3
            col = (60, 220, 120) if self.lit(1, t) else (80, 80, 90)
            if busy and int(t * 6) % 2 == 0:
                col = (255, 200, 60)
            d.ellipse((x1 - 32, y + 8, x1 - 20, y + 20), fill=col)
            if self.lit(1, t):
                a = t * 25 + k
                for s in range(3):
                    d.line((x0 + 130, y + 14, x0 + 130 + 6 * math.cos(a + s * 2.1), y + 14 + 6 * math.sin(a + s * 2.1)),
                           fill=(150, 150, 160), width=2)
        d.text((x - 50, 445), "biodatsci", font=F_LABEL, fill=(200, 200, 210))

    def machine_cluster(self, d, m, t):
        x = m["x"]
        for n, dx in enumerate((-70, 10)):
            x0, y0, x1, y1 = x + dx, 260, x + dx + 60, 420
            d.rectangle((x0, y0, x1, y1), fill=(40, 42, 50), outline=(90, 92, 100), width=4)
            for k in range(4):
                y = y0 + 12 + k * 36
                d.rectangle((x0 + 8, y, x1 - 8, y + 24), fill=(60, 62, 72))
                # four GPUs a node, three of eight busy
                busy = self.lit(2, t) and (n == 0 and k < 2 or n == 1 and k < 1)
                col = (255, 200, 60) if busy else ((60, 220, 120) if self.lit(2, t) else (80, 80, 90))
                d.ellipse((x1 - 20, y + 6, x1 - 10, y + 16), fill=col)
            d.text((x0 + 8, y1 - 18), f"dus9{7 + n}", font=F_NODE, fill=(160, 170, 190))
        d.text((x - 60, 445), "dusky (cluster)", font=F_LABEL, fill=(200, 200, 210))

    def readout(self, d, m, k, t):
        # the readouts go once the title arrives; the bench laptop carries the numbers from there
        if not self.lit(k, t) or t >= self.title_at:
            return
        a = min(1.0, (t - SCANS[k][0] - 0.45) / 0.25)
        x, y = m["x"], 150 - 20 * (1 - a)
        lines = m["lines"]
        w = 220
        h = 14 + 30 * len(lines)
        d.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), radius=10,
                            fill=(16, 52, 46), outline=(52, 190, 170), width=3)
        for j, line in enumerate(lines):
            bb = d.textbbox((0, 0), line, font=F_READ)
            d.text((x - (bb[2] - bb[0]) / 2, y - h / 2 + 8 + j * 30), line, font=F_READ, fill=(170, 240, 215))

    def wright(self, d, t):
        """Hi-vis vest over the teal shirt, tool belt, cap; at the bench on the left, holding
        the scanner out towards the machines."""
        x, y = 110, FLOOR
        skin, shirt, vest = (215, 175, 140), TEAL, (250, 220, 40)
        d.line((x - 10, y - 80, x - 18, y), fill=(50, 56, 70), width=16)
        d.line((x + 10, y - 80, x + 18, y), fill=(50, 56, 70), width=16)
        d.rectangle((x - 32, y - 6, x - 6, y + 4), fill=(50, 35, 20))
        d.rectangle((x + 6, y - 6, x + 32, y + 4), fill=(50, 35, 20))
        d.rounded_rectangle((x - 36, y - 170, x + 36, y - 70), radius=14, fill=shirt)
        d.rounded_rectangle((x - 30, y - 165, x + 30, y - 90), radius=8, fill=vest)
        d.line((x - 30, y - 130, x + 30, y - 130), fill=(200, 200, 210), width=6)
        d.rectangle((x - 40, y - 96, x + 40, y - 80), fill=(90, 60, 30))
        for k in range(-1, 2):
            d.rectangle((x + k * 24 - 6, y - 110, x + k * 24 + 6, y - 92), fill=(130, 130, 140))
        d.ellipse((x - 26, y - 226, x + 26, y - 170), fill=skin)
        d.ellipse((x - 14, y - 206, x - 8, y - 200), fill=(20, 20, 20))
        d.ellipse((x + 8, y - 206, x + 14, y - 200), fill=(20, 20, 20))
        d.line((x - 8, y - 186, x + 8, y - 186), fill=(120, 80, 70), width=3)
        d.chord((x - 28, y - 236, x + 28, y - 196), 180, 360, fill=(40, 60, 90))
        d.rectangle((x - 2, y - 218, x + 46, y - 210), fill=(40, 60, 90))
        # the left arm rests; the right one holds the scanner, raised a little per machine
        d.line((x - 34, y - 150, x - 46, y - 96), fill=shirt, width=14)
        d.ellipse((x - 55, y - 105, x - 37, y - 87), fill=skin)
        k = self.scanning(t)
        aim = (k if k is not None else (2 if t >= SCANS[-1][1] else 0))
        ex, ey = x + 70, y - 150 - 8 * aim
        d.line((x + 34, y - 150, ex, ey), fill=shirt, width=14)
        d.ellipse((ex - 9, ey - 9, ex + 9, ey + 9), fill=skin)
        # the scanner: a small grey gun with a red eye
        d.rounded_rectangle((ex - 4, ey - 16, ex + 44, ey + 2), radius=5, fill=(90, 92, 100), outline=(140, 140, 150), width=2)
        d.rectangle((ex + 4, ey + 2, ex + 16, ey + 18), fill=(70, 72, 80))
        d.ellipse((ex + 36, ey - 12, ex + 46, ey - 2), fill=LASER if k is not None else (120, 40, 50))
        return ex + 44, ey - 7

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.machine_laptop(d, MACHINES[0], t)
        self.machine_rack(d, MACHINES[1], t)
        self.machine_cluster(d, MACHINES[2], t)
        gun = self.wright(d, t)
        k = self.scanning(t)
        if k is not None:
            a, b = SCANS[k]
            m = MACHINES[k]
            # the beam sweeps up and down the machine while it rests there
            sweep = math.sin((t - a) / (b - a) * math.pi * 4)
            tx, ty = m["x"] + 10 * sweep, m["y"] + 70 * sweep
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.line((gun[0], gun[1], tx, ty), fill=(255, 60, 80, 90), width=9)
            gd.line((gun[0], gun[1], tx, ty), fill=(255, 120, 130, 220), width=3)
            gd.ellipse((tx - 8, ty - 8, tx + 8, ty + 8), fill=(255, 200, 200, 230))
            frame.paste(glow, (0, 0), glow)
            d = ImageDraw.Draw(frame)
        for j, m in enumerate(MACHINES):
            self.readout(d, m, j, t)
        return frame

    def overlay(self, frame, t, dt):
        # the bench laptop, bottom left, prints the table once every machine has answered
        d = ImageDraw.Draw(frame)
        box = laptop(d, 1130, 592, w=260, h=140, screen=(14, 18, 28))
        x0, y0, x1, y1 = box
        d.text((x0 + 8, y0 + 6), "$ murmurent machines load", font=F_TABLE, fill=(170, 230, 210))
        if t >= PRINT:
            rows = ("laptop      3 of 12    none", "biodatsci  91 of 224   5 of 8", "dusky      26 of 512   3 of 8")
            n = int((t - PRINT) / 0.5 * 90)
            shown = 0
            for j, row in enumerate(rows):
                take = max(0, min(len(row), n - shown))
                shown += len(row)
                d.text((x0 + 8, y0 + 30 + j * 22), row[:take], font=F_TABLE, fill=(60, 220, 120))
        return frame

    def audio(self, left, right):
        rs = random.Random(3)
        # the scanner: a thin whine while the beam is on, and a confirming beep when it lands
        for k, (a, b) in enumerate(SCANS):
            n = int(SR * (b - a - 0.1))
            tt = np.arange(n) / SR
            whine = np.sin(2 * math.pi * (2400 + 300 * np.sin(tt * 8)) * tt) * np.sin(math.pi * tt / (b - a)) ** 0.5 * 0.08
            pan = 0.35 + 0.3 * k
            add(left, int(a * SR), whine, 1 - pan)
            add(right, int(a * SR), whine, pan)
            beep = tone(1046.5 * 2 ** (k * 2 / 12), 0.16, decay=14, harmonics=(1.0, 0.2), attack=0.003)
            add(left, int((a + 0.45) * SR), beep, 0.5 * (1 - pan) + 0.2)
            add(right, int((a + 0.45) * SR), beep, 0.5 * pan + 0.2)
        # the rack's fans, once lit; the cluster's a little higher
        add(left, int((SCANS[1][0] + 0.45) * SR), hum(6 - SCANS[1][0], 110.0, 0.08), 1.0)
        add(right, int((SCANS[1][0] + 0.45) * SR), hum(6 - SCANS[1][0], 110.0, 0.08), 1.0)
        add(right, int((SCANS[2][0] + 0.45) * SR), hum(6 - SCANS[2][0], 150.0, 0.06), 1.0)
        # the table prints: a short key clatter
        for k in range(40):
            key = click(0.02)
            add(left, int((PRINT + k * 0.03) * SR), key, 0.2 * rs.uniform(0.7, 1.0))
            add(right, int((PRINT + k * 0.03) * SR), key, 0.3 * rs.uniform(0.7, 1.0))
        # a plain two-note figure under the title, the millwright's own
        for off, f in ((0.0, 392.0), (0.25, 523.3)):
            add(left, int((3.9 + off) * SR), tone(f, 1.2, decay=2.5, harmonics=(1.0, 0.3)), 0.3)
            add(right, int((3.9 + off) * SR), tone(f, 1.2, decay=2.5, harmonics=(1.0, 0.3)), 0.3)
        # a soft swish as the prompt box arrives
        sw = noise_burst(0.25, cutoff=2500, decay=14)
        add(left, int(4.9 * SR), sw, 0.3)
        add(right, int(4.9 * SR), sw, 0.3)


if __name__ == "__main__":
    Machines().main()
