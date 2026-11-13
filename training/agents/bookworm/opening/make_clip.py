#!/usr/bin/env python3
"""
Purpose: The bookworm's six-second opening, the quiet one. From agents/bookworm.md,
         "Your personality": organized, kind, curious, diligent, journals every day, keeps a
         vision board, holds the other agents to high standards in a gentle way. The gag:
         the library at night, the bookworm writing in her journal under a reading lamp; the
         fireworks every other opening gets start up outside the window; she looks up, one
         finger to her lips, "shh", and they fizzle out mid-air. Then, in the quiet, a page
         turns and the title comes in with a soft chime.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../bookworm_narrated.mp4.
Usage: python3 training/agents/bookworm/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import TEAL  # noqa: E402  (the movie's own colour)
from lib.opening import SR, W, H, Opening, add, chime, click, font, noise_burst, shush, text_centered  # noqa: E402

F_SIGN = font("Verdana Bold.ttf", 20)
F_HAND = font("Chalkboard.ttc", 22)
SHH = 1.45                 # she looks up and raises a finger
PAGE = 2.3                 # the page turns
WINDOW = (860, 70, 1230, 430)      # the window the fireworks are seen through
FLOOR = 600


class Bookworm(Opening):
    agent = "bookworm"
    title = "THE BOOKWORM"
    tagline = "checks every paper against its source"
    prompt_line = "ask the bookworm for the five papers behind this method, checked"
    title_at, tagline_at, prompt_at = 2.6, 3.4, 4.4
    title_colours = ((8, (10, 50, 45, 255)), (4, (52, 190, 170, 255)), (0, (235, 250, 245, 255)))
    tagline_colour, tagline_shadow = (200, 240, 230), (10, 40, 36)
    footer_colour = (200, 240, 230)
    # the fireworks start outside the window and never get past the second burst
    fireworks_schedule = [
        (0.15, 1000, 170, 2, 0.8, "peony"), (0.5, 1120, 150, 0, 0.9, "peony"), (0.9, 960, 120, 4, 1.0, "ring"),
        (1.3, 1080, 140, 1, 1.2, "peony"), (1.6, 1000, 130, 3, 1.2, "peony"), (1.9, 1140, 150, 5, 1.0, "peony"),
    ]
    fireworks_gain = 0.55
    glow = True

    def __init__(self):
        super().__init__()
        self.fireworks.kill(SHH + 0.15, fade=0.6)
        # the fireworks show only through the window: black out the trail layer around it
        draw = self.fireworks.draw

        def through_the_window(trail, t, dt):
            draw(trail, t, dt)
            d = ImageDraw.Draw(trail)
            x0, y0, x1, y1 = WINDOW
            for box in ((0, 0, W, y0 + 5), (0, y1 - 5, W, H), (0, 0, x0 + 5, H), (x1 - 5, 0, W, H)):
                d.rectangle(box, fill=(0, 0, 0))
        self.fireworks.draw = through_the_window

    def background(self, t):
        img = Image.new("RGB", (W, H), (26, 22, 30))
        d = ImageDraw.Draw(img)
        # the night sky in the window, the fireworks are drawn over it later
        d.rectangle(WINDOW, fill=(8, 10, 34))
        rs = random.Random(2)
        for _ in range(40):
            x, y = rs.randint(WINDOW[0], WINDOW[2]), rs.randint(WINDOW[1], WINDOW[3] - 80)
            d.point((x, y), fill=(200, 200, 230))
        d.ellipse((1120, 110, 1170, 160), fill=(240, 236, 210))
        return img

    def shelves(self, d, t):
        rs = random.Random(7)
        spines = [(120, 80, 70), (60, 90, 120), (140, 110, 60), (70, 110, 80), (110, 60, 90), (150, 130, 100), (52, 120, 110)]
        for x0, x1 in ((40, 760),):
            for shelf_y in range(90, FLOOR, 110):
                x = x0
                while x < x1 - 20:
                    w = rs.randint(18, 40)
                    h = rs.randint(70, 96)
                    d.rectangle((x, shelf_y + 100 - h, x + w, shelf_y + 100), fill=rs.choice(spines))
                    d.line((x + w / 2, shelf_y + 100 - h + 10, x + w / 2, shelf_y + 90), fill=(200, 190, 150), width=1)
                    x += w + 2
                d.rectangle((x0 - 10, shelf_y + 100, x1 + 10, shelf_y + 110), fill=(80, 55, 35))
        # window frame, and the sign
        d.rectangle(WINDOW, outline=(120, 90, 60), width=10)
        d.line(((WINDOW[0] + WINDOW[2]) / 2, WINDOW[1], (WINDOW[0] + WINDOW[2]) / 2, WINDOW[3]), fill=(120, 90, 60), width=8)
        d.line((WINDOW[0], (WINDOW[1] + WINDOW[3]) / 2, WINDOW[2], (WINDOW[1] + WINDOW[3]) / 2), fill=(120, 90, 60), width=8)
        # the vision board on the wall beside the window
        d.rectangle((820, 460, 1230, 580), fill=(170, 130, 80), outline=(110, 80, 50), width=4)
        for k, (txt, col) in enumerate((("read it all", (255, 240, 200)), ("check the source", (220, 240, 255)),
                                        ("be kind", (255, 220, 230)), ("journal daily", (225, 255, 230)))):
            x = 835 + k * 100
            d.rectangle((x, 475, x + 90, 565), fill=col)
            d.ellipse((x + 41, 470, x + 49, 478), fill=(200, 40, 40))
            for j, w in enumerate(txt.split(" ")):
                d.text((x + 8, 486 + j * 24), w, font=F_HAND, fill=(40, 40, 50))
        # the "quiet please" sign swings when she shushes
        swing = 0.0
        if t >= SHH:
            swing = 0.25 * math.sin((t - SHH) * 9) * math.exp(-(t - SHH) * 1.5)
        cx, cy = 790, 40
        d.line((cx, 0, cx + 60 * math.sin(swing), cy + 60 * math.cos(swing)), fill=(160, 150, 130), width=2)
        sx, sy = cx + 60 * math.sin(swing), cy + 60 * math.cos(swing)
        d.rectangle((sx - 95, sy, sx + 95, sy + 44), fill=(245, 240, 225), outline=(90, 80, 60), width=3)
        text_centered(d, sy + 10, "QUIET PLEASE", F_SIGN, (90, 60, 40), x_centre=sx)

    def desk(self, d, t):
        d.rectangle((0, FLOOR, W, H), fill=(60, 44, 36))
        d.rectangle((300, 520, 740, 540), fill=(120, 85, 50))
        d.rectangle((320, 540, 340, FLOOR), fill=(100, 70, 40))
        d.rectangle((700, 540, 720, FLOOR), fill=(100, 70, 40))
        # the reading lamp, green glass
        d.line((690, 520, 690, 400), fill=(170, 150, 60), width=6)
        d.pieslice((620, 370, 760, 450), 180, 360, fill=(40, 120, 70))
        d.ellipse((670, 505, 710, 525), fill=(170, 150, 60))
        # the journal, open; a page lifts and turns at PAGE
        d.rounded_rectangle((430, 490, 650, 536), radius=6, fill=(235, 228, 205))
        d.line((540, 492, 540, 534), fill=(160, 150, 120), width=2)
        for yy in (500, 510, 520):
            d.line((445, yy, 525, yy), fill=(140, 130, 110), width=1)
        if PAGE <= t < PAGE + 0.5:
            k = (t - PAGE) / 0.5
            x = 540 + 100 * math.cos(math.pi * k)
            d.polygon([(540, 490), (x, 470 + 30 * abs(math.sin(math.pi * k))), (x, 536), (540, 536)], fill=(245, 240, 220))

    def her(self, d, t):
        """Seated at the desk, facing us: teal cardigan, bun, round glasses; pen in the right hand,
        the left hand comes up with one finger to the lips at SHH."""
        x, y = 520, 540
        skin, shirt = (235, 200, 170), TEAL
        d.rounded_rectangle((x - 60, y - 150, x + 60, y - 20), radius=24, fill=shirt)
        d.rounded_rectangle((x - 26, y - 150, x + 26, y - 60), radius=10, fill=(245, 245, 240))   # blouse
        # head
        look_up = 0 if t < SHH else int(6 * min(1.0, (t - SHH) / 0.2))
        hy = y - 150 - look_up
        d.ellipse((x - 34, hy - 70, x + 34, hy + 6), fill=skin)
        d.chord((x - 36, hy - 78, x + 36, hy - 30), 180, 360, fill=(90, 60, 40))
        d.ellipse((x - 16, hy - 96, x + 16, hy - 66), fill=(90, 60, 40))     # the bun
        for ex in (x - 15, x + 15):
            d.ellipse((ex - 12, hy - 44, ex + 12, hy - 20), outline=(60, 50, 50), width=3)
            d.ellipse((ex - 4, hy - 36, ex + 4, hy - 28), fill=(30, 30, 40))
        d.line((x - 3, hy - 32, x + 3, hy - 32), fill=(60, 50, 50), width=3)
        if t < SHH:
            d.arc((x - 12, hy - 20, x + 12, hy - 4), 10, 170, fill=(150, 80, 80), width=3)     # a small smile, writing
        else:
            d.ellipse((x - 5, hy - 14, x + 5, hy - 6), fill=(150, 80, 80))                   # lips pursed
        # right arm writing, pen moving
        wob = 3 * math.sin(t * 20) if t < SHH else 0
        d.line((x + 50, y - 110, x + 70 + wob, y - 44), fill=shirt, width=16)
        d.ellipse((x + 60 + wob, y - 54, x + 82 + wob, y - 34), fill=skin)
        d.line((x + 76 + wob, y - 50, x + 60 + wob, y - 14), fill=(40, 40, 60), width=4)
        # left arm: on the desk, then up with the finger
        if t < SHH:
            d.line((x - 50, y - 110, x - 90, y - 40), fill=shirt, width=16)
            d.ellipse((x - 100, y - 50, x - 78, y - 30), fill=skin)
        else:
            k = min(1.0, (t - SHH) / 0.25)
            ex, ey = x - 50 + 40 * k, y - 110 - 70 * k
            d.line((x - 50, y - 110, ex, ey), fill=shirt, width=16)
            d.ellipse((ex - 12, ey - 12, ex + 12, ey + 12), fill=skin)
            d.line((ex, ey, ex + 4, ey - 34 * k), fill=skin, width=8)          # the finger, up to the lips
            if k >= 1.0 and t < SHH + 1.2:
                a = 1 - (t - SHH - 1.0) / 0.2 if t > SHH + 1.0 else 1.0
                text_centered(d, hy - 150, "shh", font("Chalkboard.ttc", 48), (int(240 * a), int(240 * a), int(230 * a)), x_centre=x - 80)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.shelves(d, t)
        self.desk(d, t)
        self.her(d, t)
        # lamp light, warm, over everything near the desk
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((380, 380, 780, 620), fill=(255, 220, 150, 60))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        frame.paste(glow, (0, 0), glow)
        return frame

    def audio(self, left, right):
        # a quiet room: the clock-less hush, a pen scratching
        rs = random.Random(3)
        for k in range(14):
            s = 0.1 + k * 0.1
            if s > SHH:
                break
            scratch = noise_burst(0.07, cutoff=2500, decay=30)
            add(left, int(s * SR), scratch, 0.10 * rs.uniform(0.6, 1.0))
            add(right, int(s * SR), scratch, 0.08)
        sh = shush(1.0)
        add(left, int((SHH + 0.2) * SR), sh, 0.9)
        add(right, int((SHH + 0.2) * SR), sh, 0.9)
        page = noise_burst(0.45, cutoff=4000, decay=7, attack=0.08)
        add(left, int(PAGE * SR), page, 0.35)
        add(right, int(PAGE * SR), page, 0.35)
        ch = chime((659.3, 784.0, 987.8), spacing=0.14, length=2.0)
        add(left, int(2.6 * SR), ch, 0.9)
        add(right, int(2.6 * SR), ch, 0.9)
        c = click()
        add(left, int(4.4 * SR), c, 0.3)
        add(right, int(4.4 * SR), c, 0.3)


if __name__ == "__main__":
    Bookworm().main()
