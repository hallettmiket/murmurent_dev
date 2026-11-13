#!/usr/bin/env python3
"""
Purpose: Splice the six-second opening (opening.mp4, from make_clip.py) onto the
         front of the prospector's narrated movie, and shift its captions to match.
         The renderer's own outputs are left as they are; this writes the pair the
         website shows.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: opening.mp4 here; ../prospector_narrated.mp4 and ../prospector.srt from the renderer.
Output: ../prospector_full.mp4 (opening + movie, 20 fps, mono AAC like the renderer's)
        and ../prospector_full.srt (every caption 6 s later). publish.py prefers the
        _full pair when it exists. index.yaml and training/README.md are not touched:
        add the opening's length to the duration and chapter times by hand.
Usage: python3 training/agents/prospector/opening/prepend.py
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
OPENING = HERE / "opening.mp4"
MOVIE = AGENT / "prospector_narrated.mp4"
SRT = AGENT / "prospector.srt"


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


def main() -> None:
    for p in (OPENING, MOVIE, SRT):
        if not p.exists():
            raise SystemExit(f"missing {p}")
    lead = duration(OPENING)
    out = AGENT / "prospector_full.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(OPENING), "-i", str(MOVIE),
        "-filter_complex",
        "[0:v]fps=20,format=yuv420p[v0];[0:a]aformat=channel_layouts=mono,aresample=44100[a0];"
        "[1:v]fps=20,format=yuv420p[v1];[1:a]aformat=channel_layouts=mono,aresample=44100[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)
    (AGENT / "prospector_full.srt").write_text(shift_srt(SRT.read_text(), lead))
    print(f"{out.name}: {duration(out):.1f} s (opening {lead:.1f} s); captions shifted in prospector_full.srt")


if __name__ == "__main__":
    main()
