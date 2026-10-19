"""Tests for the automatic two-way vault sync and its Claude Code hook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from murmurent.core import vault_sync as vs
from murmurent.hooks import vault_sync as hook


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def machines(tmp_path, monkeypatch):
    """A GitHub stand-in (a bare repo) and two machines' copies of the vault."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    copies = {}
    for name in ("laptop", "server"):
        d = tmp_path / name
        subprocess.run(["git", "clone", "-q", str(remote), str(d)], check=True,
                       capture_output=True)
        _git(d, "config", "user.email", "t@example.org")
        _git(d, "config", "user.name", "T")
        _git(d, "checkout", "-q", "-B", "main")
        copies[name] = d
    (copies["laptop"] / "oracle").mkdir()
    (copies["laptop"] / "oracle" / "start.md").write_text("start\n")
    _git(copies["laptop"], "add", "-A")
    _git(copies["laptop"], "commit", "-q", "-m", "start")
    _git(copies["laptop"], "push", "-q", "-u", "origin", "main")
    _git(copies["server"], "pull", "-q", "origin", "main")
    _git(copies["server"], "branch", "-q", "--set-upstream-to=origin/main", "main")
    state = {"root": copies["laptop"]}
    monkeypatch.setattr(vs, "personal_vault_root", lambda: state["root"])

    def on(name: str) -> Path:
        state["root"] = copies[name]
        return copies[name]
    return remote, copies, on


def _note(path: Path, sensitivity: str, body: str = "a finding\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: x\nsensitivity: {sensitivity}\n---\n{body}")


def test_notes_are_sent_but_protected_and_restricted_ones_stay(machines):
    remote, copies, on = machines
    lap = on("laptop")
    _note(lap / "oracle" / "open.md", "standard")
    _note(lap / "oracle" / "patients.md", "protected")
    _note(lap / "oracle" / "patent.md", "restricted")
    res = vs.sync()
    assert res.ok and res.pushed
    assert sorted(res.kept_local) == ["oracle/patent.md", "oracle/patients.md"]
    sent = _git(lap, "ls-tree", "-r", "--name-only", "origin/main")
    assert "oracle/open.md" in sent
    assert "patients" not in sent and "patent" not in sent
    assert (lap / "oracle" / "patients.md").exists()          # still here


def test_two_machines_each_get_the_others_notes(machines):
    remote, copies, on = machines
    _note(on("laptop") / "lab-notebook" / "2026-10-19.md", "standard", "laptop day\n")
    assert vs.sync().ok
    _note(on("server") / "oracle" / "server_note.md", "standard")
    assert vs.sync().ok                                          # rebases onto the laptop's
    on("laptop")
    assert vs.sync().ok
    assert (copies["laptop"] / "oracle" / "server_note.md").exists()
    assert (copies["server"] / "lab-notebook" / "2026-10-19.md").exists()


def test_the_same_note_changed_on_both_loses_nothing(machines):
    remote, copies, on = machines
    (on("laptop") / "oracle" / "start.md").write_text("laptop version\n")
    assert vs.sync().ok
    (on("server") / "oracle" / "start.md").write_text("server version\n")
    res = vs.sync()
    assert res.diverged and not res.pushed
    # The server's edit is still committed there, waiting to be reconciled.
    assert _git(copies["server"], "show", "HEAD:oracle/start.md") == "server version\n"


def test_the_hook_syncs_after_a_write_in_the_vault_only(machines, monkeypatch):
    remote, copies, on = machines
    lap = on("laptop")
    started = []
    monkeypatch.setattr(hook, "_spawn_worker", lambda: started.append(1))
    monkeypatch.delenv("MURMURENT_NO_VAULT_SYNC", raising=False)
    hook.handle({"hook_event_name": "PostToolUse", "tool_name": "Write",
                 "tool_input": {"file_path": str(lap / "oracle" / "n.md")}})
    hook.handle({"hook_event_name": "PostToolUse", "tool_name": "Write",
                 "tool_input": {"file_path": "/tmp/elsewhere.md"}})
    assert started == [1]
    hook.handle({"hook_event_name": "Stop"})                     # nothing changed
    assert started == [1]
    (lap / "oracle" / "typed.md").write_text("x\n")
    hook.handle({"hook_event_name": "Stop"})
    assert started == [1, 1]
    monkeypatch.setenv("MURMURENT_NO_VAULT_SYNC", "1")
    hook.handle({"hook_event_name": "Stop"})
    assert started == [1, 1]


def test_the_worker_syncs_and_logs(machines, monkeypatch, tmp_path):
    remote, copies, on = machines
    lap = on("laptop")
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    _note(lap / "oracle" / "w.md", "standard")
    hook.run_worker()
    assert "oracle/w.md" in _git(lap, "ls-tree", "-r", "--name-only", "origin/main")
    assert "synced" in (tmp_path / "home" / "vault_sync.log").read_text()


def test_install_registers_the_three_vault_hooks():
    from murmurent.commands.install_cmd import HOOK_REGISTRATIONS
    events = {r["event"] for r in HOOK_REGISTRATIONS if r.get("module") == "murmurent.hooks.vault_sync"}
    assert events == {"SessionStart", "PostToolUse", "Stop"}
