"""
Purpose: The shared engine behind each agent's six-second animated opening, the cartoon
         spliced onto the front of its training movie. An agent's opening/make_clip.py is a
         short spec on top of this: it subclasses Opening, draws its own characters and gag
         in scene(), adds its own sounds in audio(), and names its title lines. Everything
         else lives here: the frame loop, fireworks on a persistence layer, the screen shake,
         the title and tagline cards, the prompt box, the footer, the sound synthesis, the
         encode, and the splice onto the narrated movie with its captions shifted.
         The prospector's opening (training/agents/prospector/opening/make_clip.py) is the
         original this was lifted from.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: nothing but the spec; frames are drawn with Pillow and numpy, sound with numpy.
Output: <agent>/opening/opening.mp4 (1280x720, 30 fps, stereo), and with --prepend
        <agent>/<agent>_full.mp4 + <agent>_full.srt (the narrated movie with the opening in
        front, 20 fps, mono AAC like the renderer's; every caption shifted by the opening's
        length). publish.py prefers the _full pair when it exists. index.yaml and
        training/README.md are not touched: add the opening's length to the duration and the
        chapter times by hand.
Usage: python3 training/agents/<agent>/opening/make_clip.py [--stills] [--prepend]
       --stills: write still_NNN.png every half second instead of the movie, to look at.
       --prepend: after rendering, splice the clip onto <agent>_narrated.mp4.
"""
from __future__ import annotations

import math
import random
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SECONDS = 1280, 720, 30, 6
N = FPS * SECONDS
SR = 44100

_FONTS = "/System/Library/Fonts/Supplemental/"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """A system font by file name, or Pillow's default when the file is missing (a Linux box)."""
    for path in (_FONTS + name, "/System/Library/Fonts/" + name, name):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


F_BIG = font("Impact.ttf", 150)
F_MID = font("Arial Black.ttf", 48)
F_MID_SMALL = font("Arial Black.ttf", 36)
F_SMALL = font("Verdana Bold.ttf", 28)
F_MONO = font("Menlo.ttc", 26)
F_TAG = font("Arial Black.ttf", 22)

PALETTES = [
    [(255, 215, 0), (255, 240, 150), (255, 255, 255)],
    [(255, 90, 60), (255, 200, 80), (255, 255, 220)],
    [(90, 170, 255), (200, 230, 255), (255, 255, 255)],
    [(120, 255, 140), (220, 255, 200), (255, 255, 255)],
    [(255, 90, 220), (255, 180, 255), (255, 255, 230)],
    [(255, 215, 0), (255, 170, 40), (255, 255, 200)],
]


def ease_out(a: float, power: int = 2) -> float:
    return 1 - (1 - min(max(a, 0.0), 1.0)) ** power


def clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


# --------------------------------------------------------------------------- fireworks

class Rocket:
    """One firework: a rocket that climbs from the bottom edge, then a burst of particles.
    kind: peony (round), ring (one radius), willow (slow, drooping)."""

    def __init__(self, t0, x, apex_y, palette, size=1.0, kind="peony", rng=None):
        rng = rng or random
        self.t0, self.x, self.apex_y, self.palette, self.size, self.kind = t0, x, apex_y, palette, size, kind
        self.flight = 0.8 + 0.2 * rng.random()
        self.burst_t = t0 + self.flight
        self.particles = None
        self.killed_at = None          # set when something (a librarian, say) stops it early

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

    def step(self, dt, gravity=260.0):
        p = self.particles
        if p is None:
            return
        drag = 0.985 if self.kind != "willow" else 0.96
        p["vx"] *= drag
        p["vy"] = p["vy"] * drag + gravity * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
        p["age"] += dt


class Fireworks:
    """A schedule of rockets drawn on a persistence layer (the glow trails), with their sounds.
    schedule: (t0, x, apex_y, palette index, size, kind) per rocket."""

    def __init__(self, schedule, palettes=PALETTES, seed=11):
        rng = random.Random(seed)
        self.rockets = [Rocket(t0, x, y, palettes[p % len(palettes)], s, k, rng) for t0, x, y, p, s, k in schedule]

    def shakes(self):
        return [(r.burst_t, r.size) for r in self.rockets if r.killed_at is None or r.killed_at > r.burst_t]

    def kill(self, t, fade=0.5):
        """Stop every rocket at time t: bursts fade out over `fade` seconds and sink, unlaunched ones never go."""
        for r in self.rockets:
            if r.t0 >= t:
                r.t0 = r.burst_t = 1e9
            elif r.killed_at is None:
                r.killed_at = t
        self.kill_fade = fade

    def draw(self, trail: Image.Image, t: float, dt: float):
        td = ImageDraw.Draw(trail)
        for r in self.rockets:
            if r.t0 <= t < r.burst_t:
                x, y = r.position(t)
                td.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 230, 160))
                td.line((x, y, x - 2, y + 14), fill=(255, 150, 60), width=2)
            elif t >= r.burst_t:
                if r.particles is None:
                    r.burst()
                killed = r.killed_at is not None and t >= r.killed_at
                r.step(dt, gravity=900.0 if killed else 260.0)
                p = r.particles
                fade = np.clip(1 - p["age"] / p["life"], 0, 1)
                if killed:
                    fade = fade * clamp01(1 - (t - r.killed_at) / self.kill_fade)
                if fade.max() <= 0:
                    continue
                for k in np.nonzero(p["age"] < p["life"])[0]:
                    c = r.palette[p["color"][k]]
                    f = fade[k]
                    if f <= 0:
                        continue
                    s = 2.2 * r.size * (0.6 + f)
                    td.ellipse((p["x"][k] - s, p["y"][k] - s, p["x"][k] + s, p["y"][k] + s), fill=tuple(int(v * f) for v in c))
                if p["age"][0] < 0.12 and not killed:
                    rad = 90 * r.size * (1 - p["age"][0] / 0.12)
                    td.ellipse((r.x - rad, r.apex_y - rad, r.x + rad, r.apex_y + rad), fill=(255, 255, 240))

    def audio(self, left, right, gain=1.0):
        for r in self.rockets:
            if r.t0 > SECONDS:
                continue
            pan = r.x / W
            w = whistle(r.flight * 0.9)
            add(left, int(r.t0 * SR), w, (1 - pan) * 0.9 * gain)
            add(right, int(r.t0 * SR), w, pan * 0.9 * gain)
            if r.killed_at is not None and r.killed_at <= r.burst_t:
                continue
            b = bang(r.size)
            add(left, int(r.burst_t * SR), b, (0.5 + 0.5 * (1 - pan)) * gain)
            add(right, int(r.burst_t * SR), b, (0.5 + 0.5 * pan) * gain)


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


def clink(freqs=((2900, 18), (4100, 22), (5600, 30), (1200, 10)), length=0.35):
    """A short metallic hit: a pickaxe on rock, a hammer on an anvil (longer, lower freqs ring)."""
    n = int(SR * length)
    tt = np.arange(n) / SR
    return sum(np.sin(2 * math.pi * f * tt) * np.exp(-tt * d) for f, d in freqs) * 0.5 \
        + np.random.randn(n) * np.exp(-tt * 90) * 0.6


def anvil():
    """A blacksmith's hammer on an anvil: the hit, then the bell-like ring that carries."""
    return clink(((1180, 2.5), (2360, 3.5), (3600, 6), (640, 4), (5200, 12)), length=1.6) * 1.6


def tone(freq, length, decay=3.0, harmonics=(1.0, 0.4, 0.2), attack=0.01):
    n = int(SR * length)
    tt = np.arange(n) / SR
    env = np.exp(-tt * decay) * (1 - np.exp(-tt / attack))
    return sum(a * np.sin(2 * math.pi * freq * (k + 1) * tt) for k, a in enumerate(harmonics)) * env


def chime(notes=(659.3, 784.0, 1046.5), spacing=0.12, length=1.6):
    """A soft three-note chime, each note a little after the last."""
    n = int(SR * (length + spacing * len(notes)))
    out = np.zeros(n)
    for k, f in enumerate(notes):
        add(out, int(k * spacing * SR), tone(f, length, decay=2.2, harmonics=(1.0, 0.15)), 0.3)
    return out


def noise_burst(length, cutoff=None, decay=8.0, attack=0.01):
    """Filtered noise with an envelope: a shush (cutoff 3000, slow), a swish, a whoosh, a door."""
    n = int(SR * length)
    tt = np.arange(n) / SR
    x = np.random.randn(n)
    if cutoff:
        x = lowpass(x, cutoff) * 4
    return x * np.exp(-tt * decay) * (1 - np.exp(-tt / attack))


def shush(length=0.9):
    """'Shh': a breathy band of noise that swells, holds, and dies away."""
    n = int(SR * length)
    tt = np.arange(n) / SR
    x = np.random.randn(n)
    x = x - lowpass(x, 1800)            # take out the low end: a hiss, not a rumble
    x = lowpass(x, 7000) * 3
    env = np.sin(math.pi * tt / length) ** 0.6
    return x * env * 0.5


def click(length=0.03):
    n = int(SR * length)
    return np.random.randn(n) * np.exp(-np.arange(n) / SR * 400)


def hum(length, freq=120.0, gain=0.15):
    n = int(SR * length)
    tt = np.arange(n) / SR
    env = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (length - tt) / 0.4))
    return (np.sin(2 * math.pi * freq * tt) + 0.5 * np.sin(2 * math.pi * freq * 2 * tt)
            + 0.3 * lowpass(np.random.randn(n), 400) * 4) * env * gain


def glissando(f0, f1, length, gain=0.25):
    """A harp-like sweep from f0 to f1: a run of short plucked notes, each a semitone up."""
    n = int(SR * length)
    out = np.zeros(n)
    steps = int(round(12 * math.log2(f1 / f0)))
    for k in range(steps + 1):
        f = f0 * 2 ** (k / 12)
        at = int(k / max(steps, 1) * (length - 0.5) * SR)
        add(out, at, tone(f, 0.6, decay=4.0, harmonics=(1.0, 0.3, 0.1), attack=0.003), gain)
    return out


def fanfare(start, audio, gain=0.35):
    chords = [(0.0, [261.6, 329.6, 392.0]), (0.35, [293.7, 370.0, 440.0]),
              (0.7, [329.6, 415.3, 493.9, 659.3]), (1.05, [392.0, 493.9, 587.3, 784.0])]
    for off, notes in chords:
        n = int(SR * 1.4)
        tt = np.arange(n) / SR
        env = np.exp(-tt * 1.6) * (1 - np.exp(-tt * 60))
        snd = sum(np.sin(2 * math.pi * f * tt) * (1 / (k + 1)) for k, f in enumerate(notes))
        snd += 0.3 * sum(np.sin(2 * math.pi * 2 * f * tt) for f in notes)
        add(audio, int((start + off) * SR), snd * env, gain)


def add(buf, start, sound, gain):
    start = max(0, int(start))
    end = min(len(buf), start + len(sound))
    if end > start:
        buf[start:end] += sound[: end - start] * gain


# --------------------------------------------------------------------------- drawing helpers

def text_centered(d: ImageDraw.ImageDraw, y, txt, f, fill, shadow=None, x_centre=W / 2):
    bb = d.textbbox((0, 0), txt, font=f)
    x = x_centre - (bb[2] - bb[0]) / 2 - bb[0]
    if shadow:
        d.text((x + 3, y + 3), txt, font=f, fill=shadow)
    d.text((x, y), txt, font=f, fill=fill)


def paste_rgba(frame: Image.Image, layer: Image.Image) -> None:
    frame.paste(layer, (0, 0), layer)


def stick_figure(d: ImageDraw.ImageDraw, x, y, *, shirt, skin=(235, 190, 150), trousers=(40, 40, 70),
                 hair=None, bob=0.0, leg=0.0, arm_r=None, arm_l=None, scale=1.0):
    """A plain cartoon person standing on the ground line y, facing the camera; the arms are
    (angle, length) pairs from the shoulder, in radians, 0 = out to the right. Returns the shoulder points."""
    s = scale
    y = int(y + bob)
    d.line((x - 10 * s, y - 70 * s, x - 18 * s - leg, y), fill=trousers, width=int(14 * s))
    d.line((x + 10 * s, y - 70 * s, x + 18 * s + leg, y), fill=trousers, width=int(14 * s))
    d.rectangle((x - 30 * s - leg, y - 6, x - 6 * s - leg, y + 4), fill=(50, 30, 20))
    d.rectangle((x + 6 * s + leg, y - 6, x + 30 * s + leg, y + 4), fill=(50, 30, 20))
    d.rounded_rectangle((x - 34 * s, y - 150 * s, x + 34 * s, y - 60 * s), radius=int(14 * s), fill=shirt)
    d.ellipse((x - 26 * s, y - 206 * s, x + 26 * s, y - 150 * s), fill=skin)
    d.ellipse((x - 16 * s, y - 196 * s, x - 10 * s, y - 190 * s), fill=(20, 20, 20))
    d.ellipse((x + 10 * s, y - 196 * s, x + 16 * s, y - 190 * s), fill=(20, 20, 20))
    if hair:
        d.chord((x - 27 * s, y - 210 * s, x + 27 * s, y - 170 * s), 180, 360, fill=hair)
    sh_l, sh_r = (x - 30 * s, y - 135 * s), (x + 30 * s, y - 135 * s)
    for (sx, sy), arm in ((sh_r, arm_r), (sh_l, arm_l)):
        if arm is None:
            continue
        ang, L = arm
        ex, ey = sx + L * s * math.cos(ang), sy + L * s * math.sin(ang)
        d.line((sx, sy, ex, ey), fill=shirt, width=int(12 * s))
        d.ellipse((ex - 9 * s, ey - 9 * s, ex + 9 * s, ey + 9 * s), fill=skin)
    return sh_l, sh_r


def clock(d: ImageDraw.ImageDraw, cx, cy, r, hour: float, face=(245, 242, 230), rim=(40, 40, 50)):
    """A wall clock reading `hour` (decimal: 11.0, 8.5, ...)."""
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=face, outline=rim, width=max(3, r // 12))
    for k in range(12):
        a = k * math.pi / 6
        d.line((cx + (r * 0.82) * math.sin(a), cy - (r * 0.82) * math.cos(a), cx + (r * 0.92) * math.sin(a), cy - (r * 0.92) * math.cos(a)),
               fill=rim, width=max(2, r // 20))
    ha = (hour % 12) / 12 * 2 * math.pi
    ma = (hour % 1) * 2 * math.pi
    d.line((cx, cy, cx + r * 0.5 * math.sin(ha), cy - r * 0.5 * math.cos(ha)), fill=rim, width=max(4, r // 10))
    d.line((cx, cy, cx + r * 0.75 * math.sin(ma), cy - r * 0.75 * math.cos(ma)), fill=rim, width=max(3, r // 16))
    d.ellipse((cx - r * 0.06, cy - r * 0.06, cx + r * 0.06, cy + r * 0.06), fill=rim)


def laptop(d: ImageDraw.ImageDraw, x, y, w=260, h=160, screen=(20, 26, 40), body=(70, 74, 86)):
    """A laptop seen from the front, its base on the line y; returns the screen's box."""
    d.rounded_rectangle((x - w / 2 - 10, y - 14, x + w / 2 + 10, y), radius=6, fill=body)
    d.rounded_rectangle((x - w / 2, y - 14 - h, x + w / 2, y - 14), radius=8, fill=(40, 42, 50))
    box = (x - w / 2 + 10, y - 14 - h + 10, x + w / 2 - 10, y - 24)
    d.rectangle(box, fill=screen)
    return box


# --------------------------------------------------------------------------- the opening

class Opening:
    """One agent's six-second opening. Subclass it in <agent>/opening/make_clip.py and set the
    class attributes; override background(), scene(), overlay() and audio() for the gag."""

    agent = "agent"
    title = "THE AGENT"
    tagline = "what it does, in a few words"
    prompt_line = "ask the agent ..."
    footer = "a two-minute training movie · murmurent"
    title_at, tagline_at, prompt_at, footer_at = 2.6, 3.5, 4.3, 5.0
    title_y, tagline_y = 60, 236
    title_colours = ((8, (120, 60, 0, 255)), (4, (255, 170, 0, 255)), (0, (255, 250, 220, 255)))
    tagline_colour, tagline_shadow = (255, 230, 120), (40, 20, 0)
    tagline_font = F_MID          # F_MID_SMALL for a long one
    footer_colour = (255, 235, 160)
    fireworks_schedule = []          # (t0, x, apex_y, palette, size, kind)
    fireworks_gain = 1.0
    glow = True                      # blur the trail layer into a glow
    shakes = []                      # (time, strength) besides the fireworks' own
    seed = 11

    def __init__(self):
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.here = Path(sys.modules[type(self).__module__].__file__).resolve().parent
        self.fireworks = Fireworks(self.fireworks_schedule, seed=self.seed)
        self.setup()

    def setup(self):
        """Build the state that moves between frames (debris, particles); runs once."""

    # ---- things a subclass draws
    def background(self, t: float) -> Image.Image:
        return Image.new("RGB", (W, H), (6, 8, 30))

    def scene(self, frame: Image.Image, t: float, dt: float) -> Image.Image:
        """The characters and the gag, drawn over the background and under the fireworks' glow.
        May return a new frame (after a blend, say) or None to keep the one passed in."""
        return frame

    def overlay(self, frame: Image.Image, t: float, dt: float) -> Image.Image:
        """Drawn after the fireworks and the shake, before the titles: a flash, a stamp, a sign."""
        return frame

    def audio(self, left: np.ndarray, right: np.ndarray) -> None:
        """Add the gag's own sounds to the stereo buffers (SR samples per second)."""

    # ---- the shared parts
    def titles(self, frame: Image.Image, t: float) -> Image.Image:
        d = ImageDraw.Draw(frame)
        if self.title and t >= self.title_at:
            a = min(1.0, (t - self.title_at) / 0.25)
            scale = 1.6 - 0.6 * ease_out(a, 3)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            bb = ld.textbbox((0, 0), self.title, font=F_BIG)
            tw = bb[2] - bb[0]
            for off, col in self.title_colours:
                ld.text(((W - tw) / 2 - bb[0] + off, self.title_y - bb[1] + off), self.title, font=F_BIG, fill=col)
            if scale != 1.0:
                nw, nh = int(W * scale), int(H * scale)
                layer = layer.resize((nw, nh)).crop(((nw - W) // 2, (nh - H) // 2, (nw - W) // 2 + W, (nh - H) // 2 + H))
            paste_rgba(frame, layer)
        if self.tagline and t >= self.tagline_at:
            a = min(1.0, (t - self.tagline_at) / 0.3)
            text_centered(d, self.tagline_y + 30 * (1 - a), self.tagline, self.tagline_font, self.tagline_colour, self.tagline_shadow)
        if self.prompt_line and t >= self.prompt_at:
            a = min(1.0, (t - self.prompt_at) / 0.3)
            bb = d.textbbox((0, 0), self.prompt_line, font=F_MONO)
            tw = bb[2] - bb[0]
            x = (W - tw) / 2
            box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(box).rounded_rectangle((x - 24, 600, x + tw + 24, 664), radius=14, fill=(0, 0, 0, int(200 * a)))
            paste_rgba(frame, box)
            d.text((x, 616), self.prompt_line, font=F_MONO, fill=(int(255 * a),) * 3)
        if self.footer and t >= self.footer_at:
            text_centered(d, 676, self.footer, F_SMALL, self.footer_colour)
        return frame

    def frame(self, i: int, trail: Image.Image):
        t = i / FPS
        dt = 1 / FPS
        frame = self.background(t)
        frame = self.scene(frame, t, dt) or frame
        trail = Image.eval(trail, lambda v: int(v * 0.82))
        self.fireworks.draw(trail, t, dt)
        if self.fireworks.rockets:
            layers = np.asarray(frame, dtype=np.int16) + np.asarray(trail, dtype=np.int16) // 2
            if self.glow:
                layers = layers + np.asarray(trail.filter(ImageFilter.GaussianBlur(6)), dtype=np.int16)
            frame = Image.fromarray(np.clip(layers, 0, 255).astype(np.uint8))
        shake = 0
        for bt, bs in self.fireworks.shakes() + list(self.shakes):
            if 0 <= t - bt < 0.3:
                shake = max(shake, int(10 * bs * (1 - (t - bt) / 0.3)))
        if shake:
            frame = frame.transform((W, H), Image.AFFINE, (1, 0, random.randint(-shake, shake), 0, 1, random.randint(-shake, shake)))
        frame = self.overlay(frame, t, dt) or frame
        return self.titles(frame, t), trail

    def make_audio(self) -> np.ndarray:
        total = SR * (SECONDS + 1)
        left, right = np.zeros(total), np.zeros(total)
        self.fireworks.audio(left, right, self.fireworks_gain)
        self.audio(left, right)
        audio = np.stack([left, right], axis=1)[: SR * SECONDS]
        audio = np.tanh(audio * 1.4)
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio *= 0.89 / peak
        return (audio * 32767).astype(np.int16)

    def render(self, stills: bool = False) -> Path:
        here = self.here
        trail = Image.new("RGB", (W, H), (0, 0, 0))
        if stills:
            for i in range(N):
                frame, trail = self.frame(i, trail)
                if i % 15 == 0:
                    frame.save(here / f"still_{i:03d}.png")
            return here
        frames_dir = here / "frames"
        frames_dir.mkdir(exist_ok=True)
        for i in range(N):
            frame, trail = self.frame(i, trail)
            frame.save(frames_dir / f"f{i:04d}.png")
        wav = here / "sound.wav"
        with wave.open(str(wav), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes(self.make_audio().tobytes())
        out = here / "opening.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%04d.png"),
                        "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
        print(out)
        return out

    def main(self, argv=None) -> None:
        argv = sys.argv[1:] if argv is None else argv
        if "--stills" in argv:
            self.render(stills=True)
            return
        self.render()
        if "--prepend" in argv:
            prepend(self.here.parent, self.agent)


# --------------------------------------------------------------------------- the splice

def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def shift_srt(text: str, seconds: float) -> str:
    def shift(m):
        h, mi, s, ms = (int(x) for x in m.groups())
        total = h * 3600 + mi * 60 + s + ms / 1000 + seconds
        h, rem = divmod(total, 3600)
        mi, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(mi):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    return re.sub(r"(\d\d):(\d\d):(\d\d),(\d\d\d)", shift, text)


def prepend(agent_dir: Path, key: str) -> Path:
    """Splice <agent_dir>/opening/opening.mp4 onto the front of <key>_narrated.mp4, writing
    <key>_full.mp4 and <key>_full.srt (captions shifted by the opening's length)."""
    opening = agent_dir / "opening" / "opening.mp4"
    movie = agent_dir / f"{key}_narrated.mp4"
    srt = agent_dir / f"{key}.srt"
    for p in (opening, movie, srt):
        if not p.exists():
            raise SystemExit(f"missing {p}")
    lead = duration(opening)
    out = agent_dir / f"{key}_full.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(opening), "-i", str(movie),
        "-filter_complex",
        "[0:v]fps=20,format=yuv420p[v0];[0:a]aformat=channel_layouts=mono,aresample=44100[a0];"
        "[1:v]fps=20,format=yuv420p[v1];[1:a]aformat=channel_layouts=mono,aresample=44100[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
    (agent_dir / f"{key}_full.srt").write_text(shift_srt(srt.read_text(), lead))
    print(f"{out.name}: {duration(out):.1f} s (opening {lead:.1f} s); captions shifted in {key}_full.srt")
    return out


if __name__ == "__main__":
    # python3 training/lib/opening.py prepend <agent>: splice an already rendered clip.
    if len(sys.argv) == 3 and sys.argv[1] == "prepend":
        prepend(Path(__file__).resolve().parent.parent / sys.argv[2], sys.argv[2])
    else:
        raise SystemExit(__doc__)
