"""
Purpose: Tests for the session-log hook (#292): each prompt lands in
         <vault>/sessions/<date>/<session>.md with time, project, repository
         and commit; a prompt with a PHI or secret pattern is withheld and
         the hook says so; the hook never blocks.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp vault (MURMURENT_VAULT_ROOT).
Output:  Assertions.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import subprocess
from pathlib import Path

from murmurent.commands import install_cmd
from murmurent.core import lab_notebook as nb
from murmurent.hooks import session_log as hook

WHEN = dt.datetime(2026, 11, 7, 14, 5, 9)


def _vault(tmp_path: Path, monkeypatch) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("MURMURENT_VAULT_ROOT", str(vault))
    monkeypatch.delenv("MURMURENT_NOTEBOOK_DIR", raising=False)
    monkeypatch.delenv("MURMURENT_SESSIONS_DIR", raising=False)
    return vault


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repos" / "p_demo"
    repo.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("murmurent: true\nlab: lab_mh\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "first"], check=True)
    return repo


def test_records_prompt_with_time_project_repository_and_commit(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    payload = {"session_id": "abc-123", "cwd": str(repo), "prompt": "Make the plot bigger."}
    assert hook.evaluate(payload, now=WHEN) is None
    f = vault / "sessions" / "2026-11-07" / "abc-123.md"
    text = f.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "project: p_demo" in text
    assert "## 14:05:09" in text
    assert "- repository: p_demo" in text
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert f"- commit: {head}" in text
    assert "Make the plot bigger." in text
    assert "audience: me" in text
    # a second prompt in the same session appends; the frontmatter is written once
    hook.evaluate({**payload, "prompt": "Now smaller."}, now=WHEN + dt.timedelta(minutes=1))
    text = f.read_text(encoding="utf-8")
    assert text.count("---\n") == 2
    assert "## 14:06:09" in text and "Now smaller." in text


def test_prompt_kept_verbatim_inside_a_longer_fence(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    prompt = "Run this:\n```bash\nls\n```\nthen report."
    hook.evaluate({"session_id": "s", "cwd": str(tmp_path), "prompt": prompt}, now=WHEN)
    text = (vault / "sessions" / "2026-11-07" / "s.md").read_text(encoding="utf-8")
    assert "````text\n" + prompt + "\n````" in text


def test_outside_a_repository_the_project_is_none(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    hook.evaluate({"session_id": "s", "cwd": str(tmp_path), "prompt": "hello"}, now=WHEN)
    text = (vault / "sessions" / "2026-11-07" / "s.md").read_text(encoding="utf-8")
    assert "- project: (none)" in text and "- commit: (none)" in text


def test_phi_shaped_prompt_is_withheld_and_said(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    note = hook.evaluate(
        {"session_id": "s", "cwd": str(tmp_path), "prompt": "Patient MRN-4471 came back"},
        now=WHEN)
    assert note is not None and "not recorded" in note and "MRN" in note
    assert not (vault / "sessions").exists()


def test_secret_shaped_prompt_is_withheld(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    note = hook.evaluate(
        {"session_id": "s", "cwd": str(tmp_path),
         "prompt": "use key AKIAIOSFODNN7EXAMPLE for the upload"}, now=WHEN)
    assert note is not None and "secret:" in note
    assert not (vault / "sessions").exists()


def test_main_never_blocks_and_is_quiet_when_recorded(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    out = io.StringIO()
    payload = json.dumps({"session_id": "s", "cwd": str(tmp_path), "prompt": "hi"})
    assert hook.main(io.StringIO(payload), out) == 0
    assert out.getvalue() == ""
    assert hook.main(io.StringIO("not json"), io.StringIO()) == 0
    assert hook.main(io.StringIO(""), io.StringIO()) == 0


def test_main_reports_a_withheld_prompt_as_context(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    out = io.StringIO()
    payload = json.dumps({"session_id": "s", "cwd": str(tmp_path), "prompt": "MRN-99999 x"})
    assert hook.main(io.StringIO(payload), out) == 0
    data = json.loads(out.getvalue())
    assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "not recorded" in data["hookSpecificOutput"]["additionalContext"]


def test_no_vault_means_no_record_and_no_error(tmp_path, monkeypatch):
    monkeypatch.delenv("MURMURENT_VAULT_ROOT", raising=False)
    monkeypatch.delenv("MURMURENT_NOTEBOOK_DIR", raising=False)
    monkeypatch.setattr(nb, "vault_root", lambda: None)
    assert hook.evaluate({"session_id": "s", "cwd": str(tmp_path), "prompt": "hi"}, now=WHEN) is None


def test_off_switch(tmp_path, monkeypatch):
    vault = _vault(tmp_path, monkeypatch)
    monkeypatch.setenv("MURMURENT_NO_SESSION_LOG", "1")
    assert hook.evaluate({"session_id": "s", "cwd": str(tmp_path), "prompt": "hi"}, now=WHEN) is None
    assert not (vault / "sessions").exists()


def test_hook_is_registered_by_install(tmp_path):
    target = tmp_path / "settings.json"
    install_cmd.cmd_install(hooks=True, settings_path=target, backup=False)
    settings = json.loads(target.read_text(encoding="utf-8"))
    cmds = [h.get("command", "") for e in settings["hooks"]["UserPromptSubmit"] for h in e["hooks"]]
    assert any("murmurent.hooks.session_log" in c for c in cmds)
