"""Tests for the harness registry (phase 0 of docs/harnesses_plan.md): the
profile interface, Claude Code behind it with no change in effect, the lab's
override file, and `murmurent harness list`. No harness is run; nothing
touches the real home folder."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from murmurent.commands import install_cmd
from murmurent.core import commons as _commons
from murmurent.core import harness_claude_code as _cc
from murmurent.core import harness_policy as _hp

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_install_main.json"


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(_hp.HARNESSES_ENV, raising=False)
    # No lab records on the test machine.
    monkeypatch.setattr(_hp, "lab_harnesses_path", lambda env=None: None)
    monkeypatch.delenv(_hp.MACHINE_ENV, raising=False)
    monkeypatch.setattr(_hp, "_machine_file", lambda: tmp_path / ".murmurent" / "machine.yaml")
    return tmp_path


# ---------------------------------------------------------------------------
# The interface
# ---------------------------------------------------------------------------


def test_claude_code_is_a_registered_profile():
    profiles = _hp.profiles()
    assert "claude_code" in profiles
    facts = profiles["claude_code"].facts
    assert facts.place in _hp.PLACES
    assert facts.hooks_can_deny is True
    assert facts.headless == "claude -p"


def test_later_phases_say_which_phase(home):
    profile = _hp.profiles()["claude_code"]
    with pytest.raises(NotImplementedError, match="phase 1"):
        profile.render_rules([], home)
    with pytest.raises(NotImplementedError, match="phase 2"):
        profile.to_event({})
    with pytest.raises(NotImplementedError, match="phase 4"):
        next(profile.read_events(home))


def test_install_paths_and_headless(home):
    profile = _hp.profiles()["claude_code"]
    paths = profile.install_paths(home)
    assert paths.settings == home / ".claude" / "settings.json"
    assert paths.mcp == home / ".claude.json"
    assert paths.agents == home / ".claude" / "agents"
    assert profile.headless_command("hello", "claude-opus-5-5", home) == [
        "claude", "-p", "hello", "--model", "claude-opus-5-5"]
    assert profile.headless_command("hello", "", home) == ["claude", "-p", "hello"]
    stores = profile.transcript_stores(home)
    assert stores[0].root == home / ".claude" / "projects"
    assert stores[0].files() == []


# ---------------------------------------------------------------------------
# Claude Code behind the profile: the same bytes as main wrote
# ---------------------------------------------------------------------------


def test_install_writes_exactly_what_main_wrote(home):
    """The acceptance test of phase 0: with the machine-specific values pinned,
    `murmurent install --hooks` writes the two files main wrote, byte for byte.
    The fixture was captured from main at de17fdf on 2026-11-16."""
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with patch.object(sys, "executable", "/opt/venv/bin/python"), \
         patch.object(_commons, "commons_root", lambda: Path("/opt/murmurent")):
        target = home / ".claude" / "settings.json"
        install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
        assert json.loads(target.read_text(encoding="utf-8")) == expected["settings.json"]
        assert json.loads((home / ".claude.json").read_text(encoding="utf-8")) == expected["claude.json"]


def test_install_cmd_still_exports_the_registrations():
    assert install_cmd.HOOK_REGISTRATIONS is _cc.HOOK_REGISTRATIONS
    assert install_cmd.MCP_REGISTRATIONS is _cc.MCP_REGISTRATIONS
    assert {r["label"] for r in install_cmd.HOOK_REGISTRATIONS} >= {
        "murmurent-raw-guard", "murmurent-protected-paths", "murmurent-audit"}


def test_installed_reports_what_is_missing(home):
    profile = _hp.profiles()["claude_code"]
    state = profile.installed(home)
    assert state.yes is False
    assert "hooks not in" in state.detail and "MCP servers not in" in state.detail
    assert "murmurent install --hooks" in state.detail
    install_cmd.cmd_install(hooks=True, settings_path=home / ".claude" / "settings.json", backup=False)
    (home / ".claude" / "agents").mkdir()
    state = profile.installed(home)
    assert state.yes is True, state.detail


# ---------------------------------------------------------------------------
# The lab's file
# ---------------------------------------------------------------------------


def test_lab_file_overrides_facts_and_reports_mistakes(home, monkeypatch, tmp_path):
    path = tmp_path / "harnesses.yaml"
    path.write_text(yaml.safe_dump({"harnesses": {
        "claude_code": {"place": "lab_server", "models": ["claude-opus-5-5"], "headless": "no"},
        "antigravity": {"place": "google_cloud"},
        "opencode": "later",
        "faraday": {"place": "lab_server"},
    }}), encoding="utf-8")
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(path))
    policy = _hp.load_harnesses()
    cc = policy.harnesses["claude_code"]
    assert cc.place == "lab_server"
    assert cc.models == ("claude-opus-5-5",)
    assert cc.headless == "claude -p"
    text = "\n".join(policy.problems)
    assert "'headless' cannot be changed by the lab" in text
    assert policy.harnesses["antigravity"].place == "google_cloud"
    assert "'faraday' is not a harness murmurent knows" in text
    assert "'opencode' is not a harness murmurent knows" in text
    assert str(path) in policy.sources


def test_a_wrong_place_keeps_the_profiles(home, monkeypatch, tmp_path):
    path = tmp_path / "harnesses.yaml"
    path.write_text("harnesses:\n  claude_code:\n    place: the_moon\n", encoding="utf-8")
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(path))
    policy = _hp.load_harnesses()
    assert policy.harnesses["claude_code"].place == "anthropic_cloud"
    assert any("the_moon" in p for p in policy.problems)


def test_a_missing_override_file_is_a_problem_not_a_crash(home, monkeypatch, tmp_path):
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(tmp_path / "nope.yaml"))
    policy = _hp.load_harnesses()
    assert "claude_code" in policy.harnesses
    assert any("does not exist" in p for p in policy.problems)


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_harness_list_table_and_json(home):
    from murmurent.commands.harness_cmd import harness_group

    runner = CliRunner()
    res = runner.invoke(harness_group, ["list"])
    assert res.exit_code == 0, res.output
    assert "harness" in res.output.splitlines()[0]
    assert "claude_code" in res.output and "anthropic_cloud" in res.output
    assert "not on this machine" in res.output or "not installed: hooks not in" in res.output

    res = runner.invoke(harness_group, ["--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    row = data["harnesses"][0]
    assert row["name"] == "claude_code"
    assert row["installed"] is False
    assert row["paths"]["settings"].endswith("settings.json")
    assert data["chosen"] == []
    assert data["problems"] == []


def test_harness_list_prints_problems_on_stderr_and_exits_0(home, monkeypatch, tmp_path):
    from murmurent.commands.harness_cmd import harness_group

    path = tmp_path / "harnesses.yaml"
    path.write_text("harnesses:\n  faraday:\n    place: lab_server\n", encoding="utf-8")
    monkeypatch.setenv(_hp.HARNESSES_ENV, str(path))
    res = CliRunner().invoke(harness_group, ["list"])
    assert res.exit_code == 0
    assert "problem:" in res.stderr and "faraday" in res.stderr
    assert "claude_code" in res.stdout


def test_cli_registers_harness_and_harnesses():
    from murmurent.cli import cli

    assert "harness" in cli.commands and "harnesses" in cli.commands
