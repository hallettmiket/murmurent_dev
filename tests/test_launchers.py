"""Tests for the dashboard's Claude Code terminal launcher."""

from __future__ import annotations

from pathlib import Path

from murmurent.dashboard import launchers as L


def test_the_window_is_named_after_the_folder(tmp_path):
    assert L.session_title(str(tmp_path / "survival")) == "Claude Code · survival"
    assert L.session_title(str(Path.home())) == "Claude Code · home"


def _capture_mac_launch(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(L, "_session_running", lambda prefix: False)
    monkeypatch.setattr(L.subprocess, "Popen", lambda argv, **kw: calls.append(argv))
    res = L.launch_claude_session(cwd=str(tmp_path))
    return res, calls


def test_a_mac_session_sets_the_title_and_keeps_claude_from_renaming_it(monkeypatch, tmp_path):
    res, calls = _capture_mac_launch(monkeypatch, tmp_path)
    assert res["launched"]
    osa = calls[0][2]
    assert f"Claude Code · {tmp_path.name}" in osa
    assert "CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1" in osa
    # AppleScript needs each backslash doubled inside its string.
    assert "\\\\033]0;" in osa and '"' not in osa.split('do script "', 1)[1].split('"\n')[0]


def test_an_open_session_raises_its_own_window(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(L.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(L, "_session_running", lambda prefix: True)
    monkeypatch.setattr(L.subprocess, "Popen", lambda argv, **kw: calls.append(argv))
    res = L.launch_claude_session(cwd=str(tmp_path))
    assert res["already_open"] and not res["launched"]
    assert f'first window whose name contains "Claude Code · {tmp_path.name}"' in calls[0][2]
