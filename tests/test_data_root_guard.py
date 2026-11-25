"""
Purpose: Pin :mod:`murmurent.hooks.data_root_guard`, the hook for the parts
         of the data root the two tier guards leave alone.

         - modifiable/: create, overwrite, delete all ALLOW
         - mothballed/: create, overwrite, delete all DENY
         - anywhere else under the root (release/, cottage/, tools/, db/, an
           unlisted folder, a loose file at the top): create ALLOW,
           overwrite DENY, delete or move out ASK
         - immutable/, raw/, append_only/, refined/: ALLOW here (their own
           hooks rule on them)
         - outside the root, or with no root set: ALLOW
Author: Mike Hallett (with Claude Code)
Date: 2026-11-25
Input: synthetic tool calls; no network.
Output: pytest cases.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from murmurent.hooks import data_root_guard as g


def _run(payload: dict) -> dict:
    stdout = io.StringIO()
    assert g.main(stdin=io.StringIO(json.dumps(payload)), stdout=stdout) == 0
    raw = stdout.getvalue().strip()
    if not raw:
        return {"decision": "allow"}
    hso = json.loads(raw)["hookSpecificOutput"]
    return {"decision": hso["permissionDecision"], "reason": hso["permissionDecisionReason"]}


def _write(path) -> dict:
    return _run({"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x"}})


def _edit(path) -> dict:
    return _run({"tool_name": "Edit", "tool_input": {"file_path": str(path), "old_string": "a", "new_string": "b"}})


def _bash(command: str) -> dict:
    return _run({"tool_name": "Bash", "tool_input": {"command": command}})


@pytest.fixture
def root(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    for folder in ("immutable", "append_only", "modifiable", "mothballed", "release", "cottage", "tools", "odd"):
        (tmp_path / folder / "proj").mkdir(parents=True)
        (tmp_path / folder / "proj" / "old.csv").write_text("1\n", encoding="utf-8")
    (tmp_path / "loose.txt").write_text("x\n", encoding="utf-8")
    return tmp_path


# -- where a path sits ------------------------------------------------------


def test_tier_of(root):
    assert g.tier_of(str(root / "immutable" / "p")) == "own_hook"
    assert g.tier_of(str(root / "refined" / "p")) == "own_hook"
    assert g.tier_of(str(root / "modifiable" / "p")) == "modifiable"
    assert g.tier_of(str(root / "mothballed" / "p")) == "mothballed"
    assert g.tier_of(str(root / "release" / "p")) == "other"
    assert g.tier_of(str(root / "loose.txt")) == "other"
    assert g.tier_of(str(root)) == "other"
    assert g.tier_of("/somewhere/else") == ""
    assert g.tier_of("relative/path") == ""


def test_no_root_set_allows_everything(monkeypatch, tmp_path):
    monkeypatch.delenv("MURMURENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    assert _bash(f"rm -rf {tmp_path}/mothballed")["decision"] == "allow"


# -- modifiable: free -------------------------------------------------------


def test_modifiable_allows_overwrite_and_delete(root):
    old = root / "modifiable" / "proj" / "old.csv"
    assert _write(old)["decision"] == "allow"
    assert _edit(old)["decision"] == "allow"
    assert _bash(f"rm -rf {root}/modifiable/proj")["decision"] == "allow"
    assert _bash(f"echo 1 > {old}")["decision"] == "allow"


# -- mothballed: never touched ---------------------------------------------


def test_mothballed_denies_everything(root):
    folder = root / "mothballed" / "proj"
    assert _write(folder / "new.csv")["decision"] == "deny"
    assert _edit(folder / "old.csv")["decision"] == "deny"
    r = _bash(f"rm {folder}/old.csv")
    assert r["decision"] == "deny" and "mothballed" in r["reason"]
    assert _bash(f"cp a.csv {folder}/b.csv")["decision"] == "deny"
    assert _bash(f"gzip -k {folder}/old.csv > {folder}/old.csv.gz")["decision"] == "deny"


# -- everywhere else: new file yes, overwrite no, delete asks ---------------


@pytest.mark.parametrize("folder", ["release", "cottage", "tools", "odd"])
def test_other_folders_create_allowed_overwrite_denied_delete_asks(root, folder):
    old = root / folder / "proj" / "old.csv"
    assert _write(root / folder / "proj" / "new.csv")["decision"] == "allow"
    assert _bash(f"mkdir -p {root}/{folder}/proj/sub && echo 1 > {root}/{folder}/proj/sub/new.txt")["decision"] == "allow"
    r = _write(old)
    assert r["decision"] == "deny" and "versioned" in r["reason"]
    assert _edit(old)["decision"] == "deny"
    assert _bash(f"echo 1 > {old}")["decision"] == "deny"
    assert _bash(f"echo 1 >> {old}")["decision"] == "deny"
    assert _bash(f"truncate -s 0 {old}")["decision"] == "deny"
    r = _bash(f"rm {old}")
    assert r["decision"] == "ask" and "permission" in r["reason"]
    assert _bash(f"rm -rf {root}/{folder}/proj")["decision"] == "ask"
    assert _bash(f"mv {old} /tmp/elsewhere.csv")["decision"] == "ask"


def test_loose_file_at_the_top(root):
    assert _write(root / "loose.txt")["decision"] == "deny"
    assert _write(root / "new_loose.txt")["decision"] == "allow"
    assert _bash(f"rm {root}/loose.txt")["decision"] == "ask"


def test_move_into_other_folder(root):
    assert _bash(f"mv /tmp/a.csv {root}/release/proj/fresh.csv")["decision"] == "allow"
    assert _bash(f"mv /tmp/a.csv {root}/release/proj/old.csv")["decision"] == "deny"
    assert _bash(f"cp /tmp/a.csv {root}/tools/proj/old.csv")["decision"] == "deny"


def test_strictest_operation_wins(root):
    # a delete (ask) and an overwrite (deny) in one command: deny
    old = root / "release" / "proj" / "old.csv"
    assert _bash(f"rm {root}/tools/proj/old.csv && echo 1 > {old}")["decision"] == "deny"


# -- the tiers with their own hooks are left alone -------------------------


def test_own_hook_tiers_are_not_ruled_on_here(root):
    for folder in ("immutable", "append_only"):
        old = root / folder / "proj" / "old.csv"
        assert _write(old)["decision"] == "allow"
        assert _bash(f"rm {old}")["decision"] == "allow"


def test_outside_the_root_is_allowed(root, tmp_path):
    assert _bash("rm -rf /tmp/scratch")["decision"] == "allow"
    assert _write("/tmp/scratch/x.txt")["decision"] == "allow"


def test_reads_and_bad_input_are_allowed(root):
    assert _run({"tool_name": "Read", "tool_input": {"file_path": str(root / "mothballed" / "proj" / "old.csv")}})["decision"] == "allow"
    stdout = io.StringIO()
    g.main(stdin=io.StringIO("not json"), stdout=stdout)
    assert stdout.getvalue() == ""


def test_hook_is_registered_in_install_cmd():
    from murmurent.commands.install_cmd import HOOK_REGISTRATIONS
    labels = [h["label"] for h in HOOK_REGISTRATIONS]
    assert "murmurent-data-root-guard" in labels
    assert labels.index("murmurent-data-root-guard") > labels.index("murmurent-protected-paths")
