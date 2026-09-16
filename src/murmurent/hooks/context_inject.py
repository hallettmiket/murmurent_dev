"""
Purpose: ``UserPromptSubmit`` hook that prepends murmurent context to the
         user's prompt — the active project, and whether this repo's wiring
         has fallen behind the murmurent that is installed.
Author: Mike Hallett
Date: 2026-05-07
Input: ``UserPromptSubmit`` payload JSON on stdin (CC hook contract).
Output: ``hookSpecificOutput.additionalContext``, or nothing at all when there
        is neither an active project nor anything stale to report.

Two independent blocks, either of which can appear alone:

1. **Project context** — project name + sensitivity tier, the charter's first
   paragraph, the resolved member's role, and the SEAs assigned to or filed by
   them. Requires a CHARTER, so it appears only in project repos.

2. **Readiness notice** — keyed on the ``.murmurent.yaml`` marker instead, so
   it covers every murmurent-ready repo whether or not it is a project. This is
   how someone finds out that an upgrade happened: agent, rule and skill TEXT
   reaches a ready repo on its own, because ``.claude/agents/`` holds symlinks
   into the commons rather than copies, but a newly ADDED agent has no link yet
   and a repo linked to a different clone follows the wrong commons entirely.
   Neither announces itself, and both look like murmurent quietly not working.

   Deliberately NOT reported: a ``bootstrap_version`` that merely differs from
   the running version. ``repo_ready.needs_upgrade`` is true after every
   release, including one that changed nothing about this repo, so notifying on
   it would put a line in front of the user on every prompt after every upgrade
   and teach them to ignore the notice. Only a real roster gap speaks up.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from ..core.frontmatter import parse_file
from ..core.identity import resolve as resolve_identity
from ..core.repo import find_project_repo, read_members
from ..core.sea import filter_for_member, iter_seas


def _project_summary(start: str | None = None) -> str | None:
    repo = find_project_repo(start or os.getcwd())
    if repo is None:
        return None
    try:
        parsed = parse_file(repo.charter_path)
    except Exception:
        return None
    sensitivity = parsed.meta.get("sensitivity", "?")
    name = parsed.meta.get("project", repo.path.name)
    body = parsed.body.strip()
    first_para = body.split("\n\n", 1)[0] if body else ""
    members = read_members(repo.members_path) if repo.members_path else []
    identity = resolve_identity(allow_unknown=True)
    role = _resolve_role(identity.at_handle, parsed.meta, members)
    seas = iter_seas(repo)
    incoming = filter_for_member(seas, identity.handle, direction="incoming")
    outgoing = filter_for_member(seas, identity.handle, direction="outgoing")

    lines = [
        "<system-reminder>",
        "murmurent project context (auto-injected):",
        f"- project: {name} (sensitivity: {sensitivity})",
        f"- you: {identity.at_handle} ({role})",
    ]
    if first_para:
        cleaned = first_para.replace("\n", " ").strip()
        if len(cleaned) > 240:
            cleaned = cleaned[:237] + "..."
        lines.append(f"- charter: {cleaned}")
    if incoming:
        lines.append(
            "- SEAs assigned to you: " + ", ".join(f"#{s.id} ({s.state})" for s in incoming)
        )
    if outgoing:
        lines.append("- SEAs you filed: " + ", ".join(f"#{s.id} ({s.state})" for s in outgoing))
    if not (incoming or outgoing):
        lines.append("- SEAs: none for you in this project")
    lines.append("</system-reminder>")
    return "\n".join(lines)


MARKER = ".murmurent.yaml"


def _find_ready_repo(start: str | None = None) -> Path | None:
    """Nearest ancestor carrying the readiness marker, or None.

    Walks up rather than testing only the cwd, because a session is usually
    opened somewhere inside a repo (``exp/07_thing/``) rather than at its root.
    Stops at the filesystem root and at ``$HOME``, so a marker sitting in a
    home directory cannot make every shell look like a ready repo.
    """
    here = Path(start or os.getcwd()).resolve()
    home = Path.home().resolve()
    for cand in (here, *here.parents):
        if (cand / MARKER).is_file():
            return cand
        if cand == home:
            break
    return None


def _readiness_notice(start: str | None = None) -> str | None:
    """Tell the user when this ready repo's agent links have fallen behind.

    Reports only the two states that are actionable and silent:

    * agents exist in the commons that this repo has no link to — the shape a
      new agent in an upgrade takes, since nothing retro-fits links;
    * links resolving into a commons other than the installed one, which on a
      machine with two clones means edits land somewhere this repo cannot see.

    Cheap by construction: two globs over ~14 files each, no network, no git.
    This runs on every prompt submission, so it must never raise and never
    block — every failure path returns None and the prompt goes through
    untouched.
    """
    try:
        repo = _find_ready_repo(start)
        if repo is None:
            return None

        from ..core.commons import commons_root  # noqa: PLC0415

        commons = commons_root()
        agents_src = commons / "agents"
        if not agents_src.is_dir():
            return None
        available = {p.stem for p in agents_src.glob("*.md")}

        linked_dir = repo / ".claude" / "agents"
        linked: set[str] = set()
        foreign: set[Path] = set()
        if linked_dir.is_dir():
            for f in linked_dir.glob("*.md"):
                linked.add(f.stem)
                if not f.is_symlink():
                    continue
                try:
                    root = f.readlink().parent.parent
                except OSError:
                    continue
                if root.resolve() != commons.resolve():
                    foreign.add(root)

        missing = sorted(available - linked)
        if not missing and not foreign:
            return None

        lines = ["<system-reminder>",
                 "murmurent readiness (auto-injected):"]
        if foreign:
            lines.append(
                "- this repo's agents are linked into "
                + ", ".join(str(f) for f in sorted(foreign))
                + f", not the commons you are running ({commons}). Edits to an "
                  "agent there will not be visible here."
            )
        if missing:
            shown = ", ".join(missing[:8]) + ("…" if len(missing) > 8 else "")
            lines.append(
                f"- {len(missing)} commons agent(s) are not linked into this "
                f"repo: {shown}. Agent TEXT updates arrive on their own (the "
                "links are symlinks); a newly added agent needs linking once."
            )
        lines.append(f"- fix: murmurent repo upgrade {repo} --all-agents")
        lines.append("</system-reminder>")
        return "\n".join(lines)
    except Exception:  # noqa: BLE001
        # A hook that throws blocks the prompt. Nothing here is worth that.
        return None


def _resolve_role(at_handle: str, meta: dict[str, Any], members: list[str]) -> str:
    lead = str(meta.get("lead", "")).strip()
    if lead and lead.lstrip("'\"").rstrip("'\"") == at_handle:
        return "lead"
    if at_handle in members or at_handle in (meta.get("members") or []):
        return "member"
    return "non-member"


def main(stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    """UserPromptSubmit hook. CC's modern protocol: emit
    ``hookSpecificOutput.additionalContext`` to prepend system context
    to what the model sees; emit nothing to pass the prompt through
    unchanged. The legacy ``{"decision": "modify", "user_prompt": …}``
    form is no longer accepted.
    """
    src = stdin or sys.stdin
    dst = stdout or sys.stdout
    raw = src.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0

    blocks = [b for b in (_project_summary(), _readiness_notice()) if b]
    if not blocks:
        return 0

    dst.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(blocks),
        },
    }))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
