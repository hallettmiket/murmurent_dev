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
