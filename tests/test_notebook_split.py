"""
Purpose: Tests for `murmurent notebook split` (#292): prompt-shaped blocks
         leave the day's entry for sessions/<date>/pasted.md, the original
         is kept under obsolete/, fenced code is never cut, nothing is
         deleted, and the oracle's sessions tier sees the result.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp vault.
Output:  Assertions.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import lab_notebook as nb
from murmurent.mcp import oracle_server as srv

PROMPT = (
    "Please read the three issues and implement the design. You should honour every "
    "pushback point, and you must not push or open a pull request. When you are done, "
    "tell me what you left out and why, and run the tests before you report back to me."
)
NOTE = "Gel of sample 27 ran clean; band at 40 kDa as expected.\n"
CODE = "```python\nx = 1\n\ny = 2\n```\n"


def _vault(tmp_path: Path, monkeypatch) -> Path:
    vault = tmp_path / "vault"
    (vault / "lab-notebook").mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_VAULT_ROOT", str(vault))
    monkeypatch.delenv("MURMURENT_NOTEBOOK_DIR", raising=False)
    monkeypatch.delenv("MURMURENT_SESSIONS_DIR", raising=False)
    monkeypatch.setenv("MURMURENT_NO_VAULT_PULL", "1")
    return vault


def test_looks_like_prompt():
    assert nb.looks_like_prompt(PROMPT)
    assert not nb.looks_like_prompt(NOTE)
    assert not nb.looks_like_prompt("you " * 20)  # short
    assert not nb.looks_like_prompt("# " + PROMPT)  # a heading is never moved


def test_split_blocks_keeps_fenced_code_whole():
    blocks = nb.split_blocks(NOTE + "\n" + CODE + "\n" + PROMPT + "\n")
    assert len(blocks) == 3
    assert blocks[1].startswith("```python") and "y = 2" in blocks[1]
    assert "".join(blocks) == NOTE + "\n" + CODE + "\n" + PROMPT + "\n"


def test_split_moves_prompts_keeps_notes_and_original(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    entry = vault / "lab-notebook" / "2026-10-03.md"
    entry.write_text(
        "---\ndate: 2026-10-03\nproject: p_demo\nsensitivity: standard\ntags: [gel]\n---\n\n"
        + NOTE + "\n" + PROMPT + "\n\n" + CODE + "\n" + PROMPT.replace("three", "two") + "\n",
        encoding="utf-8")
    (vault / "lab-notebook" / "2026-10-04.md").write_text("Only notes today.\n", encoding="utf-8")
    paths = nb.resolve_paths()
    moves = nb.plan_split(paths)
    assert [m.entry.name for m in moves] == ["2026-10-03.md"]
    assert len(moves[0].blocks) == 2
    report = nb.apply_split(paths, moves)
    assert len(report) == 1 and "moved 2 block(s)" in report[0]

    kept = entry.read_text(encoding="utf-8")
    assert NOTE.strip() in kept and "y = 2" in kept
    assert "honour every" not in kept
    assert "project: p_demo" in kept
    assert "[[sessions/2026-10-03/pasted]]" in kept

    pasted = vault / "sessions" / "2026-10-03" / "pasted.md"
    text = pasted.read_text(encoding="utf-8")
    assert text.count("honour every") == 2
    assert "audience: me" in text and "stream: sessions" in text
    assert "[[lab-notebook/2026-10-03]]" in text

    original = vault / "obsolete" / "lab-notebook" / "2026-10-03.md"
    assert original.read_text(encoding="utf-8").count("honour every") == 2
    # nothing deleted, untouched entry untouched
    assert (vault / "lab-notebook" / "2026-10-04.md").read_text(encoding="utf-8") == "Only notes today.\n"
    # running again finds nothing and never overwrites the obsolete copy
    assert nb.plan_split(paths) == []


def test_named_entry_without_date_uses_frontmatter_date(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    (vault / "lab-notebook" / "meeting_with_x.md").write_text(
        "---\ndate: 2026-09-09\n---\n\nAgenda.\n\n" + PROMPT + "\n", encoding="utf-8")
    moves = nb.plan_split(nb.resolve_paths())
    assert moves[0].date == "2026-09-09"
    assert moves[0].target == vault / "sessions" / "2026-09-09" / "pasted.md"


def test_cli_dry_run_writes_nothing(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    (vault / "lab-notebook" / "2026-10-03.md").write_text(NOTE + "\n" + PROMPT + "\n", encoding="utf-8")
    res = CliRunner().invoke(cli, ["notebook", "split", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Would move" in res.output and "2026-10-03.md" in res.output
    assert not (vault / "sessions").exists()
    res = CliRunner().invoke(cli, ["notebook", "split"])
    assert res.exit_code == 0, res.output
    assert (vault / "sessions" / "2026-10-03" / "pasted.md").exists()
    assert "nothing was deleted" in res.output


def test_cli_without_a_vault_explains(tmp_path, monkeypatch):
    monkeypatch.delenv("MURMURENT_VAULT_ROOT", raising=False)
    monkeypatch.setattr(nb, "vault_root", lambda: None)
    res = CliRunner().invoke(cli, ["notebook", "split"])
    assert res.exit_code == 1
    assert "no personal vault" in res.output


# ---------------------------------------------------------------------------
# The oracle's sessions tier
# ---------------------------------------------------------------------------


def test_oracle_sessions_kind_and_all_puts_notes_first(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    notebook = vault / "lab-notebook"
    (notebook / "2026-11-06.md").write_text("# Gel day\n\nThe gel of the 27th looked fine.\n",
                                            encoding="utf-8")
    sessions = vault / "sessions" / "2026-11-07"
    sessions.mkdir(parents=True)
    (sessions / "abc.md").write_text(
        "---\ntitle: Claude Code session abc on 2026-11-07\ndate: 2026-11-07\nproject: p_demo\n"
        "sensitivity: standard\ntags: [session]\nsources: []\n---\n\n## 10:00:00\n\n```text\n"
        "Plot the gel of the 27th again.\n```\n", encoding="utf-8")
    (sessions / "nofm.md").write_text("## 11:00:00\n\nno frontmatter here, gel\n", encoding="utf-8")
    monkeypatch.setattr(srv, "_safe_notebook_dir", lambda: notebook)
    monkeypatch.setattr(srv, "_safe_personal_dir", lambda: None)
    monkeypatch.setattr(srv, "_safe_lab_dir", lambda: None)

    rows = srv.tool_list("sessions")
    assert {r["kind"] for r in rows} == {"sessions"}
    assert {r["path"] for r in rows} == {str(sessions / "abc.md"), str(sessions / "nofm.md")}
    by_path = {r["path"]: r for r in rows}
    assert by_path[str(sessions / "nofm.md")]["date"] == "2026-11-07"   # from the folder
    assert by_path[str(sessions / "abc.md")]["project"] == "p_demo"
    assert by_path[str(sessions / "abc.md")]["audience"] == ["me"]

    assert all(r["kind"] == "notebook" for r in srv.tool_list("notebook"))

    hits = srv.tool_search("gel", kind="all")
    assert [h["kind"] for h in hits] == ["notebook", "sessions", "sessions"]
    assert hits[0]["title"] == "Gel day"
    assert [r["kind"] for r in srv.tool_list("all")][0] == "notebook"

    got = srv.tool_get(str(sessions / "abc.md"))
    assert got["kind"] == "sessions" and "Plot the gel" in got["body"]
    assert srv.tool_search("gel", kind="sessions") and srv.tool_search("gel", kind="notebook")
