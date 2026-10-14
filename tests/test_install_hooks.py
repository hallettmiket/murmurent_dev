"""Tests for :mod:`murmurent.commands.install_cmd`."""

from __future__ import annotations

import json

from murmurent.commands import install_cmd


def test_install_writes_settings(tmp_path):
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    assert "hooks" in settings
    pre_entries = settings["hooks"]["PreToolUse"]
    matchers = [e["matcher"] for e in pre_entries]
    assert any("Write|Edit|Bash|NotebookEdit" in m for m in matchers)
    assert "murmurent-inventory" in settings["mcpServers"]


def test_install_idempotent(tmp_path):
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    first = target.read_text(encoding="utf-8")
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    second = target.read_text(encoding="utf-8")
    assert first == second


def test_install_preserves_unrelated(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps({"theme": "dark", "hooks": {"Stop": [{"matcher": ".*", "hooks": []}]}}),
        encoding="utf-8",
    )
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    assert "Stop" in settings["hooks"]
    assert "PreToolUse" in settings["hooks"]


def test_install_turns_the_feedback_survey_off(tmp_path):
    """#154: the survey interrupts sessions; murmurent sets it off by default."""
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    assert settings["env"]["CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY"] == "1"


def test_install_keeps_a_members_own_survey_choice(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps({"env": {"CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "0", "OTHER": "x"}}),
        encoding="utf-8",
    )
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    env = json.loads(target.read_text(encoding="utf-8"))["env"]
    assert env == {"CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "0", "OTHER": "x"}
