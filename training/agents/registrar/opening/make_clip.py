#!/usr/bin/env python3
"""
Purpose: The registrar's six-second opening. From agents/registrar.md: labs are opaque units
         from the registrar's vantage point, it does not look inside them; it is the centre's
         certificate authority and issues signed PI identity cards; and archiving a lab flips a
         status flag, it never deletes a lab's data. The gag, in three beats: a hand lifts the
         lid of one lab to peek and a stamp slams down, OPAQUE; a PI card is signed and sealed,
         with the sparks of the seal; and a lab dragged to the bin snaps back with an
         "archived" tag, the bin still empty.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-21
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../registrar_narrated.mp4.
Usage: python3 training/agents/registrar/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.opening import SR, W, H, Opening, add, chime, click, font, glissando, noise_burst, text_centered, tone  # noqa: E402

F_BOX = font("Verdana Bold.ttf", 18)
F_STAMP = font("Impact.ttf", 64)
F_CARD = font("Verdana Bold.ttf", 17)
F_CARD_H = font("Impact.ttf", 26)
PEEK = (0.5, 1.2)
STAMP = 1.3
CARD = (1.9, 2.5)
SIGN = (2.5, 2.8)
SEAL = 2.9
DRAG = (3.6, 4.3)
TOGGLE = 4.35
BOXES = [("lab alpha", 0, 0), ("lab beta", 1, 0), ("core imaging", 2, 0), ("lab gamma", 0, 1), ("core genomics", 1, 1), ("lab delta", 2, 1)]
BIN = (1120, 540, 1220, 660)


def box_rect(col, row):
    x0, y0 = 90 + col * 230, 110 + row * 230
    return (x0, y0, x0 + 200, y0 + 180)


class Registrar(Opening):
    agent = "registrar"
    title = "THE REGISTRAR"
    tagline = "every lab on one list, none opened"
    prompt_line = "ask the registrar to add the new core to the centre's registry"
    title_at, tagline_at, prompt_at = 3.0, 3.5, 4.7
    title_colours = ((8, (20, 50, 90, 255)), (4, (110, 170, 235, 255)), (0, (235, 245, 255, 255)))
    tagline_colour, tagline_shadow = (215, 235, 255), (10, 30, 60)
    footer_colour = (215, 235, 255)
    fireworks_schedule = [(SEAL - 0.9, 1130, 330, 0, 0.45, "ring")]      # the sparks of the seal
    fireworks_gain = 0.5
    shakes = [(STAMP, 0.8), (TOGGLE, 0.3)]
    seed = 17

    def background(self, t):
        img = Image.new("RGB", (W, H), (34, 44, 64))
        d = ImageDraw.Draw(img)
        d.rectangle((60, 60, 780, 580), fill=(44, 56, 80), outline=(90, 110, 150), width=4)
        d.text((80, 70), "THE CENTRE  ·  _registry.yaml", font=F_BOX, fill=(170, 190, 220))
        return img

    def lab_box(self, d, rect, name, lift=0.0, dim=False, tag=None):
        x0, y0, x1, y1 = rect
        inner = (x0 + 12, y0 + 36, x1 - 12, y1 - 12)
        if lift > 0:
            d.rectangle(inner, fill=(255, 230, 140))          # what is inside, and not for the registrar
            for j in range(4):
                d.line((inner[0] + 20, inner[1] + 20 + j * 24, inner[2] - 20, inner[1] + 20 + j * 24), fill=(120, 100, 40), width=3)
        fill = (120, 128, 140) if dim else (190, 200, 215)
        if lift > 0:
            d.polygon([(x0, y0 + 36 - 120 * lift), (x1, y0 + 36 - 60 * lift), (x1, y1), (x0, y1)], fill=fill)
            d.polygon([(x0, y0 + 36 - 120 * lift), (x1, y0 + 36 - 60 * lift), (x1, y1 - 60 * lift), (x0, y1 - 120 * lift)], fill=fill)
        else:
            d.rectangle((x0, y0 + 36, x1, y1), fill=fill)
        d.rectangle((x0, y0, x1, y0 + 36), fill=(90, 110, 150) if not dim else (70, 76, 90))
        d.text((x0 + 10, y0 + 8), name, font=F_BOX, fill=(240, 245, 255))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 20
        if lift == 0:
            d.rounded_rectangle((cx - 16, cy - 4, cx + 16, cy + 22), radius=4, fill=(90, 90, 100))    # the padlock
            d.arc((cx - 11, cy - 24, cx + 11, cy + 4), 180, 360, fill=(90, 90, 100), width=5)
        if tag:
            d.rectangle((x0 + 20, y1 - 46, x1 - 20, y1 - 18), fill=(60, 60, 70))
            text_centered(d, y1 - 42, tag, F_BOX, (230, 230, 240), x_centre=cx)

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        lift = 0.0
        if PEEK[0] <= t < STAMP:
            lift = min(1.0, (t - PEEK[0]) / (PEEK[1] - PEEK[0])) * 0.6
        for name, col, row in BOXES:
            rect = box_rect(col, row)
            if name == "lab beta":
                self.lab_box(d, rect, name, lift=lift)
            elif name == "lab delta":
                if DRAG[0] <= t < TOGGLE:
                    k = min(1.0, (t - DRAG[0]) / (DRAG[1] - DRAG[0]))
                    dx, dy = (BIN[0] - rect[0]) * k, (BIN[1] - 80 - rect[1]) * k
                    s = 1 - 0.4 * k
                    moved = (rect[0] + dx, rect[1] + dy, rect[0] + dx + 200 * s, rect[1] + dy + 180 * s)
                    self.lab_box(d, moved, name)
                else:
                    self.lab_box(d, rect, name, dim=t >= TOGGLE, tag="status: archived" if t >= TOGGLE else None)
            else:
                self.lab_box(d, rect, name)
        # the peeking hand
        if PEEK[0] <= t < STAMP + 0.3:
            rect = box_rect(1, 0)
            k = min(1.0, (t - PEEK[0]) / (PEEK[1] - PEEK[0]))
            hx, hy = rect[0] + 30, rect[1] + 36 - 120 * lift
            if t >= STAMP:
                hx, hy = hx - 220 * (t - STAMP) / 0.3, hy + 120 * (t - STAMP) / 0.3     # it pulls back
            elif t < PEEK[0] + 0.25:
                kk = (t - PEEK[0]) / 0.25
                hx, hy = hx - 200 * (1 - kk), hy + 140 * (1 - kk)                    # it reaches in from below
            d.rounded_rectangle((hx - 16, hy, hx + 16, hy + 40), radius=10, fill=(235, 190, 150))     # the palm
            for j in range(3):
                d.line((hx - 10 + j * 10, hy + 4, hx - 14 + j * 12, hy - 22), fill=(235, 190, 150), width=8)
            d.line((hx + 14, hy + 20, hx + 28, hy + 4), fill=(235, 190, 150), width=8)
        # the stamp
        if t >= STAMP:
            a = min(1.0, (t - STAMP) / 0.12)
            s = 1.8 - 0.8 * a
            rect = box_rect(1, 0)
            cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rectangle((cx - 110, cy - 42, cx + 110, cy + 42), outline=(200, 40, 40, 230), width=6)
            text_centered(ld, cy - 40, "OPAQUE", F_STAMP, (200, 40, 40, 230), x_centre=cx)
            layer = layer.rotate(-8, center=(cx, cy))
            if s != 1.0:
                nw, nh = int(W * s), int(H * s)
                layer = layer.resize((nw, nh)).crop((int(cx * s - cx), int(cy * s - cy), int(cx * s - cx) + W, int(cy * s - cy) + H))
            frame.paste(layer, (0, 0), layer)
            d = ImageDraw.Draw(frame)
        # the PI card
        if t >= CARD[0]:
            k = min(1.0, (t - CARD[0]) / (CARD[1] - CARD[0]))
            x = 1320 - (1320 - 830) * (1 - (1 - k) ** 2)
            d.rounded_rectangle((x, 120, x + 400, 390), radius=14, fill=(250, 248, 240), outline=(120, 100, 60), width=4)
            d.text((x + 24, 136), "PI IDENTITY CARD", font=F_CARD_H, fill=(40, 50, 80))
            d.text((x + 24, 180), "lab gamma  ·  the PI", font=F_CARD, fill=(50, 50, 60))
            d.text((x + 24, 206), "issued by the registrar", font=F_CARD, fill=(50, 50, 60))
            d.text((x + 24, 232), "attests identity only", font=F_CARD, fill=(120, 80, 60))
            if t >= SIGN[0]:
                ks = min(1.0, (t - SIGN[0]) / (SIGN[1] - SIGN[0]))
                pts = [(x + 30 + 220 * u, 330 + 18 * math.sin(u * 22) - 12 * math.sin(u * 5)) for u in [i / 60 for i in range(int(60 * ks) + 1)]]
                if len(pts) > 1:
                    d.line(pts, fill=(30, 40, 120), width=3)
            if t >= SEAL:
                ks = min(1.0, (t - SEAL) / 0.15)
                r = 34 * (1.6 - 0.6 * ks)
                d.ellipse((1130 - r, 330 - r, 1130 + r, 330 + r), fill=(170, 30, 30))
                d.ellipse((1130 - r * 0.6, 330 - r * 0.6, 1130 + r * 0.6, 330 + r * 0.6), outline=(240, 180, 180), width=3)
        # the bin, and the toggle beside it
        d.rectangle(BIN, fill=(70, 76, 90), outline=(120, 128, 140), width=4)
        d.rectangle((BIN[0] - 8, BIN[1] - 16, BIN[2] + 8, BIN[1]), fill=(120, 128, 140))
        on = t >= TOGGLE
        d.rounded_rectangle((960, 600, 1060, 640), radius=20, fill=(70, 160, 110) if on else (90, 96, 110))
        d.ellipse((1022 if on else 962, 602, 1058 if on else 998, 638), fill=(240, 240, 240))
        d.text((930, 650), "archive: flips a flag, deletes nothing", font=font("Verdana Bold.ttf", 14), fill=(200, 215, 235))
        return frame

    def audio(self, left, right):
        creak = glissando(220, 420, 0.6, gain=0.2)
        add(left, int(PEEK[0] * SR), creak, 0.5)
        add(right, int(PEEK[0] * SR), creak, 0.5)
        stamp = tone(80, 0.3, decay=15, harmonics=(1.0, 0.4))
        snap = noise_burst(0.08, cutoff=1500, decay=40)
        add(left, int(STAMP * SR), stamp, 1.0)
        add(right, int(STAMP * SR), stamp, 1.0)
        add(left, int(STAMP * SR), snap, 0.7)
        add(right, int(STAMP * SR), snap, 0.7)
        slide = noise_burst(0.5, cutoff=3000, decay=6, attack=0.1)
        add(left, int(CARD[0] * SR), slide, 0.3)
        add(right, int(CARD[0] * SR), slide, 0.3)
        for k in range(6):
            sc = noise_burst(0.04, cutoff=5000, decay=50)
            add(left, int((SIGN[0] + k * 0.05) * SR), sc, 0.15)
            add(right, int((SIGN[0] + k * 0.05) * SR), sc, 0.12)
        hiss = noise_burst(0.4, cutoff=6000, decay=8)
        add(left, int(SEAL * SR), hiss, 0.4)
        add(right, int(SEAL * SR), hiss, 0.4)
        add(left, int(SEAL * SR), stamp, 0.6)
        add(right, int(SEAL * SR), stamp, 0.6)
        drag = noise_burst(0.7, cutoff=800, decay=2, attack=0.2)
        add(left, int(DRAG[0] * SR), drag, 0.2)
        add(right, int(DRAG[0] * SR), drag, 0.2)
        c = click(0.05)
        tg = tone(660, 0.2, decay=12)
        add(left, int(TOGGLE * SR), c, 0.8)
        add(right, int(TOGGLE * SR), c, 0.8)
        add(left, int(TOGGLE * SR), tg, 0.5)
        add(right, int(TOGGLE * SR), tg, 0.5)
        ch = chime((587.3, 740.0, 880.0), spacing=0.12, length=1.6)
        add(left, int(3.0 * SR), ch, 0.7)
        add(right, int(3.0 * SR), ch, 0.7)


if __name__ == "__main__":
    Registrar().main()
