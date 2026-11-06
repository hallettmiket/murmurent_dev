"""murmurent must at least start on a native Windows Python (#281).

Windows Python has no ``pwd``, ``grp`` or ``fcntl``. A top-level import of
any of them in a module the CLI loads eagerly stops every ``murmurent``
command before it prints a word, which is what students on PCs saw. These
tests hide those modules and import the entry points: the CLI, every hook,
every MCP server and the dashboard. They do not make murmurent work on
Windows; they keep it able to run ``murmurent doctor`` and say so.
"""
from __future__ import annotations

import importlib
import importlib.abc
import sys

import pytest

from murmurent.commands import doctor_cmd

UNIX_ONLY = {"pwd", "grp", "fcntl", "termios", "tty", "resource"}

ENTRY_POINTS = [
    "murmurent.cli",
    "murmurent.hooks.raw_guard",
    "murmurent.hooks.protected_paths",
    "murmurent.hooks.phi_check",
    "murmurent.hooks.context_inject",
    "murmurent.hooks.audit",
    "murmurent.hooks.conscience_gaps",
    "murmurent.hooks.vault_sync",
    "murmurent.mcp.inventory_server",
    "murmurent.mcp.oracle_server",
    "murmurent.mcp.core_data_server",
    "murmurent.mcp.data_server",
    "murmurent.dashboard.server",
]


class _NoUnixModules(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name in UNIX_ONLY:
            raise ModuleNotFoundError(f"No module named {name!r} (simulated Windows)")
        return None


@pytest.fixture
def windows_python(monkeypatch):
    for name in list(sys.modules):
        if name in UNIX_ONLY or name == "murmurent" or name.startswith("murmurent."):
            monkeypatch.delitem(sys.modules, name)
    finder = _NoUnixModules()
    monkeypatch.setattr(sys, "meta_path", [finder] + sys.meta_path)
    yield
    for name in list(sys.modules):
        if name == "murmurent" or name.startswith("murmurent."):
            del sys.modules[name]


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_entry_point_imports_without_unix_modules(windows_python, module: str) -> None:
    importlib.import_module(module)


def test_doctor_names_wsl_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    c = doctor_cmd.check_platform()
    assert c.status == doctor_cmd.WARN
    assert "WSL" in c.detail and "wsl --install" in c.fix


def test_doctor_passes_the_platform_check_on_unix(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert doctor_cmd.check_platform().status == doctor_cmd.OK


def test_a_legacy_console_gets_question_marks_not_a_crash(monkeypatch):
    """A cp1252 console (the Windows default) must not kill a command on ✓ (#281)."""
    import io

    from murmurent import cli as _cli

    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "stderr", console)
    _cli.tolerate_console_encoding()
    console.write("  ✓ operating system: macOS\n")
    console.flush()
    assert console.buffer.getvalue() == b"  ? operating system: macOS\n"


def test_a_utf8_console_is_left_alone(monkeypatch):
    import io

    from murmurent import cli as _cli

    console = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "stderr", console)
    _cli.tolerate_console_encoding()
    assert console.errors == "strict"


def test_setup_refuses_plainly_when_symlinks_are_not_allowed(tmp_path, monkeypatch, capsys):
    """Windows without Developer Mode refuses symlinks (WinError 1314); setup
    must say so and point at WSL, not die in a traceback (#281)."""
    from pathlib import Path

    from murmurent.commands import setup_cmd

    root = tmp_path / "commons"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "oracle.md").write_text("# oracle\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(root))
    monkeypatch.setenv("MURMURENT_CC_DIR", str(tmp_path / "claude"))

    def refuse(self, target, target_is_directory=False):
        raise OSError(1314, "A required privilege is not held by the client")

    monkeypatch.setattr(Path, "symlink_to", refuse)
    rc = setup_cmd.cmd_setup(show_next_step=False)
    err = capsys.readouterr().err
    assert rc == 1
    assert "cannot create symlinks" in err
    assert "WSL" in err and "Developer Mode" in err
    assert not (tmp_path / "claude" / "agents" / "oracle.md").exists()


def test_doctor_uses_ascii_icons_on_a_legacy_console(monkeypatch):
    import io

    from murmurent.commands import doctor_cmd

    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    assert doctor_cmd._icons() == {doctor_cmd.OK: "ok", doctor_cmd.WARN: "!", doctor_cmd.FAIL: "x"}
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="utf-8"))
    assert doctor_cmd._icons()[doctor_cmd.OK] == "✓"


def test_run_supervisor_imports_without_sigkill(monkeypatch) -> None:
    """Windows has no SIGKILL; the supervisor's hint table must not need it (#281)."""
    import importlib
    import signal

    monkeypatch.delattr(signal, "SIGKILL")
    sys.modules.pop("murmurent.core.run_supervisor", None)
    rs = importlib.import_module("murmurent.core.run_supervisor")
    assert signal.SIGSEGV in rs.SIGNAL_HINTS
    assert len(rs.SIGNAL_HINTS) == 1
    sys.modules.pop("murmurent.core.run_supervisor", None)
