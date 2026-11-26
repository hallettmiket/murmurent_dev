"""
Purpose: Validate the ported agent registry and the loader in ``murmurent.core.agents``.
Author: Mike Hallett (with Claude Code)
Date: 2026-05-06
Input: ``agents/`` directory at the repo root + synthetic agent files for negative tests.
Output: pytest cases asserting all eight agents load with valid frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.core.agents import (
    VALID_CATEGORY_VALUES,
    VALID_FREEZE_VALUES,
    load_agent,
    load_registry,
)
from murmurent.core.frontmatter import FrontmatterError

REPO_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
# receptionist was deprecated in #38 (its only surface, the inbound-SEA
# dashboard panel, was removed; the SEA backend stays but dormant).
EXPECTED_AGENTS = {
    "adversary",
    "artist",
    "blacksmith",
    "bookworm",
    "millwright",
    "centre_millwright",
    "clerk",
    "conscience",
    "detective",
    "docent",
    "judge",
    "lab_oracle",
    "oracle",
    "prospector",
    "lookout",
    "registrar",
    "lawyer",
    "scribe",
    "security_guard",
    "teacher",
}

# Commons-agent categories (#38). The rest default to "member".
EXPECTED_CATEGORY = {
    "registrar": "administrative",
    "centre_millwright": "administrative",
    "clerk": "administrative",
    "lookout": "administrative",
    "judge": "choreography-support",
}


def test_registry_contains_all_expected_agents() -> None:
    registry = load_registry(REPO_AGENTS_DIR)
    names = {record.name for record in registry}
    assert names == EXPECTED_AGENTS


def test_each_agent_has_required_new_fields() -> None:
    for record in load_registry(REPO_AGENTS_DIR):
        assert record.freeze in VALID_FREEZE_VALUES, record
        assert record.category in VALID_CATEGORY_VALUES, record
        assert isinstance(record.required_tools, tuple)
        assert isinstance(record.denied_tools, tuple)
        assert isinstance(record.defaults, dict)
        assert record.description, f"{record.name} missing description"


def test_agent_categories_match_expected() -> None:
    registry = {r.name: r for r in load_registry(REPO_AGENTS_DIR)}
    for name, record in registry.items():
        assert record.category == EXPECTED_CATEGORY.get(name, "member"), name


def test_descriptions_dropped_the_verdict_boilerplate() -> None:
    """The "MUST: first line…" prefix was removed from every description in #38;
    the rule lives in rules/headline_first.md + each agent body, not the blurb."""
    for record in load_registry(REPO_AGENTS_DIR):
        assert "MUST: first line" not in record.description, record.name


def test_load_agent_rejects_invalid_category(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\nname: bad\nfreeze: personal\ncategory: purple\n---\n\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(FrontmatterError):
        load_agent(bad)


def test_security_guard_is_frozen() -> None:
    registry = {r.name: r for r in load_registry(REPO_AGENTS_DIR)}
    assert registry["security_guard"].freeze == "frozen"
    assert "WebFetch" in registry["security_guard"].denied_tools


def test_load_agent_rejects_invalid_freeze(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\nname: bad\nfreeze: blue\n---\n\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(FrontmatterError):
        load_agent(bad)


# --- Which agent works where, and optional helpers (rules/optional_helpers.md) ---

HARNESSES = ("claude_code", "antigravity", "faraday")
HARNESS_STATUSES = {"verified", "degraded", "untested"}

# Plugins, skills and connectors from outside the commons that an agent may
# use when present. An agent may name one only under "## Optional helpers".
OUTSIDE_HELPERS = (
    "deep-research", "ip-legal", "`Legal` plugin", "Research Desk", "Bio Research",
    "`pubmed` plugin", "PubMed connector", "claude-security",
    "Artifact tool", "claude.ai artifact",
)


def _front_matter_and_body(path: Path) -> tuple[dict, str]:
    import yaml
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---", 4)
    return yaml.safe_load(text[4:end]) or {}, text[end + 4:]


def test_every_agent_declares_its_harnesses() -> None:
    for path in sorted(REPO_AGENTS_DIR.glob("*.md")):
        fm, _ = _front_matter_and_body(path)
        block = fm.get("harnesses")
        assert isinstance(block, dict), f"{path.stem}: no harnesses block"
        for h in HARNESSES:
            entry = block.get(h)
            assert isinstance(entry, dict), f"{path.stem}: no entry for {h}"
            assert entry.get("status") in HARNESS_STATUSES, (path.stem, h, entry)
            assert entry.get("checked"), f"{path.stem}/{h}: no checked date"
            if entry["status"] == "verified":
                assert entry.get("evidence"), f"{path.stem}/{h}: verified without evidence"
                ev = REPO_AGENTS_DIR.parent / entry["evidence"]
                assert ev.exists(), f"{path.stem}/{h}: evidence {entry['evidence']} missing"
            if entry["status"] == "degraded":
                assert entry.get("note"), f"{path.stem}/{h}: degraded without a note"


def test_outside_helpers_only_under_optional_helpers() -> None:
    heading = "## Optional helpers"
    for path in sorted(REPO_AGENTS_DIR.glob("*.md")):
        fm, body = _front_matter_and_body(path)
        assert "helpers" not in fm, f"{path.stem}: helpers belong in the body, not front matter"
        if heading in body:
            before, after = body.split(heading, 1)
            # The section ends at the next level-two heading.
            rest = after.split("\n## ", 1)
            section, outside = rest[0], before + (rest[1] if len(rest) > 1 else "")
        else:
            section, outside = "", body
        for helper in OUTSIDE_HELPERS:
            assert helper not in outside, (
                f"{path.stem} names {helper!r} outside its '## Optional helpers' section")


def test_harness_matrix_script_runs(tmp_path: Path) -> None:
    import subprocess, sys
    runs = tmp_path / "runs.tsv"
    runs.write_text("2026-11-22\tclaude_code\tclaude-x\tlawyer\tClear\n", encoding="utf-8")
    script = REPO_AGENTS_DIR.parent / "scripts" / "harness_matrix.py"
    out = subprocess.run([sys.executable, str(script), "--agents", str(REPO_AGENTS_DIR),
                          "--runs", str(runs)], capture_output=True, text=True, check=True).stdout
    assert "| lawyer |" in out and "1 run recorded" in out
