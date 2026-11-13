"""Six-second opening for the prospector's training movie, also the clip that announced it on Slack:
a Yukon gold prospector blasts a mountain of funding open, nuggets labelled with the kinds of award fly
out, fireworks everywhere, loud. Frames with Pillow + numpy, sound synthesised with numpy, muxed by
ffmpeg. Writes opening.mp4 beside this file; prepend.py splices it onto the narrated movie.
Run: python3 training/agents/prospector/opening/make_clip.py [--stills]"""
from __future__ import annotations

import math
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
W, H, FPS, SECONDS = 1280, 720, 30, 6
N = FPS * SECONDS
SR = 44100
random.seed(11)
np.random.seed(11)

F_BIG = ImageFont.truetype("/System/Library/Fonts/Supplemental/Impact.ttf", 150)
F_MID = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", 48)
F_SMALL = ImageFont.truetype("/System/Library/Fonts/Supplemental/Verdana Bold.ttf", 28)
F_MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 26)
F_TAG = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", 22)

PALETTES = [
    [(255, 215, 0), (255, 240, 150), (255, 255, 255)],
    [(255, 90, 60), (255, 200, 80), (255, 255, 220)],
    [(90, 170, 255), (200, 230, 255), (255, 255, 255)],
    [(120, 255, 140), (220, 255, 200), (255, 255, 255)],
    [(255, 90, 220), (255, 180, 255), (255, 255, 230)],
    [(255, 215, 0), (255, 170, 40), (255, 255, 200)],
]

BLAST_T = 2.3
SWINGS = [1.5, 1.95]            # pickaxe hits before the blast
GROUND = 560


class Rocket:
    def __init__(self, t0, x, apex_y, palette, size=1.0, kind="peony"):
        self.t0, self.x, self.apex_y, self.palette, self.size, self.kind = t0, x, apex_y, palette, size, kind
        self.flight = 0.8 + 0.2 * random.random()
        self.burst_t = t0 + self.flight
        self.particles = None

    def position(self, t):
        f = (t - self.t0) / self.flight
        return self.x + 6 * math.sin(f * 9), H - (H - self.apex_y) * (1 - (1 - f) ** 2)

    def burst(self):
        n = int(240 * self.size)
        angles = np.random.uniform(0, 2 * math.pi, n)
        speed = np.full(n, 330.0 * self.size) if self.kind == "ring" else np.random.uniform(80, 360, n) * self.size
        self.particles = {
            "x": np.full(n, self.x, dtype=float), "y": np.full(n, self.apex_y, dtype=float),
            "vx": np.cos(angles) * speed, "vy": np.sin(angles) * speed,
            "life": np.random.uniform(1.0, 2.2, n) * (1.4 if self.kind == "willow" else 1.0),
            "age": np.zeros(n), "color": np.random.randint(0, len(self.palette), n),
        }

    def step(self, dt):
        p = self.particles
        if p is None:
            return
        drag = 0.985 if self.kind != "willow" else 0.96
        p["vx"] *= drag
        p["vy"] = p["vy"] * drag + 260 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["age"] += dt


SCHEDULE = [
    (0.1, 300, 200, 2, 0.8, "peony"), (0.5, 1050, 170, 1, 0.8, "peony"),
    (0.9, 640, 120, 0, 1.0, "ring"),
    (2.35, 200, 180, 0, 1.4, "peony"), (2.4, 1080, 160, 5, 1.4, "peony"), (2.45, 640, 90, 0, 1.8, "ring"),
    (2.7, 420, 240, 1, 1.0, "willow"), (2.8, 860, 220, 2, 1.0, "willow"),
    (3.1, 150, 140, 3, 1.1, "peony"), (3.2, 1130, 130, 4, 1.1, "peony"),
    (3.5, 640, 110, 5, 1.6, "peony"), (3.8, 350, 200, 0, 0.9, "ring"), (3.9, 930, 200, 1, 0.9, "ring"),
    (4.2, 500, 150, 2, 1.0, "peony"), (4.3, 780, 150, 3, 1.0, "peony"),
    (4.6, 640, 80, 0, 2.0, "peony"), (4.8, 180, 260, 4, 0.8, "willow"), (4.85, 1100, 260, 5, 0.8, "willow"),
]
ROCKETS = [Rocket(t0, x, y, PALETTES[p], s, k) for t0, x, y, p, s, k in SCHEDULE]
BURST_TIMES = [r.burst_t for r in ROCKETS]
BURST_SIZES = [r.size for r in ROCKETS]

# Nuggets that fly out of the mountain, each one a kind of award.
TAGS = ["scholarship", "fellowship", "travel award", "operating grant", "equipment", "charity call",
        "$", "$", "$", "$", "$", "$", "$", "$"]
NUGGETS = []
for i, tag in enumerate(TAGS):
    ang = math.radians(random.uniform(200, 340))
    sp = random.uniform(380, 720) if tag != "$" else random.uniform(250, 600)
    NUGGETS.append({"tag": tag, "x": 980.0, "y": 420.0, "vx": math.cos(ang) * sp, "vy": math.sin(ang) * sp,
                    "spin": random.uniform(-6, 6), "r": 22 if tag == "$" else 30})
DEBRIS = [{"x": 980.0, "y": 430.0, "vx": math.cos(a) * s, "vy": math.sin(a) * s, "r": random.uniform(4, 14)}
          for a, s in ((math.radians(random.uniform(190, 350)), random.uniform(200, 900)) for _ in range(90))]


# --------------------------------------------------------------------------- scenery

def sky(t):
    img = Image.new("RGB", (W, H), (6, 8, 30))
    d = ImageDraw.Draw(img)
    # aurora bands
    for k in range(3):
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(band)
        ph = t * 0.6 + k
        pts = [(x, 120 + 60 * k + 40 * math.sin(x / 160 + ph) + 20 * math.sin(x / 57 - ph * 2)) for x in range(0, W + 40, 40)]
        poly = pts + [(x, y + 90 + 20 * k) for x, y in reversed(pts)]
        col = [(60, 220, 140, 70), (90, 160, 255, 50), (190, 90, 230, 45)][k]
        bd.polygon(poly, fill=col)
        band = band.filter(ImageFilter.GaussianBlur(18))
        img.paste(band, (0, 0), band)
    # stars
    rs = random.Random(3)
    for _ in range(140):
        x, y = rs.randint(0, W), rs.randint(0, 380)
        tw = 150 + int(100 * math.sin(t * 5 + x))
        d.point((x, y), fill=(tw, tw, 255))
    # moon
    d.ellipse((90, 60, 170, 140), fill=(250, 245, 210))
    d.ellipse((115, 50, 185, 120), fill=(6, 8, 30))
    # far mountains (snowy)
    far = [(0, 430), (120, 300), (240, 380), (360, 260), (470, 360), (560, 310), (640, 400), (700, 330), (800, 420), (W, 440), (W, H), (0, H)]
    d.polygon(far, fill=(40, 52, 96))
    for i in range(1, 8):
        x, y = far[i]
        if y < 340:
            d.polygon([(x, y), (x - 28, y + 38), (x + 28, y + 38)], fill=(200, 215, 240))
    # snow ground
    d.rectangle((0, GROUND, W, H), fill=(190, 205, 230))
    d.polygon([(0, GROUND), (W, GROUND - 30), (W, GROUND), (0, GROUND + 10)], fill=(215, 225, 245))
    # pines
    for x in (60, 150, 230, 1180, 1240):
        for k in range(3):
            d.polygon([(x, 440 + k * 35), (x - 30 - k * 8, 500 + k * 35), (x + 30 + k * 8, 500 + k * 35)], fill=(18, 60, 40))
        d.rectangle((x - 6, 560, x + 6, 585), fill=(60, 35, 20))
    return img


def mountain(d, t, crack):
    """The mountain of funding, right of centre; cracks open as the pick hits; gone after the blast."""
    if t >= BLAST_T:
        # rubble
        d.polygon([(820, GROUND), (900, 520), (980, 535), (1060, 515), (1140, GROUND)], fill=(70, 60, 60))
        return
    base = [(780, GROUND), (880, 380), (930, 330), (980, 250), (1030, 320), (1090, 370), (1180, GROUND)]
    d.polygon(base, fill=(78, 66, 70))
    d.polygon([(930, 330), (980, 250), (1030, 320), (1005, 335), (980, 300), (955, 340)], fill=(235, 240, 250))
    # ore veins of gold
    for pts in ([(900, 470), (940, 440), (960, 480), (1000, 455)], [(1000, 520), (1040, 500), (1070, 530)]):
        d.line(pts, fill=(255, 200, 40), width=6)
    # the label chiselled on it
    f = F_MID
    txt = "FUNDING"
    bb = d.textbbox((0, 0), txt, font=f)
    x = 980 - (bb[2] - bb[0]) / 2
    d.text((x + 3, 393), txt, font=f, fill=(20, 15, 20))
    d.text((x, 390), txt, font=f, fill=(255, 215, 0))
    # cracks
    for k in range(crack):
        rs = random.Random(k)
        x0, y0 = 940 + rs.randint(-40, 60), 420 + rs.randint(-60, 40)
        pts = [(x0, y0)]
        for _ in range(5):
            x0 += rs.randint(-30, 30)
            y0 += rs.randint(10, 35)
            pts.append((x0, y0))
        d.line(pts, fill=(255, 240, 160), width=3)


def prospector(img, t):
    """A Yukon prospector: hat, beard, red plaid shirt, pickaxe. Walks in, then swings."""
    d = ImageDraw.Draw(img)
    walk = min(1.0, t / 1.2)
    x = 420 + 300 * (1 - (1 - walk) ** 2)
    y = GROUND
    bob = 6 * math.sin(t * 14) if walk < 1 else 0
    # recoil after the blast
    if t >= BLAST_T:
        k = min(1.0, (t - BLAST_T) / 0.3)
        x -= 60 * k
    y = int(y + bob)
    x = int(x)
    # legs
    leg = 12 * math.sin(t * 14) if walk < 1 else 0
    d.line((x - 10, y - 70, x - 18 - leg, y), fill=(40, 40, 70), width=14)
    d.line((x + 10, y - 70, x + 18 + leg, y), fill=(40, 40, 70), width=14)
    d.rectangle((x - 30 - leg, y - 6, x - 6 - leg, y + 4), fill=(50, 30, 20))
    d.rectangle((x + 6 + leg, y - 6, x + 30 + leg, y + 4), fill=(50, 30, 20))
    # body: red plaid
    d.rounded_rectangle((x - 34, y - 150, x + 34, y - 60), radius=14, fill=(190, 40, 40))
    for yy in range(y - 140, y - 60, 18):
        d.line((x - 34, yy, x + 34, yy), fill=(120, 20, 20), width=3)
    for xx in range(x - 26, x + 34, 18):
        d.line((xx, y - 150, xx, y - 60), fill=(120, 20, 20), width=3)
    # head, beard, hat
    d.ellipse((x - 26, y - 206, x + 26, y - 150), fill=(235, 190, 150))
    d.ellipse((x - 26, y - 182, x + 26, y - 138), fill=(210, 210, 215))     # grey beard
    d.ellipse((x - 8, y - 186, x + 8, y - 176), fill=(235, 190, 150))      # nose
    d.ellipse((x - 16, y - 196, x - 10, y - 190), fill=(20, 20, 20))
    d.ellipse((x + 10, y - 196, x + 16, y - 190), fill=(20, 20, 20))
    d.rounded_rectangle((x - 44, y - 206, x + 44, y - 196), radius=5, fill=(110, 70, 30))   # brim
    d.rounded_rectangle((x - 28, y - 246, x + 28, y - 200), radius=10, fill=(130, 85, 35))   # crown
    d.rectangle((x - 28, y - 214, x + 28, y - 206), fill=(60, 35, 15))
    # pickaxe: angle from the swing
    ang = -0.9
    for s in SWINGS:
        if s - 0.35 <= t < s:
            ang = -0.9 - 1.6 * ((t - (s - 0.35)) / 0.35)     # wind up
        elif s <= t < s + 0.12:
            ang = -2.5 + 3.2 * ((t - s) / 0.12)              # strike
        elif s + 0.12 <= t < s + 0.5:
            ang = 0.7 - 1.6 * ((t - s - 0.12) / 0.38)
    if t >= BLAST_T:
        ang = -1.4
    hx, hy = x + 30, y - 120
    L = 120
    ex, ey = hx + L * math.cos(ang), hy + L * math.sin(ang)
    d.line((hx, hy, ex, ey), fill=(120, 80, 40), width=10)
    px, py = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
    head = [(ex - 55 * px, ey - 55 * py), (ex + 18 * math.cos(ang), ey + 18 * math.sin(ang)),
            (ex + 55 * px, ey + 55 * py), (ex - 10 * math.cos(ang), ey - 10 * math.sin(ang))]
    d.polygon(head, fill=(170, 175, 185))
    # arm to the handle
    d.line((x + 20, y - 130, hx, hy), fill=(190, 40, 40), width=12)
    d.ellipse((hx - 9, hy - 9, hx + 9, hy + 9), fill=(235, 190, 150))


def nuggets(img, t, dt):
    if t < BLAST_T:
        return
    d = ImageDraw.Draw(img)
    for p in DEBRIS:
        p["vy"] += 900 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        if p["y"] > GROUND:
            p["y"], p["vy"] = GROUND, -p["vy"] * 0.3
        r = p["r"]
        d.ellipse((p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r), fill=(80, 70, 70))
    for p in NUGGETS:
        p["vy"] += 700 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        if p["y"] > GROUND - 10:
            p["y"], p["vy"], p["vx"] = GROUND - 10, -p["vy"] * 0.35, p["vx"] * 0.7
        if p["x"] < 80 or p["x"] > W - 80:
            p["x"], p["vx"] = min(max(p["x"], 80), W - 80), -p["vx"] * 0.6
        r = p["r"]
        pts = [(p["x"] + r * (0.8 + 0.3 * math.sin(k * 2.1)) * math.cos(k * math.pi / 3 + t * p["spin"]),
                p["y"] + r * (0.8 + 0.3 * math.cos(k * 1.7)) * math.sin(k * math.pi / 3 + t * p["spin"])) for k in range(6)]
        d.polygon(pts, fill=(255, 200, 30), outline=(200, 140, 0))
        d.ellipse((p["x"] - r * 0.3, p["y"] - r * 0.4, p["x"], p["y"] - r * 0.1), fill=(255, 245, 190))
        if p["tag"] != "$":
            bb = d.textbbox((0, 0), p["tag"], font=F_TAG)
            tw = bb[2] - bb[0]
            d.rounded_rectangle((p["x"] - tw / 2 - 8, p["y"] - r - 36, p["x"] + tw / 2 + 8, p["y"] - r - 6), radius=8, fill=(0, 0, 0))
            d.text((p["x"] - tw / 2, p["y"] - r - 32), p["tag"], font=F_TAG, fill=(255, 215, 0))
        else:
            d.text((p["x"] - 7, p["y"] - 12), "$", font=F_TAG, fill=(120, 80, 0))


def draw_frame(i: int, trail: Image.Image):
    t = i / FPS
    dt = 1 / FPS
    frame = sky(t)
    d = ImageDraw.Draw(frame)
    crack = sum(1 for s in SWINGS if t >= s) * 3
    mountain(d, t, crack)
    # fireworks on a persistence layer
    trail = Image.eval(trail, lambda v: int(v * 0.82))
    td = ImageDraw.Draw(trail)
    for r in ROCKETS:
        if r.t0 <= t < r.burst_t:
            x, y = r.position(t)
            td.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 230, 160))
            td.line((x, y, x - 2, y + 14), fill=(255, 150, 60), width=2)
        elif t >= r.burst_t:
            if r.particles is None:
                r.burst()
            r.step(dt)
            p = r.particles
            fade = np.clip(1 - p["age"] / p["life"], 0, 1)
            for k in np.nonzero(p["age"] < p["life"])[0]:
                c = r.palette[p["color"][k]]
                f = fade[k]
                s = 2.2 * r.size * (0.6 + f)
                td.ellipse((p["x"][k] - s, p["y"][k] - s, p["x"][k] + s, p["y"][k] + s), fill=tuple(int(v * f) for v in c))
            if p["age"][0] < 0.12:
                rad = 90 * r.size * (1 - p["age"][0] / 0.12)
                td.ellipse((r.x - rad, r.apex_y - rad, r.x + rad, r.apex_y + rad), fill=(255, 255, 240))
    glow = trail.filter(ImageFilter.GaussianBlur(6))
    frame = Image.fromarray(np.clip(np.asarray(frame, dtype=np.int16) + np.asarray(glow, dtype=np.int16)
                                    + np.asarray(trail, dtype=np.int16) // 2, 0, 255).astype(np.uint8))
    # pick sparks
    d = ImageDraw.Draw(frame)
    for s in SWINGS:
        if s <= t < s + 0.25:
            rs = random.Random(int(t * 100))
            for _ in range(25):
                a, L = rs.uniform(-3.1, 0), rs.uniform(10, 70) * (t - s) / 0.25 * 4
                d.line((900, 430, 900 + L * math.cos(a), 430 + L * math.sin(a)), fill=(255, 240, 150), width=2)
    prospector(frame, t)
    nuggets(frame, t, dt)
    # the blast itself: fireball then smoke
    if BLAST_T <= t < BLAST_T + 0.9:
        k = (t - BLAST_T) / 0.9
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        rad = 120 + 420 * k
        for j, col in enumerate(((255, 255, 230), (255, 200, 60), (255, 90, 20), (90, 60, 50))):
            rr = rad * (0.35 + 0.22 * j)
            ld.ellipse((980 - rr, 420 - rr * 0.9, 980 + rr, 420 + rr * 0.6), fill=col + (int(220 * (1 - k) ** 1.5),))
        layer = layer.filter(ImageFilter.GaussianBlur(10 + 30 * k))
        frame.paste(layer, (0, 0), layer)
        if k < 0.15:
            white = Image.new("RGB", (W, H), (255, 255, 240))
            frame = Image.blend(frame, white, 1 - k / 0.15)
    # shake
    shake = 0
    for bt, bs in zip(BURST_TIMES + [BLAST_T] + SWINGS, BURST_SIZES + [4.0] + [0.8, 0.8]):
        if 0 <= t - bt < 0.3:
            shake = max(shake, int(10 * bs * (1 - (t - bt) / 0.3)))
    if shake:
        frame = frame.transform((W, H), Image.AFFINE, (1, 0, random.randint(-shake, shake), 0, 1, random.randint(-shake, shake)))
    d = ImageDraw.Draw(frame)
    # title
    if t >= 2.6:
        a = min(1.0, (t - 2.6) / 0.25)
        scale = 1.6 - 0.6 * (1 - (1 - a) ** 3)
        txt = "THE PROSPECTOR"
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        bb = ld.textbbox((0, 0), txt, font=F_BIG)
        tw = bb[2] - bb[0]
        for off, col in ((8, (120, 60, 0, 255)), (4, (255, 170, 0, 255)), (0, (255, 250, 220, 255))):
            ld.text(((W - tw) / 2 - bb[0] + off, 60 - bb[1] + off), txt, font=F_BIG, fill=col)
        if scale != 1.0:
            nw, nh = int(W * scale), int(H * scale)
            layer = layer.resize((nw, nh)).crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))
        frame.paste(layer, (0, 0), layer)
    if t >= 3.5:
        a = min(1.0, (t - 3.5) / 0.3)
        txt = "finds the funding you may apply for"
        bb = d.textbbox((0, 0), txt, font=F_MID)
        x = (W - (bb[2] - bb[0])) / 2
        y = 236 + 30 * (1 - a)
        d.text((x + 3, y + 3), txt, font=F_MID, fill=(40, 20, 0))
        d.text((x, y), txt, font=F_MID, fill=(255, 230, 120))
    if t >= 4.3:
        a = min(1.0, (t - 4.3) / 0.3)
        line = "ask the prospector what I can apply for in the next twelve months"
        bb = d.textbbox((0, 0), line, font=F_MONO)
        tw = bb[2] - bb[0]
        x = (W - tw) / 2
        box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((x - 24, 600, x + tw + 24, 664), radius=14, fill=(0, 0, 0, int(200 * a)))
        frame.paste(box, (0, 0), box)
        d.text((x, 616), line, font=F_MONO, fill=(int(255 * a),) * 3)
    if t >= 5.0:
        txt = "a new two-minute training movie · murmurent"
        bb = d.textbbox((0, 0), txt, font=F_SMALL)
        d.text(((W - (bb[2] - bb[0])) / 2, 676), txt, font=F_SMALL, fill=(255, 235, 160))
    return frame, trail


# --------------------------------------------------------------------------- sound

def lowpass(x, cutoff):
    alpha = (1 / SR) / (1 / (2 * math.pi * cutoff) + 1 / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def bang(size):
    n = int(SR * (0.9 + 0.6 * size))
    tt = np.arange(n) / SR
    noise = np.random.randn(n)
    body = lowpass(noise, 180 + 120 / size) * np.exp(-tt * (3.2 / size))
    crack = noise * np.exp(-tt * 40) * 0.8
    thump = np.sin(2 * math.pi * (55 / size) * tt) * np.exp(-tt * 6) * 1.2
    crackle = (np.random.rand(n) < 0.004 * size) * np.random.randn(n) * np.exp(-tt * 2.5) * 0.9
    return (body * 3.0 + crack + thump + crackle) * min(1.0, 0.5 + size / 2)


def whistle(duration):
    n = int(SR * duration)
    tt = np.arange(n) / SR
    f = 600 + 1400 * (tt / duration) ** 1.6
    phase = 2 * math.pi * np.cumsum(f) / SR
    return (np.sin(phase) * 0.18 + np.random.randn(n) * 0.03) * np.sin(math.pi * tt / duration) ** 0.5


def clink():
    n = int(SR * 0.35)
    tt = np.arange(n) / SR
    return sum(np.sin(2 * math.pi * f * tt) * np.exp(-tt * d) for f, d in ((2900, 18), (4100, 22), (5600, 30), (1200, 10))) * 0.5 \
        + np.random.randn(n) * np.exp(-tt * 90) * 0.6


def fanfare(start, audio):
    chords = [(0.0, [261.6, 329.6, 392.0]), (0.35, [293.7, 370.0, 440.0]),
              (0.7, [329.6, 415.3, 493.9, 659.3]), (1.05, [392.0, 493.9, 587.3, 784.0])]
    for off, notes in chords:
        n = int(SR * 1.4)
        tt = np.arange(n) / SR
        env = np.exp(-tt * 1.6) * (1 - np.exp(-tt * 60))
        tone = sum(np.sin(2 * math.pi * f * tt) * (1 / (k + 1)) for k, f in enumerate(notes))
        tone += 0.3 * sum(np.sin(2 * math.pi * 2 * f * tt) for f in notes)
        add(audio, int((start + off) * SR), tone * env, 0.35)


def add(buf, start, sound, gain):
    end = min(len(buf), start + len(sound))
    buf[start:end] += sound[: end - start] * gain


def make_audio():
    total = SR * (SECONDS + 1)
    left, right = np.zeros(total), np.zeros(total)
    for r in ROCKETS:
        pan = r.x / W
        w = whistle(r.flight * 0.9)
        add(left, int(r.t0 * SR), w, (1 - pan) * 0.9)
        add(right, int(r.t0 * SR), w, pan * 0.9)
        b = bang(r.size)
        add(left, int(r.burst_t * SR), b, 0.5 + 0.5 * (1 - pan))
        add(right, int(r.burst_t * SR), b, 0.5 + 0.5 * pan)
    for s in SWINGS:
        c = clink()
        add(left, int(s * SR), c, 0.6)
        add(right, int(s * SR), c, 0.9)
    big = bang(3.5)
    add(left, int(BLAST_T * SR), big, 1.6)
    add(right, int(BLAST_T * SR), big, 1.9)
    # rocks raining down
    for k in range(30):
        s = BLAST_T + 0.4 + random.random() * 1.2
        th = bang(0.25) * 0.25
        add(left, int(s * SR), th, random.random())
        add(right, int(s * SR), th, random.random())
    fanfare(2.6, left)
    fanfare(2.6, right)
    n = SR * SECONDS
    rumble = lowpass(np.random.randn(n), 60) * 2.5
    left[:n] += rumble
    right[:n] += rumble
    audio = np.stack([left, right], axis=1)[: SR * SECONDS]
    audio = np.tanh(audio * 1.4)
    audio *= 0.89 / np.max(np.abs(audio))
    return (audio * 32767).astype(np.int16)


def main():
    import sys
    frames_dir = HERE / "frames"
    frames_dir.mkdir(exist_ok=True)
    if "--stills" in sys.argv:
        trail = Image.new("RGB", (W, H), (0, 0, 0))
        for i in range(N):
            frame, trail = draw_frame(i, trail)
            if i % 15 == 0:
                frame.save(HERE / f"still_{i:03d}.png")
        return
    trail = Image.new("RGB", (W, H), (0, 0, 0))
    for i in range(N):
        frame, trail = draw_frame(i, trail)
        frame.save(frames_dir / f"f{i:04d}.png")
    wav = HERE / "sound.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(make_audio().tobytes())
    out = HERE / "opening.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%04d.png"),
                    "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(out)


if __name__ == "__main__":
    main()
