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


def _hooks_by_name(settings: dict) -> dict[str, dict]:
    """Every written hook, keyed by its ``name`` (the registration label)."""
    found = {}
    for entries in settings["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                found[hook["name"]] = hook
    return found


def test_data_root_guards_fail_closed(tmp_path):
    """#354 item 2: a guard that cannot start refuses the call instead of
    letting it through. Only the three data-root guards carry
    ``onFailure: block``; a logging or verdict hook that fails must never
    block a member's work."""
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    hooks = _hooks_by_name(json.loads(target.read_text(encoding="utf-8")))
    guards = {
        "murmurent-raw-guard",
        "murmurent-protected-paths",
        "murmurent-data-root-guard",
    }
    for name in guards:
        assert hooks[name]["onFailure"] == "block", name
    for name, hook in hooks.items():
        if name not in guards:
            assert "onFailure" not in hook, name


def test_reinstall_adds_on_failure_to_an_existing_guard(tmp_path):
    """An entry written by an older installer (no ``onFailure``) is replaced
    in place, not duplicated, and a further install changes nothing."""
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    for entry in settings["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            hook.pop("onFailure", None)
    target.write_text(json.dumps(settings), encoding="utf-8")

    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    after = json.loads(target.read_text(encoding="utf-8"))
    names = [h["name"] for e in after["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert names.count("murmurent-raw-guard") == 1
    assert _hooks_by_name(after)["murmurent-raw-guard"]["onFailure"] == "block"
    once = target.read_text(encoding="utf-8")
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    assert target.read_text(encoding="utf-8") == once
