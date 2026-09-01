"""The headline-first verdict table lists every agent in ``agents/`` (issue #130).

``rules/headline_first.md`` is auto-loaded into every session, and the VSCode
BR pane shows only the first 200 characters of a subagent's reply, so the table
that tells each agent what verdict vocabulary to lead with is load-bearing.

It went two agents out of date (``centre_cable_guy``, ``lab_oracle``) and
nothing complained, because both agents declared their verdicts in their own
files. Nothing was broken; the rule was simply silent about them. That is the
project's recurring shape: a hand-maintained list that cannot announce it is
incomplete. Only a comparison against the directory catches it, so here it is.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_RULE = _REPO / "rules" / "headline_first.md"
_AGENTS = _REPO / "agents"

# Rows look like: | `agent_name` | `Verdict / Verdict — <one-line ...>` |
_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|", re.MULTILINE)


def _table_agents() -> set[str]:
    return set(_ROW.findall(_RULE.read_text(encoding="utf-8")))


def _defined_agents() -> set[str]:
    return {p.stem for p in _AGENTS.glob("*.md")}


def test_every_agent_has_a_verdict_row():
    missing = sorted(_defined_agents() - _table_agents())
    assert not missing, (
        f"agents with no row in rules/headline_first.md: {missing}. "
        "Add the row in the same commit as the agent, and take the vocabulary "
        "from the agent's own MANDATORY OUTPUT RULE line."
    )


def test_no_row_names_an_agent_that_does_not_exist():
    stale = sorted(_table_agents() - _defined_agents())
    assert not stale, (
        f"rules/headline_first.md has rows for agents not in agents/: {stale}. "
        "A renamed or removed agent leaves its row behind."
    )


def test_each_row_carries_a_verdict_vocabulary():
    """A row with a name but no verdict words teaches the agent nothing."""
    text = _RULE.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^\|\s*`([a-z_]+)`\s*\|(.*)\|\s*$", line)
        if not m:
            continue
        name, verdict = m.group(1), m.group(2).strip()
        assert "—" in verdict or "-" in verdict, (
            f"`{name}`'s row has no '<verdict> — <why>' shape: {verdict!r}"
        )
        assert re.search(r"[A-Z]", verdict), (
            f"`{name}`'s row names no categorical verb: {verdict!r}"
        )
