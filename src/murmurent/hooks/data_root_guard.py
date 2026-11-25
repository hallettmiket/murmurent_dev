"""
Purpose: Claude Code ``PreToolUse`` hook for the parts of the data root that
         the two tier guards do not cover. ``raw_guard`` refuses every write
         under ``immutable/`` and ``protected_paths`` refuses overwrites and
         deletes under ``append_only/``. This hook rules on the rest of
         ``$MURMURENT_DATA_ROOT``:

           - ``modifiable/``: anything goes; code may overwrite and delete
             its own working data.
           - ``mothballed/``: a NEW file may be placed there; nothing already
             there is changed or deleted. People move files there on their
             way to long-term storage and no agent alters them (lab folder
             protocol, rule 1).
           - everything else under the root (``release/``, ``cottage/``,
             ``tools/``, ``db/``, a folder the protocol does not name, a
             loose file at the top): a NEW file is written without asking,
             an overwrite of an existing file is refused, and a delete or a
             move out asks the member first.

Author:  Mike Hallett (with Claude Code)
Date:    2026-11-25
Input:   Tool-call JSON on stdin in the CC hook contract.
Output:  Nothing for allow; ``hookSpecificOutput`` with ``permissionDecision``
         ``deny`` or ``ask`` and a reason otherwise.

The data root is ``$MURMURENT_DATA_ROOT``, else the legacy
``$MURMURENT_LAB_VM_ROOT``, else nothing: with no root set the hook allows
everything rather than guessing a tree to guard. Paths under ``immutable/``,
``raw/``, ``append_only/`` and ``refined/`` are left to their own hooks so a
member sees one reason, not two.

Like its sisters this is a guardrail for an agent's mistake, not a security
perimeter: it sees tool calls made inside a Claude Code session and nothing
else, and it reads the text of a Bash command, so a command that merely
mentions a governed path beside a redirect is refused too.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import IO, Any

ALLOW, DENY, ASK = "allow", "deny", "ask"

#: Folders ruled on by their own hooks; this one steps aside for them.
OWN_HOOK_FOLDERS: frozenset[str] = frozenset({"immutable", "raw", "append_only", "refined"})
MODIFIABLE_FOLDERS: frozenset[str] = frozenset({"modifiable"})
UNTOUCHABLE_FOLDERS: frozenset[str] = frozenset({"mothballed"})

#: Operation kinds a tool call can amount to, in the hook's eyes.
CREATE, OVERWRITE, DELETE = "create", "overwrite", "delete"

#: What each tier answers for each operation kind.
POLICY: dict[str, dict[str, str]] = {
    "own_hook": {CREATE: ALLOW, OVERWRITE: ALLOW, DELETE: ALLOW},   # theirs to refuse
    "modifiable": {CREATE: ALLOW, OVERWRITE: ALLOW, DELETE: ALLOW},
    "mothballed": {CREATE: ALLOW, OVERWRITE: DENY, DELETE: DENY},
    "other": {CREATE: ALLOW, OVERWRITE: DENY, DELETE: ASK},
}

REMOVE_COMMANDS: frozenset[str] = frozenset({"rm", "rmdir", "shred", "unlink"})
MODIFY_COMMANDS: frozenset[str] = frozenset({"truncate", "dd", "chmod", "chown", "chgrp"})
COPY_LIKE_COMMANDS: frozenset[str] = frozenset({"cp", "rsync", "install"})

_REDIRECT = re.compile(r"(?P<op>>>?|\|\s*tee\b(?:\s+-a)?)\s+['\"]?(?P<path>[^\s'\"]+)")


# ---------------------------------------------------------------------------
# Where a path sits
# ---------------------------------------------------------------------------


def data_root() -> Path | None:
    env = os.environ.get("MURMURENT_DATA_ROOT") or os.environ.get("MURMURENT_LAB_VM_ROOT")
    return Path(env).expanduser() if env else None


def tier_of(candidate: str) -> str:
    """``""`` when the path is outside the data root; else one of the POLICY
    keys. Lexical only: no symlink chasing, no filesystem access."""
    root = data_root()
    if not candidate or root is None:
        return ""
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        return ""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return ""
    parts = rel.parts
    if not parts:
        return "other"          # the root itself
    top = parts[0].lower()
    if top in OWN_HOOK_FOLDERS:
        return "own_hook"
    if top in MODIFIABLE_FOLDERS:
        return "modifiable"
    if top in UNTOUCHABLE_FOLDERS:
        return "mothballed"
    return "other"


def _is_file(candidate: str) -> bool:
    from . import remote_paths
    return remote_paths.exists(candidate)


# ---------------------------------------------------------------------------
# What a call amounts to: a list of (operation, path)
# ---------------------------------------------------------------------------


def _bash_operations(command: str) -> list[tuple[str, str]]:
    """Every (operation, path) a Bash command performs on a governed path.
    Conservative in both directions: a command the parser cannot read is
    let through, as the sister hooks do."""
    ops: list[tuple[str, str]] = []
    if not command or not command.strip():
        return ops
    for m in _REDIRECT.finditer(command):
        path = m.group("path")
        if tier_of(path):
            ops.append((OVERWRITE if _is_file(path) else CREATE, path))
    try:
        tokens = shlex.split(command, comments=True, posix=True)
    except ValueError:
        return ops
    for i, tok in enumerate(tokens):
        name = Path(tok).name
        positionals = [a for a in tokens[i + 1:] if not a.startswith("-")]
        if name in REMOVE_COMMANDS:
            ops += [(DELETE, a) for a in positionals if tier_of(a)]
        elif name in MODIFY_COMMANDS:
            ops += [(OVERWRITE, a) for a in positionals if tier_of(a)]
        elif name == "mv" and len(positionals) >= 2:
            *sources, dest = positionals
            ops += [(DELETE, s) for s in sources if tier_of(s)]
            if tier_of(dest):
                ops.append((OVERWRITE if _is_file(dest) else CREATE, dest))
        elif name in COPY_LIKE_COMMANDS and positionals:
            dest = positionals[-1]
            if tier_of(dest):
                ops.append((OVERWRITE if _is_file(dest) else CREATE, dest))
    return ops


def operations(call: dict[str, Any]) -> list[tuple[str, str]]:
    tool = call.get("tool_name") or call.get("tool") or ""
    args = call.get("tool_input") or call.get("args") or {}
    if tool == "Write":
        target = args.get("file_path") or ""
        return [(OVERWRITE if _is_file(target) else CREATE, target)] if tier_of(target) else []
    if tool in ("Edit", "NotebookEdit"):
        target = args.get("file_path") or args.get("notebook_path") or ""
        return [(OVERWRITE, target)] if tier_of(target) else []
    if tool == "Bash":
        return _bash_operations(args.get("command", ""))
    return []


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

_WHY = {
    ("mothballed", OVERWRITE): "nothing already under mothballed/ is changed: it is on its way to long-term storage",
    ("mothballed", DELETE): "nothing under mothballed/ is deleted: it is on its way to long-term storage",
    ("other", OVERWRITE): "a file under the data root is not overwritten; write a new versioned name (file_2.csv) instead",
    ("other", DELETE): "deleting under the data root needs the member's permission",
}


def evaluate(call: dict[str, Any]) -> dict[str, Any]:
    """``{"decision": allow|deny|ask, "reason": ...}``. The strictest
    operation in the call decides: a deny beats an ask beats an allow."""
    worst, reason = ALLOW, ""
    rank = {ALLOW: 0, ASK: 1, DENY: 2}

    def judge(ops: list[tuple[str, str]], where: str) -> None:
        nonlocal worst, reason
        for op, path in ops:
            tier = tier_of(path)
            verdict = POLICY[tier][op]
            if rank[verdict] > rank[worst]:
                worst = verdict
                reason = f"{_WHY.get((tier, op), 'lab data policy')}: {op} of {where}{path}"

    judge(operations(call), "")
    tool = call.get("tool_name") or call.get("tool") or ""
    if tool == "Bash":
        # The same rules for a stretch of the command that runs on another
        # machine whose data root is declared (ssh, scp, rsync).
        from . import remote_paths
        args = call.get("tool_input") or call.get("args") or {}
        for host, root, view in remote_paths.views(args.get("command", "")):
            with remote_paths.on_host(host, root):
                judge(_bash_operations(view), f"{host}:")
    return {"decision": worst, "reason": reason} if worst != ALLOW else {"decision": ALLOW}


def main(stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    src = stdin or sys.stdin
    dst = stdout or sys.stdout
    raw_text = src.read()
    if not raw_text.strip():
        return 0
    try:
        call = json.loads(raw_text)
    except json.JSONDecodeError:
        return 0
    decision = evaluate(call if isinstance(call, dict) else {})
    if decision["decision"] in (DENY, ASK):
        dst.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision["decision"],
                "permissionDecisionReason": decision.get("reason", ""),
            },
        }))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
