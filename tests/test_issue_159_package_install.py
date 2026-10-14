"""
Purpose: Guard the three install gaps a PyPI (uv tool) install hit in #159.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: pyproject.toml; install_cmd and setup_cmd run against tmp_path
Output: pytest assertions

1. mcp 2.x renamed FastMCP, and all four murmurent MCP servers crashed on start
   for anyone whose install resolved it. The dependency is capped below 2.
2. The agent-activity hook pointed at ~/repos/murmurent/scripts/, which only a
   clone has. It now resolves through commons_root(), and a re-install replaces
   the old broken entry instead of adding a second one beside it.
3. `murmurent setup` linked agents, rules and skills but not output styles.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from murmurent.commands import install_cmd, setup_cmd

REPO = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = "scripts/murmurent_log_agent_event.sh"


def test_mcp_dependency_is_capped_below_2() -> None:
    deps = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["dependencies"]
    mcp = [d for d in deps if d.replace(" ", "").startswith("mcp>")]
    assert mcp, "mcp is no longer a dependency"
    assert "<2" in mcp[0], (
        "mcp must stay below 2.0 until the servers are ported: mcp 2.x has no "
        "mcp.server.fastmcp.FastMCP and every murmurent MCP server crashes on start"
    )


@pytest.fixture
def commons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "commons"
    for sub in ("agents", "rules", "skills", "output_styles", "scripts"):
        (root / sub).mkdir(parents=True)
    (root / "agents" / "oracle.md").write_text("# oracle\n", encoding="utf-8")
    (root / "output_styles" / "plain_english.md").write_text("# style\n", encoding="utf-8")
    (root / HOOK_SCRIPT).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(root))
    # A clone path that does not exist: the machine has never cloned murmurent.
    monkeypatch.setenv("MURMURENT_REPO_ROOT", str(tmp_path / "no_clone_here"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / "home").mkdir()
    return root


def _agent_hook_commands(settings: dict) -> list[str]:
    return [
        h["command"]
        for event in ("PreToolUse", "SubagentStop")
        for entry in settings["hooks"].get(event, [])
        for h in entry["hooks"]
        if "murmurent_log_agent_event" in h["command"]
    ]


def test_agent_hook_points_at_the_commons_not_a_clone(commons: Path, tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    commands = _agent_hook_commands(json.loads(target.read_text(encoding="utf-8")))
    assert len(commands) == 2
    for cmd in commands:
        assert str(commons / HOOK_SCRIPT) in cmd
        assert "no_clone_here" not in cmd


def test_reinstall_replaces_a_stale_clone_path(commons: Path, tmp_path: Path) -> None:
    """The settings Vanessa had: hook entries naming a clone that never existed."""
    stale = "/home/someone/repos/murmurent/scripts/murmurent_log_agent_event.sh"
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Agent",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": stale,
                                    "name": "murmurent-agent-report-pre",
                                }
                            ],
                        }
                    ],
                    "SubagentStop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": stale,
                                    "name": "murmurent-agent-report-stop",
                                }
                            ]
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    commands = _agent_hook_commands(json.loads(target.read_text(encoding="utf-8")))
    assert len(commands) == 2, f"stale entry kept beside the new one: {commands}"
    assert all(stale not in c for c in commands)


def test_setup_links_output_styles(commons: Path, tmp_path: Path, monkeypatch) -> None:
    cc = tmp_path / "claude"
    monkeypatch.setenv("MURMURENT_CC_DIR", str(cc))
    assert setup_cmd.cmd_setup(show_next_step=False) == 0
    link = cc / "output-styles" / "plain_english.md"
    assert link.is_symlink()
    assert link.resolve() == (commons / "output_styles" / "plain_english.md").resolve()
