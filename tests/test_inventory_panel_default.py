"""
Purpose: The dashboard's Repositories panel shows repositories that are on
         GitHub but not cloned on this computer by default; the toggle hides
         them. On any one laptop that is the normal state of most of a lab's
         repositories, so hiding them answered "what does the lab have?" with
         "what is on this computer".
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   docs/designer_dashboard/hifi-app.jsx, read as text.
Output:  pass or fail.
"""
from __future__ import annotations

import re
from pathlib import Path

JSX = Path(__file__).resolve().parents[1] / "docs" / "designer_dashboard" / "hifi-app.jsx"


def test_repos_not_cloned_here_are_shown_by_default():
    text = JSX.read_text(encoding="utf-8")
    m = re.search(r"const \[showAllGithub, setShowAllGithub\] = useState\((\w+)\);", text)
    assert m is not None, "the toggle's state is gone or renamed"
    assert m.group(1) == "true"
    assert 'include {stats ? stats.ghOnly : "?"} repos not cloned here' in text
    assert 'Shown only with "include GitHub-only rows"' not in text
