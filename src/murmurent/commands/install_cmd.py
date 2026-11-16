"""
Purpose: ``murmurent install --hooks``: merge murmurent's hooks and MCP servers
         into Claude Code's files. The registrations and the merge logic live
         in :mod:`murmurent.core.harness_claude_code`, the Claude Code
         profile, since phase 0 of ``docs/harnesses_plan.md``; this module
         keeps the command's name, output and effect, and re-exports the
         names other modules import from here.
Author: Mike Hallett (with Claude Code)
Date: 2026-05-07
Input: CLI flags from :mod:`murmurent.cli`.
Output: Updated ``~/.claude/settings.json`` and ``~/.claude.json``; returns the
        settings path that was edited.
"""

from __future__ import annotations

from pathlib import Path

import click

from ..core import harness_claude_code as _cc
from ..core.harness_claude_code import (  # noqa: F401 - re-exported for callers and tests
    DEFAULT_ENV,
    DEFAULT_SETTINGS_PATH,
    HOOK_REGISTRATIONS,
    MCP_REGISTRATIONS,
    _ensure_env,
    _ensure_hook,
    _ensure_mcp,
    _ensure_mcp_claude_json,
    _expand_placeholders,
    _matches_existing,
    _resolve_command,
)


def cmd_install(
    *,
    hooks: bool = False,
    settings_path: Path | None = None,
    backup: bool = True,
) -> Path:
    """Install hooks + MCP servers into the CC settings file."""
    if not hooks:
        raise click.ClickException("phase 4 supports --hooks only (full install lands in phase 5).")
    try:
        target, changed = _cc.install(settings_path, backup=backup)
    except _cc.SettingsUnreadable as exc:
        raise click.ClickException(str(exc))
    if changed:
        click.echo(f"Installed murmurent hooks + MCP into {target}")
    else:
        click.echo(f"{target}: no changes (already installed).")
    return target
