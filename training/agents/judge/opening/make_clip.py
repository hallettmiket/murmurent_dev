#!/usr/bin/env python3
"""
Purpose: The judge's six-second opening. From agents/judge.md, "Your personality": even-handed
         and exact; not a peacemaker; does not manufacture a consensus the evidence does not
         support; would rather say Split honestly than Presented dishonestly; shows its work.
         The gag: three contributions wave their placards, two for gene A, one for gene B, and
         the fireworks for A are already going up; three gavel blows end the party; the bench
         reads SPLIT, two say A, one says B, no shared metric; and the work is shown on the
         wall, who found what.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../judge_narrated.mp4.
Usage: python3 training/agents/judge/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import SAND  # noqa: E402
from lib.opening import SR, W, H, Opening, add, chime, clink, font, noise_burst, stick_figure, text_centered, tone  # noqa: E402

F_PLACARD = font("Arial Black.ttf", 26)
F_SPLIT = font("Impact.ttf", 96)
F_LINE = font("Verdana Bold.ttf", 20)
F_PAPER = font("Menlo.ttc", 18)
GAVEL = [1.6, 1.95, 2.3]
VERDICT = 2.6
TABLE = 3.3
FLOOR = 700
BENCH = (380, 330, 1100, 640)
SHOUTERS = [(150, "GENE A", (90, 120, 200)), (420, "GENE B", (200, 110, 80)), (1080, "GENE A", (90, 160, 110))]


class Judge(Opening):
    agent = "judge"
    title = "THE JUDGE"
    tagline = "shows the split, never fakes a consensus"
    prompt_line = "ask the judge to combine the three labs' candidate lists"
    title_at, tagline_at, prompt_at = 3.6, 4.1, 4.8
    title_colours = ((8, (70, 50, 20, 255)), (4, (214, 190, 140, 255)), (0, (255, 250, 235, 255)))
    tagline_colour, tagline_shadow = (245, 230, 200), (50, 35, 10)
    footer_colour = (245, 230, 200)
    fireworks_schedule = [(0.3, 300, 200, 0, 0.9, "peony"), (0.7, 520, 170, 5, 1.0, "peony"),
                          (1.1, 380, 150, 1, 1.1, "ring"), (1.45, 600, 190, 0, 0.9, "peony")]
    fireworks_gain = 0.7
    shakes = [(g, 0.9) for g in GAVEL]
    seed = 14

    def __init__(self):
        super().__init__()
        self.fireworks.kill(GAVEL[0] + 0.05, fade=0.3)      # the first blow ends the party

    def background(self, t):
        img = Image.new("RGB", (W, H), (58, 38, 26))
        d = ImageDraw.Draw(img)
        for x in range(0, W, 128):
            d.rectangle((x + 8, 20, x + 120, 300), fill=(84, 58, 38))
        d.rectangle((0, FLOOR, W, H), fill=(40, 28, 20))
        return img

    def bench(self, d, t):
        d.rectangle(BENCH, fill=(110, 76, 48))
        d.rectangle((BENCH[0], BENCH[1], BENCH[2], BENCH[1] + 24), fill=(140, 100, 64))
        d.rectangle((BENCH[0] + 20, BENCH[1] + 60, BENCH[2] - 20, BENCH[3] - 30), fill=(96, 66, 42))
        if t >= VERDICT:
            a = min(1.0, (t - VERDICT) / 0.2)
            s = 1.8 - 0.8 * a
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            text_centered(ld, 380, "SPLIT", F_SPLIT, (200, 40, 40, int(255 * a)), x_centre=740)
            if s != 1.0:
                nw, nh = int(W * s), int(H * s)
                layer = layer.resize((nw, nh)).crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))
            d._image.paste(layer, (0, 0), layer)
            text_centered(d, 500, "2 say GENE A, 1 says GENE B", F_LINE, (245, 230, 200), x_centre=740)
            text_centered(d, 530, "no shared metric: no consensus computed", F_LINE, (245, 230, 200), x_centre=740)

    def judge(self, d, t):
        swing = 0.0
        for g in GAVEL:
            if 0 <= t - g < 0.18:
                swing = 1.0
            elif -0.25 <= t - g < 0:
                swing = (t - g + 0.25) / 0.25 * -0.6
        ang = -1.3 + 1.6 * swing if swing >= 0 else -1.3 + swing
        stick_figure(d, 740, BENCH[1] + 30, shirt=(30, 30, 44), hair=(230, 230, 230), arm_r=(ang, 90), arm_l=(2.9, 70), scale=1.15)
        hx, hy = 740 + 34, BENCH[1] + 30 - 155
        gx, gy = hx + 90 * math.cos(ang), hy + 90 * math.sin(ang)
        d.line((gx, gy, gx + 30 * math.cos(ang - 1.57), gy + 30 * math.sin(ang - 1.57)), fill=(90, 60, 30), width=22)
        d.rectangle((BENCH[0] + 300, BENCH[1] - 10, BENCH[0] + 420, BENCH[1] + 6), fill=(90, 60, 30))     # the block

    def shouters(self, d, t):
        quiet = t >= GAVEL[0]
        for k, (x, txt, shirt) in enumerate(SHOUTERS):
            bob = 0 if quiet else 8 * math.sin(t * 14 + k * 2)
            arm = (-1.6, 80) if not quiet else (-1.2, 60)
            stick_figure(d, x, FLOOR, shirt=shirt, hair=(40, 30, 20), bob=bob, arm_r=arm, arm_l=(2.6, 60), scale=0.8)
            px, py = x + 30, FLOOR - 165 + bob - 64
            d.rectangle((px - 70, py - 90, px + 70, py - 40), fill=(245, 240, 225), outline=(60, 40, 20), width=3)
            d.line((px, py - 40, px, py), fill=(120, 90, 60), width=6)
            text_centered(d, py - 84, txt, F_PLACARD, (60, 40, 20), x_centre=px)
            if not quiet and int(t * 6 + k) % 2 == 0:
                d.text((px + 80, py - 100), "!", font=F_SPLIT, fill=(255, 220, 120))

    def paper(self, d, t):
        if t < TABLE:
            return
        a = min(1.0, (t - TABLE) / 0.25)
        d.rectangle((40, 40, 360, 300), fill=(250, 246, 232))
        d.text((60, 52), "who found what", font=F_LINE, fill=(60, 40, 20))
        rows = [("lab alpha", "GENE A", "AUC .81"), ("lab beta", "GENE B", "p .03"), ("core", "GENE A", "AUC .79")]
        for j, row in enumerate(rows[: int(3 * a + 0.999)]):
            d.text((60, 100 + j * 50), "  ".join(row), font=F_PAPER, fill=(40, 40, 50))
        d.text((60, 258), "keys aligned; metrics differ", font=F_PAPER, fill=(120, 60, 40))

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.bench(d, t)
        self.judge(d, t)
        self.shouters(d, t)
        self.paper(d, t)
        return frame

    def audio(self, left, right):
        crowd = noise_burst(1.7, cutoff=900, decay=0.4, attack=0.2)
        add(left, 0, crowd, 0.3)
        add(right, 0, crowd, 0.3)
        for g in GAVEL:
            hit = clink(freqs=((700, 30), (1100, 40), (260, 12)), length=0.3)
            thump = tone(140, 0.25, decay=18, harmonics=(1.0, 0.4))
            add(left, int(g * SR), hit, 0.8)
            add(right, int(g * SR), hit, 0.8)
            add(left, int(g * SR), thump, 1.0)
            add(right, int(g * SR), thump, 1.0)
        low = tone(196, 0.9, decay=2.5, harmonics=(1.0, 0.5, 0.25))
        add(left, int(VERDICT * SR), low, 0.6)
        add(right, int(VERDICT * SR), low, 0.6)
        for j in range(3):
            c = noise_burst(0.05, cutoff=3000, decay=40)
            add(left, int((TABLE + 0.1 + j * 0.08) * SR), c, 0.3)
            add(right, int((TABLE + 0.1 + j * 0.08) * SR), c, 0.3)
        ch = chime((392.0, 493.9, 587.3), spacing=0.14, length=1.6)
        add(left, int(3.6 * SR), ch, 0.7)
        add(right, int(3.6 * SR), ch, 0.7)


if __name__ == "__main__":
    Judge().main()
