"""
Purpose: Guard issue #156: every install route gets a working dashboard icon.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: core/launcher.py, the CLI, run against a temporary home folder
Output: pytest assertions

The old icon came from two shell scripts that ``cd`` into a repository folder
and ran ``uv run murmurent``. A PyPI install has neither the scripts nor a
folder to ``cd`` into, so it got no icon. The launcher now runs the installed
``murmurent`` by its full path.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.commands import doctor_cmd
from murmurent.core import launcher as L

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: h)
    return h


def test_linux_icon_runs_the_installed_program(home: Path) -> None:
    res = L.create(platform=L.LINUX)
    desktop = home / ".local/share/applications/murmurent-dashboard.desktop"
    script = home / ".local/share/murmurent/murmurent-dashboard-launcher.sh"
    assert res.present and res.location == desktop
    entry = desktop.read_text(encoding="utf-8")
    assert f"Exec={script}" in entry and "Name=Murmurent Dashboard" in entry
    body = script.read_text(encoding="utf-8")
    assert f'PROGRAM="{L.murmurent_program()}"' in body
    assert "uv run" not in body and "cd " not in body   # no repository folder needed
    assert script.stat().st_mode & 0o111


def test_mac_app_is_a_proper_bundle(home: Path) -> None:
    res = L.create(platform=L.MAC)
    app = home / "Applications" / "Murmurent Dashboard.app"
    assert res.location == app
    exe = app / "Contents/MacOS/murmurent-launcher"
    assert exe.stat().st_mode & 0o111
    assert "<string>murmurent-launcher</string>" in (app / "Contents/Info.plist").read_text()
    assert str(L.murmurent_program()) in exe.read_text(encoding="utf-8")


def test_user_option_fixes_the_handle(home: Path) -> None:
    L.create(platform=L.LINUX, user="bob")
    body = (home / ".local/share/murmurent/murmurent-dashboard-launcher.sh").read_text()
    assert 'MURMURENT_USER="bob"' in body


def test_remove_deletes_only_what_it_wrote(home: Path) -> None:
    apps = home / ".local/share/applications"
    apps.mkdir(parents=True)
    other = apps / "someone-elses.desktop"
    other.write_text("[Desktop Entry]\n", encoding="utf-8")
    L.create(platform=L.LINUX)
    res = L.remove(platform=L.LINUX)
    assert res.files and not (apps / "murmurent-dashboard.desktop").exists()
    assert other.exists()
    assert L.remove(platform=L.LINUX).files == []   # nothing left, no error


def test_other_platforms_say_so(home: Path) -> None:
    res = L.create(platform="win32")
    assert not res.supported and not any(home.iterdir())
    assert "no dashboard icon" in L.where_to_find(res).lower()


def test_doctor_reports_missing_then_present(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(L, "current_platform", lambda: L.LINUX)
    check = doctor_cmd.check_launcher()
    assert check.status == doctor_cmd.WARN and check.fix == "murmurent launcher"
    L.create()
    assert doctor_cmd.check_launcher().status == doctor_cmd.OK


def test_cli_creates_and_removes(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(L, "current_platform", lambda: L.LINUX)
    out = CliRunner().invoke(cli, ["launcher"]).output
    assert "applications menu" in out
    out = CliRunner().invoke(cli, ["launcher", "--remove"]).output
    assert "Removed" in out


def test_install_no_launcher_writes_nothing(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(L, "current_platform", lambda: L.LINUX)
    from murmurent.commands import repo_cmd, setup_cmd

    monkeypatch.setattr(setup_cmd, "cmd_setup", lambda **_: 0)
    monkeypatch.setattr(repo_cmd, "cmd_upgrade", lambda **_: 0)
    settings = home / "settings.json"
    r = CliRunner().invoke(cli, ["install", "--settings", str(settings), "--no-launcher"])
    assert r.exit_code == 0, r.output
    assert not (home / ".local/share/applications").exists()
    r = CliRunner().invoke(cli, ["install", "--settings", str(settings)])
    assert (home / ".local/share/applications/murmurent-dashboard.desktop").is_file()


def test_the_wheel_ships_the_icon() -> None:
    forced = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["hatch"]["build"][
        "targets"]["wheel"]["force-include"]
    assert forced.get(f"assets/{L.ICON_NAME}") == f"murmurent/commons/assets/{L.ICON_NAME}"
