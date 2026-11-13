#!/usr/bin/env python3
"""
Purpose: Splice the six-second opening (opening.mp4, from make_clip.py) onto the
         front of the prospector's narrated movie, and shift its captions to match.
         The work is done by training/lib/opening.py (prepend), shared with every
         agent's opening; this file stays so the documented command keeps working.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-13
Input: opening.mp4 here; ../prospector_narrated.mp4 and ../prospector.srt from the renderer.
Output: ../prospector_full.mp4 and ../prospector_full.srt (every caption 6 s later).
Usage: python3 training/agents/prospector/opening/prepend.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from lib.opening import prepend  # noqa: E402

if __name__ == "__main__":
    prepend(HERE.parent, "prospector")
