"""
Purpose: tests for issue #151, step 3, the lab-wide space scan: every project's
         data folders and the unclaimed folders are scanned; dormant projects
         get a mothballing row; the report, the Slack summary (no file names),
         fetching it from another machine, the schedule, and the dashboard's
         PI-only Space page.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-17
Input: temporary folders only. No network, no systemd, no Slack.
Output: pass or fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import project_unit as pu
from murmurent.core import space_lab as sl
from murmurent.core import space_scan as ss
from murmurent.core import space_schedule as sch
from murmurent.core import space_table as st
from murmurent.core.millwright_policy import POLICY_ENV

MB = 1024 * 1024
DAY = 86400
ME = ss.owner_name(os.getuid())


@pytest.fixture
def lab(monkeypatch, tmp_path):
    """A data root with two projects (one long unused) and one unclaimed folder."""
    data = tmp_path / "data"
    lab_mgmt = tmp_path / "lab_mgmt"
    for d in (data / "immutable", data / "append_only", lab_mgmt, tmp_path / "home"):
        d.mkdir(parents=True)
    (tmp_path / "policy.yaml").write_text(yaml.safe_dump({"compress_min_mb": 1,
                                                          "duplicate_min_mb": 1}))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(data))
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv(POLICY_ENV, str(tmp_path / "policy.yaml"))
    monkeypatch.setattr(pu, "this_machine_lab", lambda: "mh")
    monkeypatch.setattr(ss, "member_logins", lambda _cp: ({ME}, []))
    for name in ("brca", "old_study"):
        cp.upsert(name, lab="mh", lead="@tester", member="tester")
        (data / "append_only" / name).mkdir()
    cp.upsert("other_lab", lab="xy", lead="@someone", member="someone")
    (data / "append_only" / "other_lab").mkdir()

    def write(rel: str, size: int = 10, age_days: float = 0, seed: int = 0) -> Path:
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((f"{seed}:{rel}".encode() * (size // 8 + 1))[:size])
        if age_days:
            then = time.time() - age_days * DAY
            os.utime(path, (then, then))
        return path

    write("append_only/brca/01_align/reads.fastq", 2 * MB)
    write("append_only/old_study/01_x/table.csv", 1000, age_days=3 * 365)
    write("append_only/mystery_dump/notes.txt", 500)
    write("append_only/other_lab/secret.txt", 50)
    return {"data": data, "lab_mgmt": lab_mgmt, "write": write, "tmp": tmp_path}


def test_the_lab_scan_covers_projects_and_unclaimed_folders(lab):
    report = sl.scan_lab()
    names = {p["name"] for p in report["projects"]}
    assert names == {"brca", "old_study"}                 # other labs are left alone
    assert report["unclaimed"]["files"] == 1
    conn = st.connect()
    [row] = st.rows(conn, sl.UNCLAIMED_PROJECT, category=st.UNCLAIMED)
    assert row["path"].endswith("append_only/mystery_dump") and row["owner"] == ME
    assert st.rows(conn, "brca", category=st.COMPRESSIBLE)
    assert not st.rows(conn, "other_lab", include_settled=True)


def test_a_long_unused_project_is_dormant_and_mothballing_is_suggested(lab):
    report = sl.scan_lab()
    old = next(p for p in report["projects"] if p["name"] == "old_study")
    assert old["activity"] == pu.DORMANT
    [row] = st.rows(st.connect(), "old_study", category=st.DORMANT)
    assert row["suggestion"] == st.MOTHBALL and "has not been used since" in row["reason"]
    brca = next(p for p in report["projects"] if p["name"] == "brca")
    assert brca["activity"] == pu.ACTIVE


def test_a_lab_scan_keeps_rows_an_in_session_scan_found_in_repositories(lab):
    conn = st.connect()
    repo_row = st.Item(path="/home/someone/repos/brca/big.h5", category=st.OUT_OF_PLACE,
                       suggestion=st.MOVE, reason="r", size=5)
    st.record_scan(conn, st.ScanSummary(project="brca", started_at=st.now_iso(),
                                        items=[repo_row]))
    sl.scan_lab()
    paths = [r["path"] for r in st.rows(conn, "brca", include_settled=True)]
    assert "/home/someone/repos/brca/big.h5" in paths


def test_folders_under_the_older_names_are_listed_one_by_one(lab):
    lab["write"]("refined/legacy_project/out.csv", 100)
    lab["write"]("campervans/trip.txt", 100)
    folders = {str(f.relative_to(lab["data"])) for f in sl.top_level_folders()}
    assert {"refined/legacy_project", "campervans", "append_only/mystery_dump"} <= folders
    assert "refined" not in folders and "append_only" not in folders


def test_a_file_the_scan_may_not_look_at_does_not_stop_it(lab, monkeypatch):
    real = Path.is_file

    def guarded(self):
        if self.name == "pyvenv.cfg":
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "is_file", guarded)
    report = sl.scan_lab()
    assert {p["name"] for p in report["projects"]} == {"brca", "old_study"}


@pytest.mark.skipif(os.geteuid() == 0, reason="permissions do not bind the root account")
def test_what_cannot_be_read_is_reported_by_owner_with_the_fix(lab):
    locked = lab["data"] / "append_only" / "brca" / "02_locked"
    lab["write"]("append_only/brca/02_locked/hidden.csv", 100)
    peek_only = lab["data"] / "append_only" / "brca" / "03_names_only"
    lab["write"]("append_only/brca/03_names_only/a.csv", 100)
    lab["write"]("append_only/brca/03_names_only/b.csv", 100)
    locked.chmod(0o000)
    peek_only.chmod(0o444)          # names can be listed, nothing can be looked at
    try:
        report = sl.scan_lab()
    finally:
        locked.chmod(0o755)
        peek_only.chmod(0o755)
    blind = report["unreadable"]
    assert blind["items"] == 3 and blind["by_owner"] == {ME: 3}
    rows = {r["path"]: r for r in st.rows(st.connect(), "brca", category=st.UNREADABLE)}
    assert "chmod -R g+rX" in rows[str(locked)]["reason"]
    assert rows[str(peek_only)]["n_files"] == 2
    assert any(line.startswith("Not readable: 3 items") for line in sl.describe(report))
    assert "3 items could not be read" in sl.slack_summary(report)


def test_folder_rows_do_not_count_twice_or_crowd_out_what_to_act_on(lab):
    report = sl.scan_lab()
    unclaimed = report["unclaimed"]
    assert st.UNCLAIMED not in unclaimed["by_category"]           # the folder row itself
    assert unclaimed["waiting_bytes"] <= unclaimed["bytes"]
    assert all(t["category"] not in sl.CONTAINERS for t in report["top"])
    [folder] = report["unclaimed_folders"]
    assert folder["path"].endswith("append_only/mystery_dump") and ME in folder["owners"]
    old = next(p for p in report["projects"] if p["name"] == "old_study")
    assert st.DORMANT not in old["by_category"]
    assert report["dormant"] and report["dormant"][0]["project"] == "old_study"
    text = "\n".join(sl.describe(report))
    assert "Folders no project claims" in text and "Dormant projects" in text


def test_a_project_whose_data_folders_are_missing_is_still_reported(lab):
    cp.upsert("Murmurent", lab="mh", lead="@tester", member="tester")
    report = sl.scan_lab()
    entry = next(p for p in report["projects"] if p["name"] == "Murmurent")
    assert entry["no_data"] and any("append_only/Murmurent" in f for f in entry["looked_in"])
    assert any("no data folder found" in line for line in sl.describe(report))
    assert "Projects whose data folders were not found: Murmurent" in sl.slack_summary(report)


def test_the_report_can_be_rebuilt_from_the_table_without_rescanning(lab, monkeypatch):
    sl.scan_lab()
    report = sl.read_report()
    report["top"] = []                       # as if made by an older version
    sl._write_report(report)
    monkeypatch.setattr(sl.ss if hasattr(sl, "ss") else ss, "scan_project",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("rescanned")))
    rebuilt = sl.rebuild_report()
    assert rebuilt["top"] and "rebuilt_at" in rebuilt
    out = CliRunner().invoke(cli, ["space", "lab", "--rebuild"])
    assert out.exit_code == 0 and "Lab mh space report" in out.output


def test_a_disk_is_named_by_its_mount_point(tmp_path):
    assert sl.mount_point(str(tmp_path)) in [str(p) for p in [tmp_path, *tmp_path.parents]]
    assert os.path.ismount(sl.mount_point(str(tmp_path)))


def test_two_lab_scans_cannot_run_at_once(lab):
    with sl._lock():
        with pytest.raises(sl.LabScanBusy):
            sl.scan_lab()


def test_the_report_is_written_privately_and_reads_back(lab):
    sl.scan_lab()
    path = sl.report_path()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    report = sl.read_report()
    lines = sl.describe(report)
    assert lines[0].startswith("Lab mh space report")
    assert any("old_study" in line and "dormant" in line for line in lines)


def test_the_slack_summary_names_no_file_or_folder(lab):
    report = sl.scan_lab()
    text = sl.slack_summary(report)
    assert str(lab["data"]) not in text and "reads.fastq" not in text
    assert "Dormant, mothballing suggested: old_study" in text


def test_the_summary_goes_to_the_pi_through_the_labs_bot(lab, monkeypatch):
    from murmurent.core import membership
    report = sl.scan_lab()
    monkeypatch.setattr("murmurent.core.lab.pi_handle", lambda: "tester")
    monkeypatch.setattr(membership, "get", lambda h: type("R", (), {"slack": "U123",
                                                                    "email": "t@x"})())
    sent = {}

    def fake_send(group, *, text, slack, email):
        sent.update(group=group, text=text, slack=slack)
        return True, "sent"

    assert sl.notify_pi(report, send=fake_send) == (True, "sent")
    assert sent["group"] == "mh" and sent["slack"] == "U123"


def test_the_report_can_be_fetched_from_another_machine(lab, monkeypatch):
    from murmurent.core import hosts
    from murmurent.core import remote
    report = sl.scan_lab()
    monkeypatch.setattr(hosts, "resolve", lambda name: hosts.Host(name=name, kind="ssh",
                                                                  ssh_host="server"))
    calls = []

    def fake_run(self, command, **kw):
        calls.append(command)
        return remote.RemoteResult(host="server", command=command, returncode=0,
                                   stdout=json.dumps(report), stderr="")

    monkeypatch.setattr(remote.Remote, "run", fake_run)
    assert sl.fetch_report("server")["lab"] == "mh"
    assert calls == ["murmurent space lab --json"]

    out = CliRunner().invoke(cli, ["space", "lab", "--host", "server"])
    assert out.exit_code == 0 and "old_study" in out.output


def test_a_notice_printed_at_login_does_not_spoil_the_report(lab, monkeypatch):
    from murmurent.core import hosts
    from murmurent.core import remote
    report = sl.scan_lab()
    monkeypatch.setattr(hosts, "resolve", lambda name: hosts.Host(name=name, kind="ssh"))
    noisy = ("REMINDER: Please run CPU-intensive processes with 'nice -n 19 command'\n"
             "Example: nice -n 19 python my_script.py {not json}\n" + json.dumps(report, indent=2))
    monkeypatch.setattr(remote.Remote, "run", lambda self, command, **kw: remote.RemoteResult(
        host="server", command=command, returncode=0, stdout=noisy, stderr=""))
    assert sl.fetch_report("server")["lab"] == "mh"


def test_a_machine_with_no_report_yet_says_so(lab, monkeypatch):
    from murmurent.core import hosts
    from murmurent.core import remote
    monkeypatch.setattr(hosts, "resolve", lambda name: hosts.Host(name=name, kind="ssh"))

    def fake_run(self, command, **kw):
        raise remote.RemoteError("x", returncode=1, stdout="",
                                 stderr="Error: no lab space report on this computer yet.")

    monkeypatch.setattr(remote.Remote, "run", fake_run)
    assert sl.fetch_report("server") is None


# ---------------------------------------------------------------------------
# The schedule
# ---------------------------------------------------------------------------


class FakeSystemctl:
    def __init__(self, linger: str = "no"):
        self.calls: list[list[str]] = []
        self.linger = linger

    def __call__(self, argv):
        self.calls.append(argv)
        out = ""
        if argv[:2] == ["loginctl", "show-user"]:
            out = f"Linger={self.linger}\n"
        elif "is-active" in argv:
            out = "active\n"
        elif "show" in argv:
            out = "Sun 2026-10-18 02:00:00 EDT\n"
        return subprocess.CompletedProcess(argv, 0, out, "")


def test_calendar_lines_and_mistakes():
    assert sch.calendar("sun", "02:00") == "Sun *-*-* 02:00:00"
    assert sch.calendar("Wednesday", "23:30") == "Wed *-*-* 23:30:00"
    for day, at in (("someday", "02:00"), ("sun", "25:00"), ("sun", "2am")):
        with pytest.raises(ValueError):
            sch.calendar(day, at)


def test_install_writes_the_units_switches_on_and_records_it(lab, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lab["tmp"] / "config"))
    fake = FakeSystemctl(linger="no")
    result = sch.install("sun", "02:00", run=fake)
    service = (sch.unit_dir() / f"{sch.UNIT}.service").read_text()
    timer = (sch.unit_dir() / f"{sch.UNIT}.timer").read_text()
    assert "space scan-lab --notify" in service and "Nice=19" in service
    assert f"MURMURENT_DATA_ROOT={lab['data']}" in service
    assert "OnCalendar=Sun *-*-* 02:00:00" in timer and "Persistent=true" in timer
    assert ["systemctl", "--user", "enable", "--now", f"{sch.UNIT}.timer"] in fake.calls
    text = "\n".join(result.lines())
    assert "only while you are logged in" in text and "enable-linger" in text
    recorded = (lab["lab_mgmt"] / "policy" / "scheduled_jobs.md").read_text()
    assert "Weekly lab space scan" in recorded and "May not" in recorded

    sch.remove(run=fake)
    assert not (sch.unit_dir() / f"{sch.UNIT}.timer").exists()
    assert "Weekly lab space scan" not in (lab["lab_mgmt"] / "policy" /
                                          "scheduled_jobs.md").read_text()


def test_with_lingering_on_it_says_the_scan_runs_while_logged_out(lab, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lab["tmp"] / "config"))
    result = sch.install(run=FakeSystemctl(linger="yes"))
    assert any("whether or not you are logged in" in line for line in result.lines())


# ---------------------------------------------------------------------------
# The dashboard's Space page
# ---------------------------------------------------------------------------


def test_the_space_report_is_for_the_pi_only(lab, monkeypatch):
    from fastapi.testclient import TestClient

    from murmurent.dashboard.server import create_app
    sl.scan_lab()
    client = TestClient(create_app())
    from murmurent.core import membership
    monkeypatch.setattr(membership, "pi_handle", lambda: "the_pi")
    assert client.get("/api/space/lab?user=student").status_code == 403
    ok = client.get("/api/space/lab?user=the_pi")
    assert ok.status_code == 200 and ok.json()["report"]["lab"] == "mh"
    assert client.get("/space").status_code == 200
