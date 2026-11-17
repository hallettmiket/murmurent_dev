"""`murmurent security acl-check` reports what the mode bits say and
prescribes nothing: no chmod line, exit 0, the caveat about a storage array's
own rules on every run."""

from __future__ import annotations

import json
import os
import stat

from murmurent.commands import security_cmd as _sc


def _root(tmp_path, immutable_mode: int, append_mode: int):
    (tmp_path / "immutable").mkdir()
    (tmp_path / "append_only").mkdir()
    os.chmod(tmp_path / "immutable", immutable_mode)
    os.chmod(tmp_path / "append_only", append_mode)
    return tmp_path


def test_shared_setgid_tree_is_described_not_fixed(tmp_path):
    root = _root(tmp_path, 0o2770, 0o2770)
    rows = {r["folder"]: r for r in _sc.acl_check_rows(root)}
    assert rows["immutable"]["state"] == "shared" and "set-gid" in rows["immutable"]["detail"]
    assert "the group" in rows["immutable"]["note"] and "only the hooks refuse" in rows["immutable"]["note"]
    assert "anyone in the group can delete" in rows["append_only"]["note"]
    assert all("chmod" not in r["note"] and "fix" not in r for r in rows.values())


def test_owner_only_and_sticky_are_named(tmp_path):
    root = _root(tmp_path, 0o755, 0o1770)
    rows = {r["folder"]: r for r in _sc.acl_check_rows(root)}
    assert rows["immutable"]["state"] == "owner-only"
    assert "sticky" in rows["append_only"]["detail"] and "deleted only by its owner" in rows["append_only"]["note"]
    assert bool(os.stat(root / "append_only").st_mode & stat.S_ISVTX)


def test_missing_folder_and_exit_code(tmp_path, capsys):
    (tmp_path / "immutable").mkdir()
    assert _sc.cmd_acl_check(str(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "append_only: no such folder" in out and "mode bits only" in out and "chmod" not in out
    assert _sc.cmd_acl_check(str(tmp_path), json_out=True) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["caveat"].startswith("mode bits only") and [r["folder"] for r in data["rows"]] == ["immutable", "append_only"]
    assert _sc.cmd_acl_check(None) == 2 if not (os.environ.get("MURMURENT_DATA_ROOT") or os.environ.get("MURMURENT_LAB_VM_ROOT")) else True
