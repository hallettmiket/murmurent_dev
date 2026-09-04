"""Tests for ``murmurent doctor`` (:mod:`murmurent.commands.doctor_cmd`).

Each test stages one of the ways an install has actually gone wrong and checks
that the doctor names it and names the fix. The commons and ``~/.claude`` are
both redirected into ``tmp_path`` so nothing here touches the real machine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.commands import doctor_cmd, setup_cmd


@pytest.fixture
def commons(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "commons"
    for sub in ("agents", "rules", "skills"):
        (root / sub).mkdir(parents=True)
    (root / "agents" / "oracle.md").write_text("# oracle\n", encoding="utf-8")
    (root / "agents" / "artist.md").write_text("# artist\n", encoding="utf-8")
    (root / "rules" / "headline_first.md").write_text("# rule\n", encoding="utf-8")
    (root / "skills" / "murmurent-push").mkdir()
    (root / "skills" / "murmurent-push" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# claude\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(root))
    # PATH hygiene is a property of the machine running the tests, so it is
    # pinned to OK here and covered by its own test below.
    monkeypatch.setattr(
        doctor_cmd, "check_path_tools",
        lambda: doctor_cmd.Check("path", doctor_cmd.OK, "pinned for tests"),
    )
    return root


def test_path_check_flags_a_stranger_python(monkeypatch, tmp_path):
    stranger = tmp_path / "other" / "bin"
    stranger.mkdir(parents=True)
    (stranger / "pip").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "mine" / "bin" / "python3"))
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "mine"))
    monkeypatch.setattr(
        doctor_cmd.shutil, "which",
        lambda tool: str(stranger / "pip") if tool == "pip" else None,
    )
    check = doctor_cmd.check_path_tools()
    assert check.status == doctor_cmd.WARN
    assert "pip ->" in check.detail
    assert "uv tool install" in check.fix


@pytest.fixture
def cc_dir(tmp_path, monkeypatch) -> Path:
    cc = tmp_path / "claude"
    cc.mkdir()
    monkeypatch.setenv("MURMURENT_CC_DIR", str(cc))
    return cc


def _write_settings(cc: Path, interpreter: str = sys.executable) -> None:
    settings = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write", "hooks": [
                    {"type": "command", "command": f"{interpreter} -m murmurent.hooks.raw_guard"},
                ]},
            ],
        },
        "mcpServers": {"murmurent-oracle": {"command": "x"}},
    }
    (cc / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


def _healthy(commons: Path, cc: Path) -> None:
    setup_cmd.cmd_setup(show_next_step=False)
    _write_settings(cc)


def test_healthy_install_passes(commons, cc_dir):
    _healthy(commons, cc_dir)
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "All checks passed." in result.output
    assert "✗" not in result.output


def test_missing_settings_fails_and_names_the_fix(commons, cc_dir):
    setup_cmd.cmd_setup(show_next_step=False)
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 1
    assert "hooks" in result.output
    assert "murmurent install --hooks" in result.output


def test_nothing_linked_fails(commons, cc_dir):
    _write_settings(cc_dir)
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 1
    assert "agents" in result.output
    assert "murmurent install" in result.output


def test_dangling_commons_link_is_a_warning_with_setup_as_the_fix(commons, cc_dir):
    _healthy(commons, cc_dir)
    gone = cc_dir / "agents" / "receptionist.md"
    gone.symlink_to(commons / "agents" / "receptionist.md")  # target never existed
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "dangling: receptionist.md" in result.output
    assert "murmurent setup" in result.output


def test_hooks_pinned_to_a_vanished_interpreter_fail(commons, cc_dir, tmp_path):
    setup_cmd.cmd_setup(show_next_step=False)
    _write_settings(cc_dir, interpreter=str(tmp_path / "gone" / "bin" / "python3"))
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 1
    assert "no longer exists" in result.output
    assert "murmurent install --hooks" in result.output


def test_dev_clone_pointed_at_release_remote_is_flagged(commons, cc_dir, monkeypatch):
    _healthy(commons, cc_dir)
    (commons / ".git").mkdir()

    def fake_git(root, *args):
        if args[:3] == ("remote", "get-url", "origin"):
            return "git@github.com:hallettmiket/murmurent.git"
        if args[:2] == ("rev-list", "--count"):
            return str(doctor_cmd.RELEASE_HISTORY_MAX + 1)
        return "abc1234"

    monkeypatch.setattr(doctor_cmd, "_git", fake_git)
    check = doctor_cmd.check_clone_remote()
    assert check.status == doctor_cmd.WARN
    assert "remote set-url origin" in check.fix
    assert doctor_cmd.DEV_REMOTE in check.fix


def test_release_clone_at_release_remote_is_fine(commons, cc_dir, monkeypatch):
    (commons / ".git").mkdir()

    def fake_git(root, *args):
        if args[:3] == ("remote", "get-url", "origin"):
            return "git@github.com:hallettmiket/murmurent.git"
        if args[:2] == ("rev-list", "--count"):
            return "6"
        return "abc1234"

    monkeypatch.setattr(doctor_cmd, "_git", fake_git)
    assert doctor_cmd.check_clone_remote().status == doctor_cmd.OK


def test_setup_prunes_dangling_commons_links_only(commons, cc_dir, tmp_path):
    setup_cmd.cmd_setup(show_next_step=False)
    agents = cc_dir / "agents"
    (agents / "receptionist.md").symlink_to(commons / "agents" / "receptionist.md")
    mine = tmp_path / "vault" / "agents" / "mine.md"
    (agents / "mine.md").symlink_to(mine)  # personal link, target absent: stays
    setup_cmd.cmd_setup(show_next_step=False)
    assert not (agents / "receptionist.md").is_symlink()
    assert (agents / "mine.md").is_symlink()
    assert (agents / "oracle.md").is_symlink()
    assert os.readlink(agents / "oracle.md") == str(commons / "agents" / "oracle.md")
