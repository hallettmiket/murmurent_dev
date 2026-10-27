"""
Purpose: Say whether this machine holds its group's lab records repo, and
        how to get it if not.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-27
Input: The identity card (which group), the canonical clone path
       (``repo.lab_repo_path``), and the stored member-card bundle (which
       carries the GitHub address of the records repo).
Output: :class:`RecordsStatus`, shown on the dashboard and printed by the
        terminal commands that read the records.

A group's records repo (``murmurent_lab_mgmt_<group>``) lives at exactly one
place per machine. When it is not there, nothing is invented: the person is
told the one command that puts it there.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from . import repo as _repo


@dataclass(frozen=True)
class RecordsStatus:
    """Where the group's records repo should be on this machine, and whether it is."""

    group: str
    path: str
    present: bool
    is_git: bool
    remote: str = ""   # git URL of the records repo on GitHub, when known
    hint: str = ""     # the command to run when ``present`` is False

    def to_dict(self) -> dict:
        return asdict(self)


def records_remote(group: str) -> str:
    """The git URL of ``group``'s records repo, or ''.

    Known from the member-card bundle this machine imported (the PI's machine
    stamps ``records_repo`` into it at issue time), else from the clone's own
    ``origin`` when the clone exists.
    """
    slug = _bundle_records_slug(group)
    if slug:
        return f"git@github.com:{slug}.git"
    try:
        from . import group_reconcile as _gr

        with _repo.use_lab_mgmt_root(_repo.lab_repo_path(group)):
            slug = _gr.lab_mgmt_repo_slug()
    except Exception:  # noqa: BLE001 - best-effort
        slug = ""
    return f"git@github.com:{slug}.git" if slug else ""


def _bundle_records_slug(group: str) -> str:
    try:
        from .issuance import cards_dir

        for p in cards_dir().glob("*_member.json"):
            bundle = json.loads(p.read_text(encoding="utf-8"))
            payload = (bundle.get("member_card") or {}).get("payload") or {}
            if str(payload.get("group") or "") == str(group):
                return str(bundle.get("records_repo") or "")
    except (OSError, ValueError):
        pass
    return ""


def records_status(group: str = "") -> RecordsStatus | None:
    """Status of ``group``'s records repo on this machine. With no ``group``,
    the owner's primary group from their card; ``None`` when there is none."""
    if not group:
        groups = _repo.owner_groups()
        if not groups:
            return None
        group = groups[0].group
    path = _repo.lab_repo_path(group)
    present = path.is_dir()
    remote = records_remote(group)
    return RecordsStatus(
        group=group, path=str(path), present=present,
        is_git=(path / ".git").exists(), remote=remote,
        hint="" if present else _repo.records_clone_hint(group, remote=remote),
    )


__all__ = ["RecordsStatus", "records_status", "records_remote"]
