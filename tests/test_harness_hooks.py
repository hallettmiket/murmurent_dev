"""Phase 2 of docs/harnesses_plan.md: the governance hooks hold in every
harness. The same recorded cases go through the Claude Code adapter and the
Antigravity adapter and get the same decisions; the adapter entry point
answers in Antigravity's shape; the audit, the agents log and the session
record carry the harness; hooks.json is rendered and merged; the ACL check
reads the filesystem. No harness is run."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.commands import harness_cmd, security_cmd
from murmurent.core import harness_antigravity as _ag
from murmurent.core import harness_policy as _hp
from murmurent.hooks import adapter as _adapter
from murmurent.hooks import audit as _audit

COMMONS = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(COMMONS))
    monkeypatch.setenv("MURMURENT_HARNESS_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("MURMURENT_AGENT_LOG", str(tmp_path / "agents.log"))
    monkeypatch.setenv("MURMURENT_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.delenv("MURMURENT_NO_SESSION_LOG", raising=False)
    monkeypatch.setattr(_hp, "lab_harnesses_path", lambda env=None: None)
    monkeypatch.setattr(_hp, "_machine_file", lambda: tmp_path / ".murmurent" / "machine.yaml")
    return tmp_path


@pytest.fixture
def data_root(monkeypatch, tmp_path):
    root = tmp_path / "data"
    for rel in ("immutable/proj/raw_1.csv", "append_only/proj/1_qc/result_1.csv"):
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(root))
    return root


def _cases(name: str, root: Path) -> list[dict]:
    text = (COMMONS / "templates" / "hook_payloads" / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text.replace("<DATA_ROOT>", str(root)))["cases"]


# ---------------------------------------------------------------------------
# The adapters
# ---------------------------------------------------------------------------


def test_both_adapters_produce_the_same_event(data_root):
    cc = _hp.profiles()["claude_code"]
    ag = _hp.profiles()["antigravity"]
    a = cc.to_event({"tool_name": "Bash", "tool_input": {"command": "rm x"}, "session_id": "s", "cwd": "/w"})
    b = ag.to_event({"toolCall": {"name": "run_command", "args": {"CommandLine": "rm x"}},
                     "conversationId": "s", "cwd": "/w"})
    assert (a.tool, a.command, a.session, a.cwd) == (b.tool, b.command, b.session, b.cwd) == ("shell", "rm x", "s", "/w")
    assert a.as_claude_call() == b.as_claude_call() == {"tool_name": "Bash", "tool_input": {"command": "rm x"}}
    w = ag.to_event({"toolCall": {"name": "write_to_file", "args": {"TargetFile": "/a/b.csv", "CodeContent": "hi"}}})
    assert (w.tool, w.path, w.content, w.tool_name) == ("write", "/a/b.csv", "hi", "write_to_file")
    other = ag.to_event({"toolCall": {"name": "browser_click", "args": {"x": 1}}})
    assert other.tool == "other" and other.as_claude_call()["tool_name"] == "browser_click"


def test_an_unexpected_path_key_does_not_blind_the_guard():
    ag = _hp.profiles()["antigravity"]
    ev = ag.to_event({"toolCall": {"name": "write_to_file", "args": {"Whatever": "/data/immutable/p/x.csv"}}})
    assert ev.path == "/data/immutable/p/x.csv"


@pytest.mark.parametrize("name", ["claude_code", "antigravity"])
def test_the_guards_answer_the_recorded_cases_alike(name, data_root):
    profile = _hp.profiles()[name]
    for case in _cases(name, data_root):
        decision, guard = _adapter.decide(profile.to_event(case["payload"]))
        assert decision["decision"] == case["expect"], (name, case["name"], decision, guard)
        if case["expect"] == "deny":
            assert guard in ("raw_guard", "protected_paths", "phi_check"), case["name"]


def test_from_decision_shapes():
    cc = _hp.profiles()["claude_code"]
    ag = _hp.profiles()["antigravity"]
    deny = {"decision": "deny", "reason": "no"}
    assert cc.from_decision(deny)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert cc.from_decision({"decision": "allow"}) == {}
    assert ag.from_decision(deny) == {"decision": "deny", "reason": "no"}
    assert ag.from_decision({"decision": "allow"}) == {"decision": "ask"}   # required field; own check decides


# ---------------------------------------------------------------------------
# The entry point and the records
# ---------------------------------------------------------------------------


def _run(argv: list[str], payload: dict) -> dict:
    out = io.StringIO()
    assert _adapter.main(argv, stdin=io.StringIO(json.dumps(payload)), stdout=out) == 0
    return json.loads(out.getvalue())


def test_entry_point_denies_in_antigravity_shape_and_audits_it(home, data_root):
    payload = {"hookEventName": "PreToolUse", "conversationId": "c1", "cwd": str(data_root),
               "modelName": "gemini-4-argon",
               "toolCall": {"name": "run_command", "args": {"CommandLine": f"rm {data_root}/immutable/proj/raw_1.csv"}}}
    answer = _run(["--harness", "antigravity", "--event", "PreToolUse"], payload)
    assert answer["decision"] == "deny" and "immutable" in answer["reason"]
    rows = [json.loads(l) for f in (home / "audit").glob("*.log") for l in f.read_text().splitlines()]
    assert rows and rows[-1]["harness"] == "antigravity" and rows[-1]["decision"] == "deny"
    assert rows[-1]["hook"] == "raw_guard" and rows[-1]["model"] == "gemini-4-argon"
    assert rows[-1]["place"] == "google_personal"


def test_entry_point_asks_for_an_allowed_call_and_audits_post(home, data_root):
    """Antigravity's contract says ``decision`` is required: its command-line
    tool refused every call answered ``{}`` (2026-11-16). ``ask`` leaves the
    call to Antigravity's own permission check."""
    payload = {"hookEventName": "PreToolUse", "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}
    assert _run(["--harness", "antigravity", "--event", "PreToolUse"], payload) == {"decision": "ask"}
    assert _run(["--harness", "antigravity", "--event", "PostToolUse"], dict(payload, error="exit status 1")) == {}
    rows = [json.loads(l) for f in (home / "audit").glob("*.log") for l in f.read_text().splitlines()]
    assert rows[-1]["outcome"] == "error" and rows[-1]["tool"] == "Bash" and rows[-1]["harness"] == "antigravity"


def test_entry_point_never_stops_the_harness(home, monkeypatch):
    assert _run(["--harness", "nope", "--event", "PreToolUse"], {"x": 1}) == {}
    out = io.StringIO()
    assert _adapter.main(["--harness", "antigravity", "--event", "PreToolUse"], stdin=io.StringIO("not json"), stdout=out) == 0
    assert json.loads(out.getvalue()) == {"decision": "ask"}      # unreadable input: the harness's own rules decide
    # A crash inside the adapter answers the same neutral shape, never a refusal.
    monkeypatch.setattr(_adapter, "handle", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _run(["--harness", "antigravity", "--event", "PreToolUse"], {"toolCall": {"name": "run_command"}}) == {"decision": "ask"}
    assert _run(["--harness", "antigravity", "--event", "PostToolUse"], {}) == {}
    assert _run(["--harness", "claude_code", "--event", "PreToolUse"], {}) == {}


def test_session_start_writes_the_agents_log_line(home):
    answer = _run(["--harness", "antigravity", "--event", "SessionStart"],
                  {"conversationId": "c1", "modelName": "gemini-4-argon", "cwd": str(home)})
    assert isinstance(answer, dict)
    line = (home / "agents.log").read_text(encoding="utf-8")
    assert "antigravity: session started (gemini-4-argon, google_personal)" in line


def test_pre_invocation_records_a_prompt_once(home, monkeypatch):
    seen: list[dict] = []
    from murmurent.hooks import session_log

    monkeypatch.setattr(session_log, "evaluate", lambda payload: seen.append(payload) or None)
    payload = {"conversationId": "c1", "cwd": str(home), "lastUserInput": "fix the test", "invocationNum": 1}
    _run(["--harness", "antigravity", "--event", "PreInvocation"], payload)
    _run(["--harness", "antigravity", "--event", "PreInvocation"], dict(payload, invocationNum=2))
    assert len(seen) == 1 and seen[0]["prompt"] == "fix the test" and seen[0]["session_id"] == "c1"
    _run(["--harness", "antigravity", "--event", "PreInvocation"], dict(payload, lastUserInput="now this"))
    assert len(seen) == 2


def test_claude_code_audit_rows_keep_their_defaults(home):
    path = _audit.write_entry({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    row = json.loads(path.read_text().splitlines()[-1])
    assert (row["harness"], row["place"], row["decision"]) == ("claude_code", "anthropic_cloud", "")


# ---------------------------------------------------------------------------
# hooks.json, the smoke command, the ACL check
# ---------------------------------------------------------------------------


def test_hooks_json_is_rendered_and_merged(home):
    ag = _hp.profiles()["antigravity"]
    target = home / _ag.CONFIG_DIR / _ag.HOOKS_FILE
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"theirs": {"Stop": [{"command": "./x.sh"}]}}), encoding="utf-8")
    ag.install(home, COMMONS)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "theirs" in data and _ag.HOOK_NAME in data
    pre = data[_ag.HOOK_NAME]["PreToolUse"][0]
    assert pre["matcher"] == _ag.GOVERNED_MATCHER
    assert "murmurent.hooks.adapter --harness antigravity --event PreToolUse" in pre["hooks"][0]["command"]
    assert "SessionStart" in data[_ag.HOOK_NAME] and "PreInvocation" in data[_ag.HOOK_NAME]
    assert ag.installed(home).yes is True
    assert "hooks" in ag.installed(home).detail


def test_smoke_command_passes_for_both(home):
    runner = CliRunner()
    for name in ("antigravity", "claude_code"):
        res = runner.invoke(harness_cmd.harness_group, ["smoke", name])
        assert res.exit_code == 0, res.output
        assert "BAD" not in res.output and "as expected" in res.output


def test_acl_check_describes_and_prescribes_nothing(tmp_path):
    """The full cases are in test_acl_check.py; here only that the command
    runs from the CLI and never prints a chmod line."""
    root = tmp_path / "lab"
    (root / "immutable").mkdir(parents=True)
    (root / "append_only").mkdir()
    (root / "immutable").chmod(0o2770)
    (root / "append_only").chmod(0o2770)
    res = CliRunner().invoke(_cli(), ["security", "acl-check", str(root)])
    assert res.exit_code == 0 and "chmod" not in res.output and "Nothing was changed" in res.output
    assert security_cmd.acl_check_rows(tmp_path / "nowhere")[0]["state"] == "missing"


def _cli():
    from murmurent.cli import cli

    return cli


def test_hooks_json_carries_the_data_root(home, monkeypatch):
    """The App is started from the Dock with no shell variables, so the hook
    command must carry the data root itself."""
    ag = _hp.profiles()["antigravity"]
    monkeypatch.setenv("MURMURENT_DATA_ROOT", "/data/lab vm")
    rep = ag.install(home, COMMONS)
    data = json.loads((home / _ag.CONFIG_DIR / _ag.HOOKS_FILE).read_text(encoding="utf-8"))
    cmd = data[_ag.HOOK_NAME]["PreToolUse"][0]["hooks"][0]["command"]
    assert cmd.startswith("MURMURENT_DATA_ROOT='/data/lab vm' ")
    assert any("carry the data root /data/lab vm" in n for n in rep.notes)
    monkeypatch.delenv("MURMURENT_DATA_ROOT")
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    rep = ag.install(home, COMMONS)
    data = json.loads((home / _ag.CONFIG_DIR / _ag.HOOKS_FILE).read_text(encoding="utf-8"))
    assert not data[_ag.HOOK_NAME]["PreToolUse"][0]["hooks"][0]["command"].startswith("MURMURENT_DATA_ROOT")
    assert any("MURMURENT_DATA_ROOT is not set" in w for w in rep.warnings)
