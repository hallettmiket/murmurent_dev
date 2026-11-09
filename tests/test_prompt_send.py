"""
Purpose: Tests for ``murmurent prompt``: prompts written in a vault file are
         split into blocks, the latest is sent (clipboard, paste or tmux,
         faked here) and recorded under sessions/<date>/sent.md.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp vault.
Output:  Assertions.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from click.testing import CliRunner

from murmurent.core import lab_notebook as _nb
from murmurent.core import prompt_send as ps


def _vault(tmp_path, monkeypatch) -> _nb.NotebookPaths:
    root = tmp_path / "vault"
    (root / "lab-notebook").mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_VAULT_ROOT", str(root))
    return _nb.require_paths()


def test_blocks_skip_heading_and_help_and_send_marker():
    text = "# Prompts, 2026-11-07\n\nOne prompt per block; a line `---` ends a block.\n\n---\n\nfirst prompt\n\n--- send\n\nsecond\nprompt\n"
    assert ps.blocks(text) == ["first prompt", "second\nprompt"]


def test_send_copies_pastes_and_records(tmp_path, monkeypatch):
    paths = _vault(tmp_path, monkeypatch)
    calls = {}
    sent = ps.send("ask the blacksmith to count the bands", paths=paths, to="Claude",
                   now=_dt.datetime(2026, 11, 7, 9, 30),
                   clipboard=lambda t: calls.setdefault("clip", t),
                   paster=lambda app: calls.setdefault("paste", app),
                   tmux=lambda pane, t: calls.setdefault("tmux", pane))
    assert calls == {"clip": "ask the blacksmith to count the bands", "paste": "Claude"}
    assert sent.record == paths.vault / "sessions" / "2026-11-07" / "sent.md"
    body = sent.record.read_text()
    assert "ask the blacksmith to count the bands" in body and "09:30" in body


def test_send_to_tmux_and_no_paste(tmp_path, monkeypatch):
    paths = _vault(tmp_path, monkeypatch)
    calls = {}
    ps.send("x", paths=paths, tmux_pane="main:1.0", clipboard=lambda t: None,
            paster=lambda a: calls.setdefault("paste", a), tmux=lambda pane, t: calls.setdefault("tmux", pane))
    assert calls == {"tmux": "main:1.0"}
    s = ps.send("y", paths=paths, paste=False, clipboard=lambda t: None,
                paster=lambda a: calls.setdefault("paste2", a), tmux=lambda p, t: None)
    assert s.pasted_to == "" and "paste2" not in calls


def test_cli_new_and_send_latest_block(tmp_path, monkeypatch):
    from murmurent.cli import cli
    paths = _vault(tmp_path, monkeypatch)
    monkeypatch.setattr(ps, "copy_to_clipboard", lambda t: None)
    monkeypatch.setattr(ps, "paste_into_app", lambda app: None)
    monkeypatch.setattr(ps, "send_to_tmux", lambda pane, t: None)
    r = CliRunner()
    out = r.invoke(cli, ["prompt", "new", "--no-open"])
    assert out.exit_code == 0, out.output
    path = Path(out.output.strip())
    assert path.exists() and path.parent.name == "prompts"
    path.write_text(path.read_text() + "ask the oracle what I noted about gel 27\n\n---\n\nsecond one\n")
    out = r.invoke(cli, ["prompt", "send", "--file", str(path), "--no-paste"])
    assert out.exit_code == 0, out.output
    assert "sent (10 characters" in out.output and "sessions/" in out.output
    out = r.invoke(cli, ["prompt", "send", "--text", "hello there"])
    assert out.exit_code == 0 and "pasted into Claude" in out.output
    # --quiet prints nothing on success, so an Obsidian hotkey set to replace the selection
    # clears the prompt from the note; the record is still written.
    out = r.invoke(cli, ["prompt", "send", "--quiet", "--text", "clear me after sending"])
    assert out.exit_code == 0 and out.output == ""
    assert any("clear me after sending" in f.read_text() for f in (paths.vault / "sessions").rglob("*.md"))
