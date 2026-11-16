"""
Purpose: One entry point for every harness's hooks other than Claude Code's
         (phase 2 of ``docs/harnesses_plan.md``). The harness's own payload
         is turned into murmurent's :class:`ToolEvent` by its profile, the
         guards that protect the data root run on that event exactly as they
         run for Claude Code, and the decision goes back in the harness's own
         shape. The audit record, the session record in the vault, the
         project context at session start and the agents-log line all go
         through here too, so a session in any harness leaves the same
         traces.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-16
Input:   ``--harness <name> --event <PreToolUse|PostToolUse|SessionStart|PreInvocation>``
         and the harness's payload on stdin.
Output:  The harness's answer on stdout: a deny, or nothing to say.

Failure policy: the guards are the only thing that may refuse. Everything
else (the audit, the session record, the context) never blocks and never
raises; a hook that throws would stop the harness, which is worse than a
missing log line. ``MURMURENT_HOOK_DEBUG=1`` prints the reason on stderr.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from ..core import harness_policy as _hp

EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "PreInvocation")
DEBUG_ENV = "MURMURENT_HOOK_DEBUG"


def _debug(msg: str) -> None:
    if os.environ.get(DEBUG_ENV):
        print(f"murmurent adapter: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# PreToolUse: the guards
# ---------------------------------------------------------------------------


def guards() -> list[tuple[str, Any]]:
    """The guards in the order they run, each ``(name, evaluate)`` taking a
    call in Claude Code's shape and returning ``{"decision": ...}``."""
    from . import phi_check, protected_paths, raw_guard

    return [
        ("raw_guard", raw_guard.evaluate),
        ("protected_paths", protected_paths.evaluate),
        ("phi_check", phi_check.evaluate_pre),
    ]


def decide(event: _hp.ToolEvent) -> tuple[dict[str, Any], str]:
    """Run every guard on the event; the first deny wins. Returns the
    decision and the name of the guard that made it ('' for allow)."""
    call = event.as_claude_call()
    for name, evaluate in guards():
        try:
            decision = evaluate(call)
        except Exception as exc:  # noqa: BLE001 - a guard that throws must not stop the harness
            _debug(f"{name} raised {exc!r}; treated as allow")
            continue
        if decision.get("decision") == "deny":
            return decision, name
    return {"decision": "allow"}, ""


# ---------------------------------------------------------------------------
# The other events
# ---------------------------------------------------------------------------


def _model(payload: dict[str, Any]) -> str:
    return str(payload.get("modelName") or payload.get("model") or "")


def audit(profile: _hp.Profile, event: _hp.ToolEvent, payload: dict[str, Any],
          decision: str = "", hook: str = "") -> None:
    try:
        from . import audit as _audit

        call = event.as_claude_call()
        call["outcome"] = "error" if payload.get("error") else "ok"
        _audit.write_entry(call, harness=profile.facts.name, model=_model(payload),
                           place=profile.facts.place, decision=decision, hook=hook)
    except Exception as exc:  # noqa: BLE001
        _debug(f"audit skipped: {exc!r}")


def agents_log_line(profile: _hp.Profile, payload: dict[str, Any]) -> None:
    """One plain line in ``~/.murmurent/agents.log`` when a session starts in
    another harness, so the dashboard's pane shows it beside Claude Code's."""
    try:
        log = Path(os.environ.get("MURMURENT_AGENT_LOG") or Path.home() / ".murmurent" / "agents.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        model = _model(payload) or "model unknown"
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {profile.facts.name}: session started ({model}, {profile.facts.place})\n")
    except Exception as exc:  # noqa: BLE001
        _debug(f"agents log skipped: {exc!r}")


def session_start(profile: _hp.Profile, payload: dict[str, Any]) -> dict[str, Any]:
    """The project summary and readiness notice Claude Code gets on its first
    prompt, injected once at session start; and the agents-log line."""
    agents_log_line(profile, payload)
    try:
        from . import context_inject

        blocks = [b for b in (context_inject._project_summary(payload.get("cwd")),
                              context_inject._readiness_notice(payload.get("cwd"))) if b]
    except Exception as exc:  # noqa: BLE001
        _debug(f"context skipped: {exc!r}")
        blocks = []
    if not blocks:
        return {}
    return {"injectSteps": [{"systemMessage": {"systemMessage": "\n".join(blocks)}}]}


def _state_dir() -> Path:
    return Path(os.environ.get("MURMURENT_HARNESS_STATE") or Path.home() / ".murmurent" / "harness_state")


def pre_invocation(profile: _hp.Profile, payload: dict[str, Any]) -> dict[str, Any]:
    """Record the prompt in the vault's session record, once per prompt.
    Antigravity fires this before every model call, so the same prompt
    comes round several times in one turn; a small state file per
    conversation remembers the last one recorded."""
    prompt = str(payload.get("lastUserInput") or "")
    session = str(payload.get("conversationId") or "")
    if not prompt.strip():
        return {}
    try:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        marker = _state_dir() / profile.facts.name / f"{session or 'unknown'}.last"
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == digest:
            return {}
        from . import session_log

        note = session_log.evaluate({"session_id": session, "cwd": payload.get("cwd") or "", "prompt": prompt})
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(digest, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _debug(f"session record skipped: {exc!r}")
        return {}
    if note:
        return {"injectSteps": [{"systemMessage": {"systemMessage": note}}]}
    return {}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def handle(harness: str, event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The answer for one hook call. Pure apart from the records it writes."""
    profile = _hp.profiles()[harness]
    if event_name == "PreToolUse":
        event = profile.to_event(payload)
        decision, hook = decide(event)
        if decision.get("decision") == "deny":
            audit(profile, event, payload, decision="deny", hook=hook)
        return profile.from_decision(decision)
    if event_name == "PostToolUse":
        audit(profile, profile.to_event(payload), payload)
        return {}
    if event_name == "SessionStart":
        return session_start(profile, payload)
    if event_name == "PreInvocation":
        return pre_invocation(profile, payload)
    return {}


def main(argv: list[str] | None = None, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="murmurent.hooks.adapter")
    parser.add_argument("--harness", required=True)
    parser.add_argument("--event", required=True, choices=EVENTS)
    args = parser.parse_args(argv)
    src = stdin or sys.stdin
    dst = stdout or sys.stdout
    raw = src.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if args.harness not in _hp.profiles():
        _debug(f"unknown harness {args.harness!r}; nothing done")
        dst.write("{}")
        return 0
    try:
        answer = handle(args.harness, args.event, payload)
    except Exception as exc:  # noqa: BLE001 - never stop the harness
        _debug(f"{args.event} failed: {exc!r}")
        answer = {}
    dst.write(json.dumps(answer))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
