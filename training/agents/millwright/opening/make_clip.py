#!/usr/bin/env python3
"""
Purpose: The millwright's six-second opening. From agents/millwright.md, "Personality":
         efficient, practical, slightly literal; wires things up, checks the signal is clean,
         hands over the keys; says "Wired. @handle is ready to connect on <machine> for
         <project>."; never alarmed, never verbose; shows up at 8 a.m., installs the thing,
         tests the thing, documents the thing, and leaves by 10. The gag, literally that: the
         clock reads 8:00, one cable goes in, the rack's lights go green one by one, the
         laptop prints "Wired.", three boxes get ticked (installed, tested, documented), the
         clock sweeps to 10:00, and the millwright walks out and shuts the door.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing; drawn here on training/lib/opening.py.
Output: opening.mp4 beside this file; --prepend splices it onto ../millwright_narrated.mp4.
Usage: python3 training/agents/millwright/opening/make_clip.py [--stills] [--prepend]
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.draw import TEAL  # noqa: E402  (the movie's own colour)
from lib.opening import (F_MONO, F_TAG, H, SR, W, Opening, add, clink, clock, click, font, hum, laptop,  # noqa: E402
                         noise_burst, text_centered, tone)

F_CHECK = font("Verdana Bold.ttf", 24)
PLUG = 0.9                              # the cable goes in
LIGHTS = [1.25, 1.55, 1.85]             # the rack's lights go green
WIRED = 2.2                             # the laptop prints the line
TICKS = [3.4, 3.7, 4.0]                 # installed, tested, documented
SWEEP = (3.3, 4.7)                      # the clock runs from 8 to 10
LEAVE = 4.7                             # walks out
DOOR = 5.5                              # the door shuts
FLOOR = 600
RACK = (1000, 160, 1180, FLOOR)


class Millwright(Opening):
    agent = "millwright"
    title = "THE MILLWRIGHT"
    tagline = "installs it, tests it, documents it, gone by ten"
    prompt_line = "ask the millwright to set up the new project and wire my laptop to it"
    title_at, tagline_at, prompt_at = 2.6, 3.0, 4.6
    title_colours = ((8, (10, 50, 45, 255)), (4, (52, 190, 170, 255)), (0, (235, 250, 245, 255)))
    tagline_colour, tagline_shadow = (200, 240, 230), (10, 40, 36)
    footer_colour = (200, 240, 230)
    fireworks_schedule = []         # never alarmed; no fireworks, three green lights
    shakes = [(DOOR, 0.6)]

    def hour(self, t):
        a, b = SWEEP
        if t < a:
            return 8.0
        if t > b:
            return 10.0
        return 8.0 + 2.0 * (1 - (1 - (t - a) / (b - a)) ** 2)

    def background(self, t):
        img = Image.new("RGB", (W, H), (30, 36, 48))
        d = ImageDraw.Draw(img)
        for y in range(0, FLOOR, 40):
            d.line((0, y, W, y), fill=(36, 42, 56), width=1)
        d.rectangle((0, FLOOR, W, H), fill=(54, 58, 66))
        for x in range(0, W, 60):
            d.line((x, FLOOR, x, H), fill=(48, 52, 60), width=1)
        clock(d, 255, 360, 50, self.hour(t), face=(240, 240, 232), rim=(50, 50, 60))
        # the door, left: open until DOOR
        d.rectangle((40, 220, 200, FLOOR), fill=(22, 26, 36))
        shut = t >= DOOR
        if shut:
            d.rectangle((40, 220, 200, FLOOR), fill=(110, 80, 50), outline=(60, 40, 25), width=5)
            d.ellipse((170, 410, 184, 424), fill=(220, 200, 120))
        else:
            d.polygon([(40, 220), (90, 240), (90, FLOOR), (40, FLOOR)], fill=(110, 80, 50), outline=(60, 40, 25))
        # the desk with the laptop, middle left
        d.rectangle((300, 470, 620, 488), fill=(90, 70, 50))
        d.rectangle((320, 488, 336, FLOOR), fill=(70, 55, 40))
        d.rectangle((584, 488, 600, FLOOR), fill=(70, 55, 40))
        return img

    def rack(self, d, t):
        x0, y0, x1, y1 = RACK
        d.rectangle((x0, y0, x1, y1), fill=(40, 42, 50), outline=(90, 92, 100), width=6)
        for k in range(8):
            y = y0 + 20 + k * 52
            d.rectangle((x0 + 12, y, x1 - 12, y + 40), fill=(60, 62, 72))
            for j in range(6):
                d.rectangle((x0 + 26 + j * 22, y + 24, x0 + 40 + j * 22, y + 32), fill=(30, 30, 36))
            # the status light: red, then green from its LIGHTS time; fans whir after PLUG
            lit = k < 3 and t >= LIGHTS[k]
            col = (60, 220, 120) if lit else ((226, 100, 100) if k < 3 else (80, 80, 90))
            if lit and int(t * 8) % 2 == 0 and t < LIGHTS[k] + 0.3:
                col = (180, 255, 200)
            d.ellipse((x1 - 34, y + 6, x1 - 22, y + 18), fill=col)
            if t >= PLUG:
                a = t * 25 + k
                for s in range(3):
                    d.line((x0 + 150, y + 16, x0 + 150 + 7 * math.cos(a + s * 2.1), y + 16 + 7 * math.sin(a + s * 2.1)), fill=(150, 150, 160), width=2)
        # the port the cable goes into
        d.rectangle((x0 - 6, 500, x0 + 14, 520), fill=(20, 20, 24), outline=(140, 140, 150), width=2)

    def wright(self, d, t):
        """Hi-vis vest over the teal shirt, tool belt, cap; walks in carrying a cable, plugs it in,
        turns to the laptop, then walks out of the door."""
        if t >= DOOR:
            return
        if t < PLUG:
            x = 880 + 60 * min(1.0, t / PLUG)
            walking = t < PLUG - 0.1
        elif t < LEAVE:
            x = 940 - 240 * min(1.0, (t - PLUG) / 0.5)
            walking = t < PLUG + 0.5
        else:
            x = 700 - 700 * min(1.0, (t - LEAVE) / (DOOR - LEAVE)) ** 0.9
            walking = True
        y = FLOOR
        skin, shirt, vest = (215, 175, 140), TEAL, (250, 220, 40)
        bob = 5 * math.sin(t * 16) if walking else 0
        leg = 14 * math.sin(t * 16) if walking else 0
        y = int(y + bob)
        d.line((x - 10, y - 80, x - 18 - leg, y), fill=(50, 56, 70), width=16)
        d.line((x + 10, y - 80, x + 18 + leg, y), fill=(50, 56, 70), width=16)
        d.rectangle((x - 32 - leg, y - 6, x - 6 - leg, y + 4), fill=(50, 35, 20))
        d.rectangle((x + 6 + leg, y - 6, x + 32 + leg, y + 4), fill=(50, 35, 20))
        d.rounded_rectangle((x - 36, y - 170, x + 36, y - 70), radius=14, fill=shirt)
        d.rounded_rectangle((x - 30, y - 165, x + 30, y - 90), radius=8, fill=vest)
        d.line((x - 30, y - 130, x + 30, y - 130), fill=(200, 200, 210), width=6)
        d.rectangle((x - 40, y - 96, x + 40, y - 80), fill=(90, 60, 30))          # the tool belt
        for k in range(-1, 2):
            d.rectangle((x + k * 24 - 6, y - 110, x + k * 24 + 6, y - 92), fill=(130, 130, 140))
        # head and cap
        d.ellipse((x - 26, y - 226, x + 26, y - 170), fill=skin)
        d.ellipse((x - 14, y - 206, x - 8, y - 200), fill=(20, 20, 20))
        d.ellipse((x + 8, y - 206, x + 14, y - 200), fill=(20, 20, 20))
        d.line((x - 8, y - 186, x + 8, y - 186), fill=(120, 80, 70), width=3)
        d.chord((x - 28, y - 236, x + 28, y - 196), 180, 360, fill=(40, 60, 90))
        d.rectangle((x - 2, y - 218, x + 46, y - 210), fill=(40, 60, 90))
        # arms: the right one carries the cable to the port, the left rests; typing at WIRED
        if t < PLUG + 0.5:
            k = min(1.0, t / PLUG)
            ex, ey = x + 60, y - 120 + 10 * k
            d.line((x + 34, y - 150, ex, ey), fill=shirt, width=14)
            d.ellipse((ex - 9, ey - 9, ex + 9, ey + 9), fill=skin)
            # the cable: from the hand to the port once plugged, else dangling
            if t >= PLUG:
                d.line((ex, ey, RACK[0] + 4, 510), fill=(60, 200, 230), width=6)
            else:
                d.line((ex, ey, ex + 30, ey + 40, ex + 60, ey + 30), fill=(60, 200, 230), width=6, joint="curve")
        else:
            d.line((x + 34, y - 150, x + 50, y - 100), fill=shirt, width=14)
            d.ellipse((x + 41, y - 109, x + 59, y - 91), fill=skin)
        d.line((x - 34, y - 150, x - 46, y - 96), fill=shirt, width=14)
        d.ellipse((x - 55, y - 105, x - 37, y - 87), fill=skin)
        if t >= PLUG + 0.5 and t < LEAVE:
            # the cable stays in the port, running along the floor
            pass

    def scene(self, frame, t, dt):
        d = ImageDraw.Draw(frame)
        self.rack(d, t)
        if t >= PLUG:
            d.line((RACK[0] + 4, 512, 900, 560, 620, 560, 600, 480), fill=(60, 200, 230), width=6, joint="curve")
        box = laptop(d, 460, 475, w=280, h=160, screen=(14, 18, 28))
        x0, y0, x1, y1 = box
        d.text((x0 + 8, y0 + 6), "$ murmurent doctor", font=F_MONO, fill=(170, 230, 210))
        d.text((x0 + 8, y0 + 34), "hooks ok  mcp ok  data root ok", font=F_MONO, fill=(120, 150, 150))
        if t >= WIRED:
            n = int((t - WIRED) / 0.6 * 60)
            line = "Wired. @allie is ready to"[:n]
            line2 = "connect on lab-server for dcis_sc."[: max(0, n - 25)]
            d.text((x0 + 8, y0 + 70), line, font=F_MONO, fill=(60, 220, 120))
            d.text((x0 + 8, y0 + 96), line2, font=F_MONO, fill=(60, 220, 120))
        self.wright(d, t)
        return frame

    def overlay(self, frame, t, dt):
        # the three boxes, ticked in turn, on a clipboard by the rack
        if t < TICKS[0] - 0.3:
            return frame
        d = ImageDraw.Draw(frame)
        x, y = 800, 320
        d.rounded_rectangle((x - 20, y - 20, x + 200, y + 130), radius=10, fill=(245, 242, 230), outline=(80, 70, 60), width=4)
        d.rectangle((x + 55, y - 34, x + 125, y - 14), fill=(90, 90, 100))
        for k, (label, at) in enumerate(zip(("installed", "tested", "documented"), TICKS)):
            yy = y + 10 + k * 40
            d.rectangle((x, yy, x + 26, yy + 26), outline=(60, 60, 70), width=3)
            d.text((x + 40, yy - 2), label, font=F_CHECK, fill=(50, 50, 60))
            if t >= at:
                d.line((x + 5, yy + 13, x + 11, yy + 22, x + 24, yy + 3), fill=(30, 160, 90), width=5)
        return frame

    def audio(self, left, right):
        rs = random.Random(2)
        # footsteps in, and out
        for s in list(np.arange(0.1, PLUG, 0.3)) + list(np.arange(PLUG + 0.05, PLUG + 0.5, 0.25)) + list(np.arange(LEAVE, DOOR, 0.28)):
            step = noise_burst(0.08, cutoff=300, decay=40) * 2
            add(left, int(s * SR), step, 0.5 * rs.uniform(0.8, 1.0))
            add(right, int(s * SR), step, 0.5 * rs.uniform(0.8, 1.0))
        # the plug clicks home, the fans spin up and stay
        c = clink(((3000, 50), (4500, 70), (900, 30)), length=0.1)
        add(left, int(PLUG * SR), c, 0.8)
        add(right, int(PLUG * SR), c, 1.0)
        add(left, int(PLUG * SR), hum(6 - PLUG, 110.0, 0.12), 1.0)
        add(right, int(PLUG * SR), hum(6 - PLUG, 110.0, 0.12), 1.0)
        for k, s in enumerate(LIGHTS):
            beep = tone(880 * 2 ** (k * 2 / 12), 0.18, decay=12, harmonics=(1.0, 0.2), attack=0.003)
            add(left, int(s * SR), beep, 0.35)
            add(right, int(s * SR), beep, 0.45)
        # the line printed: a short key clatter
        for k in range(26):
            key = click(0.02)
            add(left, int((WIRED + k * 0.023) * SR), key, 0.25)
            add(right, int((WIRED + k * 0.023) * SR), key, 0.25)
        # a plain two-note figure under the title, no fanfare
        for off, f in ((0.0, 392.0), (0.25, 523.3)):
            add(left, int((2.6 + off) * SR), tone(f, 1.2, decay=2.5, harmonics=(1.0, 0.3)), 0.3)
            add(right, int((2.6 + off) * SR), tone(f, 1.2, decay=2.5, harmonics=(1.0, 0.3)), 0.3)
        # three ticks of a pen
        for s in TICKS:
            tick = noise_burst(0.06, cutoff=3000, decay=50)
            add(left, int(s * SR), tick, 0.5)
            add(right, int(s * SR), tick, 0.5)
        # the clock runs
        for k in range(int((SWEEP[1] - SWEEP[0]) / 0.07)):
            tk = click(0.01)
            add(left, int((SWEEP[0] + k * 0.07) * SR), tk, 0.12)
            add(right, int((SWEEP[0] + k * 0.07) * SR), tk, 0.12)
        # the door shuts
        door = noise_burst(0.35, cutoff=250, decay=12) * 3
        add(left, int(DOOR * SR), door, 1.1)
        add(right, int(DOOR * SR), door, 0.8)
        add(left, int(DOOR * SR), tone(90, 0.4, decay=7, harmonics=(1.0, 0.5)), 0.6)
        add(right, int(DOOR * SR), tone(90, 0.4, decay=7, harmonics=(1.0, 0.5)), 0.5)


if __name__ == "__main__":
    Millwright().main()
