"""
Purpose: Pin :mod:`murmurent.hooks.remote_paths` and the three guards' use of
         it: a Bash command that reaches a declared host's data root over ssh,
         scp or rsync is judged by the same rules as a local path, against
         that host's root, with the file's existence asked of the host.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-25
Input: synthetic commands; the host table is faked, no ssh is run.
Output: pytest cases.
"""

from __future__ import annotations

import io
import json
import os

import pytest

from murmurent.hooks import data_root_guard as drg
from murmurent.hooks import protected_paths as pp
from murmurent.hooks import raw_guard as rg
from murmurent.hooks import remote_paths as rp

ROOT = "/srv/lab"
ROOTS = {"srv": ROOT, "srv.example.edu": ROOT}


def _decision(module, payload: dict) -> dict:
    stdout = io.StringIO()
    assert module.main(stdin=io.StringIO(json.dumps(payload)), stdout=stdout) == 0
    raw = stdout.getvalue().strip()
    if not raw:
        return {"decision": "allow", "reason": ""}
    hso = json.loads(raw)["hookSpecificOutput"]
    return {"decision": hso["permissionDecision"], "reason": hso["permissionDecisionReason"]}


def _bash(module, command: str) -> dict:
    return _decision(module, {"tool_name": "Bash", "tool_input": {"command": command}})


@pytest.fixture
def hosts(monkeypatch, tmp_path):
    """A declared host with a data root that is nowhere on this machine, and a
    laptop whose own root is elsewhere; existence on the host is faked."""
    monkeypatch.setattr(rp, "remote_roots", lambda: dict(ROOTS))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "laptop_root"))
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    present: set[str] = set()
    monkeypatch.setattr(rp, "REMOTE_EXISTS", lambda host, path: path in present)
    return present


# -- finding the stretches that run on a host --------------------------------


def test_views_ssh_with_options_and_user(hosts):
    v = rp.views("ssh -o BatchMode=yes -p 22 -t mhallet@srv.example.edu 'cd /tmp && ls /srv/lab'")
    assert v == [("srv.example.edu", ROOT, "cd /tmp && ls /srv/lab")]


def test_views_unknown_host_is_nobodys_business(hosts):
    assert rp.views("ssh elsewhere 'touch /srv/lab/immutable/x'") == []
    assert rp.views("ls /srv/lab") == []


def test_views_copy_operands(hosts):
    v = rp.views("rsync -av ./out/ srv:/srv/lab/append_only/p/ other:/x")
    assert v == [("srv", ROOT, "rsync -av ./out/ /srv/lab/append_only/p/ other:/x")]
    v = rp.views("scp srv:/srv/lab/tools/a.txt ./a.txt")
    assert v == [("srv", ROOT, "scp /srv/lab/tools/a.txt ./a.txt")]


def test_views_two_ssh_calls(hosts):
    v = rp.views("ssh srv 'ls /srv/lab' && ssh srv.example.edu uptime")
    assert [x[0] for x in v] == ["srv", "srv.example.edu"]


def test_on_host_restores_the_environment(hosts, tmp_path):
    before = os.environ["MURMURENT_DATA_ROOT"]
    with rp.on_host("srv", ROOT):
        assert os.environ["MURMURENT_DATA_ROOT"] == ROOT
        assert rp.active_host() == "srv"
    assert os.environ["MURMURENT_DATA_ROOT"] == before
    assert rp.active_host() == ""


def test_unreachable_host_counts_as_existing(monkeypatch, hosts):
    monkeypatch.setattr(rp, "REMOTE_EXISTS", None)

    def boom(*a, **k):
        raise OSError("no ssh")
    monkeypatch.setattr(rp.subprocess, "run", boom)
    with rp.on_host("srv", ROOT):
        assert rp.exists("/srv/lab/tools/x") is True


def test_env_override_declares_a_host(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path))          # no hosts.yaml
    monkeypatch.setenv(rp.ENV_OVERRIDE, "box=/mnt/data, user@two=/d2")
    import murmurent.core.machine_policy as mp
    monkeypatch.setattr(mp, "load_machines", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("none")))
    roots = rp.remote_roots()
    assert roots["box"] == "/mnt/data" and roots["two"] == "/d2"


# -- the three guards, through ssh -----------------------------------------


def test_raw_guard_refuses_a_write_under_the_hosts_immutable(hosts):
    r = _bash(rg, "ssh srv 'cp /tmp/a.csv /srv/lab/immutable/proj/a.csv'")
    assert r["decision"] == "deny" and "on srv" in r["reason"]
    assert _bash(rg, "ssh srv 'cp /tmp/a.csv /tmp/b.csv'")["decision"] == "allow"


def test_protected_paths_asks_the_host_whether_the_file_exists(hosts):
    target = "/srv/lab/append_only/proj/old.csv"
    assert _bash(pp, f"ssh srv 'echo 1 > {target}'")["decision"] == "allow"   # new on the host
    hosts.add(target)
    r = _bash(pp, f"ssh srv 'echo 1 > {target}'")
    assert r["decision"] == "deny" and "on srv" in r["reason"]
    r = _bash(pp, f"rsync -av ./out.csv srv:{target}")
    assert r["decision"] == "deny"
    assert _bash(pp, "rsync -av ./out.csv srv:/srv/lab/append_only/proj/new.csv")["decision"] == "allow"


def test_data_root_guard_rules_on_the_hosts_other_folders(hosts):
    old = "/srv/lab/tools/old.sh"
    hosts.add(old)
    assert _bash(drg, "ssh srv 'cp /tmp/x /srv/lab/cottage/me/new.txt'")["decision"] == "allow"
    r = _bash(drg, f"ssh srv 'cp /tmp/x {old}'")
    assert r["decision"] == "deny" and "srv:" in r["reason"]
    r = _bash(drg, f"ssh srv 'rm {old}'")
    assert r["decision"] == "ask" and "permission" in r["reason"]
    assert _bash(drg, "ssh srv 'rm /srv/lab/modifiable/proj/scratch.bin'")["decision"] == "allow"


def test_local_root_is_still_judged_locally(hosts, tmp_path):
    local_old = tmp_path / "laptop_root" / "tools" / "old.sh"
    local_old.parent.mkdir(parents=True)
    local_old.write_text("x\n", encoding="utf-8")
    assert _bash(drg, f"rm {local_old}")["decision"] == "ask"
