"""
Purpose: One record for every harness's sessions (phase 4 of
         ``docs/harnesses_plan.md``). Each profile reads its own transcripts
         into :class:`~.harness_policy.Event` rows; the audit log adds the
         refusals the hooks made; this module folds both into one row per
         session, whatever harness ran it, for ``murmurent sessions``, the
         dashboard and, later, the nightly review.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   Each installed harness's transcript stores on this machine; the
         audit log (``~/.claude/murmurent-audit/*.log``).
Output:  :class:`Session` rows, newest first. Read-only.

A harness whose transcripts cannot be read is reported as such in its own
row rather than left out, so "half of what the lab did" is never silently
missing from the record.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

from . import harness_policy as _hp


@dataclass
class Session:
    harness: str
    session: str
    place: str
    start: str = ""
    end: str = ""
    model: str = ""
    project: str = ""
    repo: str = ""
    calls: int = 0
    refusals: int = 0
    tools: dict[str, int] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(text: str) -> _dt.datetime | None:
    if not text:
        return None
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _audit_dir() -> Path:
    from ..hooks.audit import _log_dir

    return _log_dir()


def audit_rows(since: _dt.date | None = None) -> Iterator[dict[str, Any]]:
    """Every audit row on this machine, oldest first; ``since`` keeps the
    day files from that date on."""
    folder = _audit_dir()
    if not folder.is_dir():
        return
    for day in sorted(folder.glob("*.log")):
        try:
            if since and _dt.date.fromisoformat(day.stem) < since:
                continue
        except ValueError:
            pass
        try:
            lines = day.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _events_for(profile: _hp.Profile, home: Path, since: _dt.datetime | None) -> tuple[list[_hp.Event], str]:
    """All events of one harness, and a note when it could not be read."""
    events: list[_hp.Event] = []
    stores = profile.transcript_stores(home)
    files = [f for store in stores for f in store.files()]
    if not files:
        return [], "no transcripts on this machine"
    try:
        for f in files:
            if since is not None:
                try:
                    if _dt.datetime.fromtimestamp(f.stat().st_mtime, tz=_dt.timezone.utc) < since:
                        continue
                except OSError:
                    continue
            events.extend(profile.read_events(f))
    except NotImplementedError as exc:
        return [], f"{len(files)} transcripts, not read: {exc}"
    return events, ""


def sessions(since: _dt.date | None = None, home: Path | None = None,
             policy: _hp.HarnessPolicy | None = None) -> list[Session]:
    """One row per session across every harness installed here, newest
    first. ``since`` limits to transcripts touched and audit days from that
    date on."""
    home = home or Path.home()
    policy = policy or _hp.load_harnesses()
    since_dt = (_dt.datetime.combine(since, _dt.time.min, tzinfo=_dt.timezone.utc) if since else None)
    rows: dict[tuple[str, str], Session] = {}
    notes: list[Session] = []
    profiles = _hp.profiles()
    for name in policy.names():
        profile = profiles[name]
        events, note = _events_for(profile, home, since_dt)
        if note:
            notes.append(Session(harness=name, session="", place=profile.facts.place, note=note))
            continue
        for ev in events:
            key = (ev.harness, ev.session)
            row = rows.get(key)
            if row is None:
                row = rows[key] = Session(harness=ev.harness, session=ev.session, place=ev.place)
            row.calls += 1
            row.tools[ev.tool] = row.tools.get(ev.tool, 0) + 1
            if ev.model and not row.model:
                row.model = ev.model
            if ev.project and not row.project:
                row.project = ev.project
            if ev.repo and not row.repo:
                row.repo = ev.repo
            if ev.t and (not row.start or ev.t < row.start):
                row.start = ev.t
            if ev.t and ev.t > row.end:
                row.end = ev.t
    # The refusals the hooks made, by harness and session.
    for audit in audit_rows(since):
        key = (str(audit.get("harness") or "claude_code"), str(audit.get("session") or ""))
        row = rows.get(key)
        if row is not None and audit.get("model") and not row.model:
            row.model = str(audit["model"])     # Antigravity's transcript names no model; its hook does
        if audit.get("decision") != "deny":
            continue
        if row is None:
            row = rows[key] = Session(harness=key[0], session=key[1] or NOT_RECORDED,
                                      place=str(audit.get("place") or ""), model=str(audit.get("model") or ""))
            row.start = row.end = str(audit.get("ts") or "")
        row.refusals += 1
    ordered = sorted(rows.values(), key=lambda r: r.end or r.start, reverse=True)
    return ordered + notes


NOT_RECORDED = "(session not recorded)"


def short_id(session: str) -> str:
    if session == NOT_RECORDED:
        return "not recorded"
    return session[:8] if len(session) > 12 else session


_ = os  # the module reads nothing from the environment yet; kept for the override a later phase adds
