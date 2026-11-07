"""
Purpose: The "Videos and news" section of both READMEs is generated from
         training/index.yaml by training/front_page.py; this test fails when
         someone edits the section by hand or changes the index without
         re-running the script.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   training/index.yaml, README.md, release/README_public.md.
Output:  Assertions.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _front_page():
    spec = importlib.util.spec_from_file_location("front_page", ROOT / "training" / "front_page.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_readme_sections_match_the_index():
    fp = _front_page()
    section = fp.readme_section(fp.load())
    for readme in fp.READMES:
        text = readme.read_text()
        assert fp.START in text and fp.END in text, f"{readme.name} has no generated section"
        assert section.strip() in text, f"{readme.name}: run python3 training/front_page.py"


def test_index_lists_every_agent_movie_and_news_has_dates():
    fp = _front_page()
    d = fp.load()
    assert len(d["movies_in_order"]) >= 16
    for n in d["news"]:
        assert n.get("date") and n.get("title")
    for v in d["videos"]:
        assert v.get("page", "").startswith("https://")
    assert fp.EM_DASH not in fp.readme_section(d) if hasattr(fp, "EM_DASH") else "—" not in fp.readme_section(d)
