"""
Purpose: Let the three data-root guards (``raw_guard``, ``protected_paths``,
         ``data_root_guard``) judge a command that reaches ANOTHER machine's
         data root: an ``ssh <server> '...'`` whose remote command touches the
         server's data root, or an ``rsync`` or ``scp`` whose source or
         destination is ``<server>:<path under its data root>``. Each guard
         judges paths against the data root of the machine the session runs
         on; a session on a laptop that sends work to the lab server would
         otherwise see nothing. This module finds, in a Bash command, every
         stretch that runs on a known host, and hands the guard that stretch
         together with that host's data root.

Author:  Mike Hallett (with Claude Code)
Date:    2026-11-25
Input:   A Bash command string; the lab's ``policy/machines.yaml`` (each
         machine's ``data_root``), the member's ``~/.murmurent/hosts.yaml``
         (the ssh alias each machine is reached by), and the override
         ``$MURMURENT_REMOTE_DATA_ROOTS`` (``host=/root,host2=/root2``).
Output:  ``views(command)``: a list of ``(host, data_root, command_as_seen_on_host)``.

How a guard uses it::

    for host, root, view in remote_paths.views(command):
        with remote_paths.on_host(host, root):
            reason = _bash_violation(view)      # the guard's own analysis
            if reason:
                return f"on {host}: {reason}"

Inside ``on_host`` the data-root environment variables name the remote root,
so the guard's own prefix functions resolve to it, and ``exists()`` asks the
host over ssh whether a file is there (batch mode, short timeout). A host that
does not answer is treated as if the file exists, which is the safe direction:
an overwrite is refused rather than let through. Only hosts whose data root is
declared are judged; an ssh to any other host is not this module's business.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import subprocess
from pathlib import Path
from typing import Callable, Iterator

ENV_OVERRIDE = "MURMURENT_REMOTE_DATA_ROOTS"
SSH_TIMEOUT_SECONDS = 8
#: Options of ssh that take a value, so the host is the first positional.
_SSH_VALUE_OPTS = frozenset("BbcDEeFIiJLlmOopQRSWw")

#: The host a guard is currently judging for, or "" on the local machine.
_ACTIVE_HOST = ""

#: Replaceable in tests: ``(host, path) -> bool``.
REMOTE_EXISTS: Callable[[str, str], bool] | None = None


# ---------------------------------------------------------------------------
# Which hosts have a declared data root
# ---------------------------------------------------------------------------


def _strip_user(host: str) -> str:
    return host.split("@", 1)[-1].strip().lower()


def remote_roots() -> dict[str, str]:
    """``{alias: data_root}`` for every host whose data root is known. Aliases
    are the machine's name, its ``ssh_host`` with and without ``user@``, and
    the ssh alias in the member's hosts file, all lower-case."""
    roots: dict[str, str] = {}
    try:
        from ..core.machine_policy import load_machines
        policy = load_machines()
        for name, machine in policy.machines.items():
            if not machine.data_root or machine.runs_here():
                continue
            roots[name.lower()] = machine.data_root
            if machine.ssh_host:
                roots[_strip_user(machine.ssh_host)] = machine.data_root
    except Exception:  # noqa: BLE001  (no lab records here: nothing declared)
        pass
    try:
        import yaml
        home = Path(os.environ.get("MURMURENT_HOME") or "~/.murmurent").expanduser()
        data = yaml.safe_load((home / "hosts.yaml").read_text(encoding="utf-8")) or {}
        for name, entry in (data.get("hosts") or {}).items():
            root = roots.get(str(name).lower())
            alias = _strip_user(str((entry or {}).get("ssh_host") or ""))
            if root and alias and alias != "na":
                roots[alias] = root
    except Exception:  # noqa: BLE001
        pass
    for item in os.environ.get(ENV_OVERRIDE, "").split(","):
        host, sep, root = item.partition("=")
        if sep and host.strip() and root.strip():
            roots[_strip_user(host)] = root.strip()
    return roots


# ---------------------------------------------------------------------------
# The stretches of a command that run on a host
# ---------------------------------------------------------------------------


def _ssh_views(tokens: list[str], roots: dict[str, str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    i = 0
    while i < len(tokens):
        if Path(tokens[i]).name != "ssh":
            i += 1
            continue
        j = i + 1
        host = ""
        while j < len(tokens):
            tok = tokens[j]
            if tok.startswith("-"):
                if len(tok) == 2 and tok[1] in _SSH_VALUE_OPTS:
                    j += 2
                else:
                    j += 1
                continue
            host = tok
            j += 1
            break
        if host and _strip_user(host) in roots:
            remote = " ".join(tokens[j:])
            if remote.strip():
                out.append((_strip_user(host), roots[_strip_user(host)], remote))
        return out + (_ssh_views(tokens[j:], roots) if host else [])
    return out


def _copy_views(tokens: list[str], roots: dict[str, str]) -> list[tuple[str, str, str]]:
    """For ``host:path`` operands (scp, rsync), one view per host in which
    that host's operands are bare paths and other hosts' operands are left."""
    hosts: list[str] = []
    for tok in tokens:
        head, sep, _ = tok.partition(":")
        if sep and head and "/" not in head and _strip_user(head) in roots:
            if _strip_user(head) not in hosts:
                hosts.append(_strip_user(head))
    out: list[tuple[str, str, str]] = []
    for host in hosts:
        view = []
        for tok in tokens:
            head, sep, rest = tok.partition(":")
            if sep and head and "/" not in head and _strip_user(head) == host:
                view.append(rest)
            else:
                view.append(tok)
        out.append((host, roots[host], shlex.join(view)))
    return out


def views(command: str) -> list[tuple[str, str, str]]:
    """Every ``(host, data_root, command as the host would run it)`` in the
    command. Empty for a command that touches no declared host, and for one
    the parser cannot read."""
    if not command or not command.strip():
        return []
    roots = remote_roots()
    if not roots:
        return []
    try:
        tokens = shlex.split(command, comments=True, posix=True)
    except ValueError:
        return []
    return _ssh_views(tokens, roots) + _copy_views(tokens, roots)


# ---------------------------------------------------------------------------
# Judging as if on the host
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def on_host(host: str, data_root: str) -> Iterator[None]:
    """Make the data-root variables name the host's root for the duration,
    and send ``exists()`` to that host."""
    global _ACTIVE_HOST
    saved = {k: os.environ.get(k) for k in ("MURMURENT_DATA_ROOT", "MURMURENT_LAB_VM_ROOT")}
    os.environ["MURMURENT_DATA_ROOT"] = data_root
    os.environ.pop("MURMURENT_LAB_VM_ROOT", None)
    previous, _ACTIVE_HOST = _ACTIVE_HOST, host
    try:
        yield
    finally:
        _ACTIVE_HOST = previous
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def active_host() -> str:
    return _ACTIVE_HOST


def _ssh_exists(host: str, path: str) -> bool:
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_TIMEOUT_SECONDS}", host,
             "test", "-e", shlex.quote(path)],
            capture_output=True, timeout=SSH_TIMEOUT_SECONDS + 4, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True            # unreachable: assume it is there (refuse an overwrite)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return True                # 255 and the like: could not ask


def exists(path: str) -> bool:
    """Does ``path`` exist as a file where the guard is currently judging:
    on the active host over ssh, else on this machine (file or symlink)."""
    if _ACTIVE_HOST:
        checker = REMOTE_EXISTS or _ssh_exists
        return checker(_ACTIVE_HOST, path)
    try:
        p = Path(path).expanduser()
        return p.is_file() or p.is_symlink()
    except OSError:
        return False
