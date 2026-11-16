"""Phase 4 of docs/harnesses_plan.md: one session record for every harness.
Synthetic transcripts in each harness's own shape (the shapes read from real
files on 2026-11-16, content invented), the readers, the fold into one row
per session with the hooks' refusals from the audit log, and `murmurent
sessions`. Nothing is read from the real home folder."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.commands.sessions_cmd import sessions_command
from murmurent.core import harness_antigravity as _ag
from murmurent.core import harness_policy as _hp
from murmurent.core import sessions as _sessions
from murmurent.hooks import audit as _audit


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MURMURENT_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(_hp, "lab_harnesses_path", lambda env=None: None)
    monkeypatch.setattr(_hp, "project_for_cwd", lambda cwd: "coin_seq" if "coin_seq" in cwd else "")
    return tmp_path


def _claude_line(t: str, tool: str, args: dict, session: str = "s-claude-0001") -> str:
    return json.dumps({"type": "assistant", "timestamp": t, "sessionId": session, "cwd": "/Users/me/repos/coin_seq",
                       "message": {"model": "claude-opus-5-5", "role": "assistant",
                                   "content": [{"type": "text", "text": "ok"},
                                               {"type": "tool_use", "id": "x", "name": tool, "input": args}]}})


def _write_claude(home: Path) -> Path:
    folder = home / ".claude" / "projects" / "-Users-me-repos-coin-seq"
    folder.mkdir(parents=True)
    f = folder / "s-claude-0001.jsonl"
    f.write_text("\n".join([
        json.dumps({"type": "user", "timestamp": "2026-11-16T10:00:00Z", "sessionId": "s-claude-0001", "message": {"role": "user", "content": "hi"}}),
        _claude_line("2026-11-16T10:00:05Z", "Bash", {"command": "ls"}),
        _claude_line("2026-11-16T10:00:09Z", "Read", {"file_path": "/a"}),
        "not json at all",
        _claude_line("2026-11-16T10:01:00Z", "Bash", {"command": "murmurent machines load"}),
    ]) + "\n", encoding="utf-8")
    return f


def _write_antigravity(home: Path, conv: str = "1fca6826-d00a-4cca-9467-f563a060e27e") -> Path:
    folder = home / _ag.APP_DATA_DIR / "brain" / conv / ".system_generated" / "logs"
    folder.mkdir(parents=True)
    f = folder / "transcript.jsonl"
    f.write_text("\n".join([
        json.dumps({"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "status": "DONE",
                    "created_at": "2026-11-16T17:53:27Z", "content": "list the folder"}),
        json.dumps({"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
                    "created_at": "2026-11-16T17:53:30Z", "input_tokens": 10, "output_tokens": 5,
                    "tool_calls": [{"name": "read_file", "args": {"Path": "/x"}}, {"name": "run_command", "args": {"CommandLine": "ls"}}]}),
        json.dumps({"step_index": 4, "source": "MODEL", "type": "GENERIC", "status": "DONE",
                    "created_at": "2026-11-16T17:53:41Z", "content": "done"}),
    ]) + "\n", encoding="utf-8")
    return f


def test_claude_code_reader(home):
    f = _write_claude(home)
    events = list(_hp.profiles()["claude_code"].read_events(f))
    assert [e.tool for e in events] == ["Bash", "Read", "Bash"]
    e = events[0]
    assert (e.harness, e.model, e.place, e.session, e.project, e.repo) == (
        "claude_code", "claude-opus-5-5", "anthropic_cloud", "s-claude-0001", "coin_seq", "coin_seq")
    assert e.t == "2026-11-16T10:00:05Z" and e.summary == '{"command": "ls"}'
    stores = _hp.profiles()["claude_code"].transcript_stores(home)
    assert [p.name for p in stores[0].files()] == ["s-claude-0001.jsonl"]


def test_antigravity_reader(home):
    f = _write_antigravity(home)
    events = list(_hp.profiles()["antigravity"].read_events(f))
    assert [e.tool for e in events] == ["read_file", "run_command"]
    assert events[0].session == "1fca6826-d00a-4cca-9467-f563a060e27e"
    assert events[0].place == "google_personal" and events[0].model == ""
    assert events[1].summary == '{"CommandLine": "ls"}'
    stores = _hp.profiles()["antigravity"].transcript_stores(home)
    assert sum(len(s.files()) for s in stores) == 1


def test_sessions_fold_transcripts_and_refusals(home):
    _write_claude(home)
    _write_antigravity(home)
    # The hooks' refusals and the model Antigravity's transcript lacks come from the audit log.
    _audit.write_entry({"tool_name": "Bash", "tool_input": {"command": "rm x"}}, harness="antigravity",
                       model="gemini-4-argon", place="google_personal", decision="deny", hook="raw_guard",
                       session="1fca6826-d00a-4cca-9467-f563a060e27e")
    _audit.write_entry({"tool_name": "Bash", "tool_input": {"command": "ls"}}, harness="antigravity",
                       model="gemini-4-argon", place="google_personal", session="1fca6826-d00a-4cca-9467-f563a060e27e")
    _audit.write_entry({"tool_name": "Write", "tool_input": {"file_path": "/i"}, "session_id": "s-claude-0001"},
                       decision="deny", hook="protected_paths")
    rows = {r.session: r for r in _sessions.sessions(None, home) if not r.note}
    ag = rows["1fca6826-d00a-4cca-9467-f563a060e27e"]
    assert (ag.calls, ag.refusals, ag.model, ag.tools) == (2, 1, "gemini-4-argon", {"read_file": 1, "run_command": 1})
    assert ag.start == "2026-11-16T17:53:30Z" and ag.end == "2026-11-16T17:53:30Z"
    cc = rows["s-claude-0001"]
    assert (cc.calls, cc.refusals, cc.project, cc.model) == (3, 1, "coin_seq", "claude-opus-5-5")
    assert cc.start == "2026-11-16T10:00:05Z" and cc.end == "2026-11-16T10:01:00Z"
    newest_first = [r.harness for r in _sessions.sessions(None, home) if not r.note]
    assert newest_first == ["antigravity", "claude_code"]


def test_a_harness_without_transcripts_gets_its_own_row(home):
    _write_claude(home)
    rows = _sessions.sessions(None, home)
    notes = [r for r in rows if r.note]
    assert [n.harness for n in notes] == ["antigravity"]
    assert "no transcripts" in notes[0].note


def test_since_keeps_recent_files_only(home):
    f = _write_claude(home)
    old = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc).timestamp()
    import os

    os.utime(f, (old, old))
    assert not [r for r in _sessions.sessions(_dt.date(2026, 11, 1), home) if not r.note]
    assert [r for r in _sessions.sessions(_dt.date(2025, 12, 1), home) if not r.note]


def test_audit_row_carries_the_session(home):
    path = _audit.write_entry({"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "abc"})
    assert json.loads(path.read_text().splitlines()[-1])["session"] == "abc"


def test_sessions_command(home):
    _write_claude(home)
    _write_antigravity(home)
    runner = CliRunner()
    res = runner.invoke(sessions_command, ["--all"])
    assert res.exit_code == 0, res.output
    assert "claude_code" in res.output and "antigravity" in res.output and "coin_seq" in res.output
    assert res.output.splitlines()[0].startswith("start")
    res = runner.invoke(sessions_command, ["--all", "--json"])
    data = json.loads(res.output)
    assert data["since"] is None and len([r for r in data["sessions"] if not r["note"]]) == 2
    res = runner.invoke(sessions_command, ["--since", "not-a-date"])
    assert res.exit_code != 0 and "YYYY" in res.output or "2026-11-16" in res.output


def test_unknown_tool_names_are_classed_by_what_they_say():
    ag = _hp.profiles()["antigravity"]
    assert ag.to_event({"toolCall": {"name": "edit_file", "args": {"Path": "/p"}}}).tool == "edit"
    assert ag.to_event({"toolCall": {"name": "create_file", "args": {"Path": "/p"}}}).tool == "write"
    assert ag.to_event({"toolCall": {"name": "run_terminal_cmd", "args": {"Cmd": "ls"}}}).command == "ls"
    assert ag.to_event({"toolCall": {"name": "search_web", "args": {"query": "x"}}}).tool == "other"
