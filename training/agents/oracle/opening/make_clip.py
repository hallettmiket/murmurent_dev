#!/usr/bin/env python3
"""
Purpose: The oracle's six-second opening. From agents/oracle.md: the personal memory of one
         member, living in their own vault, remembering genes, findings, hypotheses and the
         context of every experiment, browsable as a graph of linked notes. The gag: a member
         is still typing "what was that gene we flagged back in Mar" when the notes light up
         one by one along the path through the vault, and the oracle, hooded on its tripod,
         answers before the question is finished: MMP11, run 17, 14 March, and you wrote
         "never again".
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../oracle_narrated.mp4.
Usage: python3 training/agents/oracle/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.opening import SR, W, H, Opening, add, chime, click, font, glissando, hum, laptop, stick_figure, text_centered, tone  # noqa: E402

F_HAND = font("Chalkboard.ttc", 26)
F_NOTE = font("Verdana Bold.ttf", 16)
QUESTION = "what was that gene we flagged back in Mar"
TYPE_FROM, TYPE_TO = 0.3, 2.3                   # the question is still being typed...
LIGHT = [0.9, 1.15, 1.4, 1.6, 1.8, 1.95]        # ...while the notes light up along the path
ANSWER = 2.0                                    # and the answer lands before the question ends
FLOOR = 600


class Oracle(Opening):
    agent = "oracle"
    title = "THE ORACLE"
    tagline = "remembers what you forgot you knew"
    prompt_line = "ask the oracle what we decided about chrM in March"
    title_at, tagline_at, prompt_at = 2.8, 3.5, 4.5
    title_colours = ((8, (40, 20, 80, 255)), (4, (178, 150, 235, 255)), (0, (245, 240, 255, 255)))
    tagline_colour, tagline_shadow = (225, 210, 255), (30, 15, 60)
    footer_colour = (225, 210, 255)
    fireworks_schedule = []          # the notes light up instead
    seed = 5

    def setup(self):
        rs = random.Random(21)
        self.nodes = [(rs.randint(700, 1230), rs.randint(60, 520)) for _ in range(26)]
        self.path = [3, 11, 7, 18, 22, 14]      # the path the memory travels, six notes to the answer
        for i, xy in zip(self.path, ((740, 520), (860, 460), (980, 420), (1060, 320), (1130, 220), (1170, 120))):
            self.nodes[i] = xy                  # set places, so the labels never sit on each other
        self.edges = []
        for i, (x, y) in enumerate(self.nodes):
            near = sorted(range(len(self.nodes)), key=lambda j: (self.nodes[j][0] - x) ** 2 + (self.nodes[j][1] - y) ** 2)[1:4]
            self.edges += [(i, j) for j in near]
        self.edges += list(zip(self.path, self.path[1:]))
        self.labels = {3: "chrM artefact", 11: "run 17", 7: "p13 vs p14", 18: "QC drift", 22: "never again", 14: "MMP11"}

    def background(self, t):
        img = Image.new("RGB", (W, H), (16, 10, 32))
        d = ImageDraw.Draw(img)
        for k in range(8):           # the cave, lit from below
            d.ellipse((400 - k * 60, 420 - k * 20, 1300 + k * 60, 900 + k * 20), fill=(16 + 3 * k, 10 + 2 * k, 32 + 6 * k))
        d.rectangle((0, FLOOR, W, H), fill=(28, 20, 48))
        return img

    def lit(self, i, t):
        if i not in self.path:
            return 0.0
        k = self.path.index(i)
        return 0.0 if t < LIGHT[k] else min(1.0, (t - LIGHT[k]) / 0.15)

    def graph(self, frame, t):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for a, b in self.edges:
            on = min(self.lit(a, t), self.lit(b, t))
            d.line((*self.nodes[a], *self.nodes[b]), fill=(178, 150, 235, int(40 + 180 * on)), width=2 if on else 1)
        for i, (x, y) in enumerate(self.nodes):
            on = self.lit(i, t)
            r = 5 + 9 * on
            col = (200 + int(55 * on), 180 + int(60 * on), 255, 255) if on else (120, 100, 170, 255)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
            if on and i in self.labels:
                d.text((x + 14, y - 12), self.labels[i], font=F_NOTE, fill=(240, 232, 255, int(255 * on)))
        glow = layer.filter(ImageFilter.GaussianBlur(8))
        frame.paste(glow, (0, 0), glow)
        frame.paste(layer, (0, 0), layer)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        # the member at the laptop, still typing
        stick_figure(d, 170, FLOOR, shirt=(70, 90, 140), hair=(60, 40, 30), arm_r=(0.3, 70), arm_l=(2.8, 70))
        box = laptop(d, 330, FLOOR, w=240, h=150)
        n = int(len(QUESTION) * min(1.0, max(0.0, (t - TYPE_FROM) / (TYPE_TO - TYPE_FROM))))
        typed = QUESTION[:n] + ("|" if int(t * 3) % 2 == 0 else "")
        d.rectangle(box, fill=(20, 16, 40))
        yy, line = box[1] + 10, ""
        for w in typed.split(" "):
            if d.textlength((line + " " + w).strip(), font=F_NOTE) > box[2] - box[0] - 20:
                d.text((box[0] + 10, yy), line, font=F_NOTE, fill=(220, 220, 230))
                yy, line = yy + 20, w
            else:
                line = (line + " " + w).strip()
        d.text((box[0] + 10, yy), line, font=F_NOTE, fill=(220, 220, 230))
        # the oracle: hooded, on a tripod stool, over the vault
        ox, oy = 560, FLOOR
        for dx in (-40, 0, 40):
            d.line((ox + dx, oy, ox, oy - 90), fill=(90, 70, 50), width=6)
        d.polygon([(ox - 70, oy - 80), (ox + 70, oy - 80), (ox + 40, oy - 250), (ox - 40, oy - 250)], fill=(60, 40, 110))
        d.ellipse((ox - 34, oy - 290, ox + 34, oy - 222), fill=(50, 32, 92))
        d.chord((ox - 40, oy - 300, ox + 40, oy - 220), 180, 360, fill=(60, 40, 110))
        pulse = 0.5 + 0.5 * math.sin(t * 6)
        for ex in (ox - 13, ox + 13):
            d.ellipse((ex - 6, oy - 262, ex + 6, oy - 254), fill=(200 + int(55 * pulse), 180, 255))
        self.graph(frame, t)
        d = ImageDraw.Draw(frame)
        if t >= ANSWER:
            a = min(1.0, (t - ANSWER) / 0.2)
            card = (30, 292 + int(20 * (1 - a)), 500, 402 + int(20 * (1 - a)))
            d.rounded_rectangle(card, radius=12, fill=(245, 240, 255), outline=(120, 90, 190), width=3)
            d.polygon([(card[2] - 1, card[1] + 30), (card[2] + 40, card[1] + 10), (card[2] - 1, card[1] + 60)], fill=(245, 240, 255))
            d.text((card[0] + 16, card[1] + 8), "MMP11. Run 17, 14 March.", font=F_HAND, fill=(50, 30, 90))
            d.text((card[0] + 16, card[1] + 42), "You wrote: \"never again\".", font=F_HAND, fill=(50, 30, 90))
            d.text((card[0] + 16, card[1] + 82), "(you had not finished asking)", font=F_NOTE, fill=(130, 110, 170))
        return frame

    def audio(self, left, right):
        h = hum(5.5, freq=55.0, gain=0.5)
        add(left, 0, h, 0.5)
        add(right, 0, h, 0.5)
        rs = random.Random(4)
        for k in range(len(QUESTION)):
            s = TYPE_FROM + (TYPE_TO - TYPE_FROM) * k / len(QUESTION)
            c = click(0.02)
            add(left, int(s * SR), c, 0.25 * rs.uniform(0.5, 1))
            add(right, int(s * SR), c, 0.2)
        for k, s in enumerate(LIGHT):
            n = tone(523.3 * (2 ** (k / 6)), 0.9, decay=4.0)
            add(left, int(s * SR), n, 0.5)
            add(right, int(s * SR), n, 0.5)
        g = glissando(440, 1760, 0.5, gain=0.3)
        add(left, int((ANSWER - 0.3) * SR), g, 0.8)
        add(right, int((ANSWER - 0.3) * SR), g, 0.8)
        ch = chime((880.0, 1108.7, 1318.5), spacing=0.1, length=1.8)
        add(left, int(2.8 * SR), ch, 0.8)
        add(right, int(2.8 * SR), ch, 0.8)


if __name__ == "__main__":
    Oracle().main()
