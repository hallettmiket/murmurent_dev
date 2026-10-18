"""The server etiquette check (#151, step 4).

`ps` and `nvidia-smi` are faked; nobody is messaged; no systemd.
"""

from __future__ import annotations

import datetime as _dt
from types import SimpleNamespace

import pytest

from murmurent.core import etiquette as et
from murmurent.core.millwright_policy import Policy

MONDAY_NOON = _dt.datetime(2026, 10, 19, 12, 0).astimezone()
SUNDAY_NOON = _dt.datetime(2026, 10, 18, 12, 0).astimezone()


def _cp(out=""):
    return SimpleNamespace(returncode=0, stdout=out, stderr="")


def fake_server(ps_lines, gpus="", apps=""):
    seen = []

    def run(argv):
        seen.append(argv)
        if argv[0] == "ps":
            return _cp("\n".join(ps_lines))
        if "--query-gpu=index,uuid,utilization.gpu" in argv:
            return _cp(gpus)
        if "--query-compute-apps=gpu_uuid,pid" in argv:
            return _cp(apps)
        return _cp("")
    return run, seen


@pytest.fixture(autouse=True)
def people(monkeypatch, tmp_path):
    monkeypatch.setattr(et, "_is_person", lambda user: user != "root")
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))


POLICY = Policy(max_cores_per_person=100, gpus_per_person_working_hours=4,
                gpus_per_person_outside_hours="all")
GPUS = "\n".join(f"{i}, GPU-{i}, {80 if i < 6 else 0}" for i in range(8))


def test_reads_no_command_lines():
    run, seen = fake_server([])
    et.check(policy=POLICY, run=run, now=MONDAY_NOON, logins={})
    ps = next(a for a in seen if a[0] == "ps")
    assert not any(w in " ".join(ps) for w in ("args", "cmd", "comm", "command"))


def test_findings_and_privacy_for_people_outside_the_lab():
    ps = [
        "bob 101 0 3000.0 7200",      # 30 cores at nice 0, two hours: priority
        "bob 102 19 9000.0 7200",     # 90 more cores at nice 19: total 120 > 100
        "bob 103 0 400.0 30",         # too young to count
        "carol 201 0 900.0 7200",     # not in the lab: counted, not named
        "dave 301 0 3.0 7200",        # an idle shell: ignored
        "root 1 0 50.0 9999",
    ]
    apps = "\n".join(f"GPU-{i}, 102" for i in range(6))   # bob holds GPUs 0-5
    run, _ = fake_server(ps, GPUS, apps)
    bob = SimpleNamespace(handle="@bob")
    rep = et.check(policy=POLICY, run=run, now=MONDAY_NOON, logins={"bob": bob})
    kinds = {f["kind"] for f in rep["members"][0]["findings"]}
    assert rep["members"][0]["handle"] == "bob"
    assert kinds == {et.PRIORITY, et.CORES, et.GPUS}
    assert rep["others"] == {et.PRIORITY: 1, et.CORES: 0, et.GPUS: 0}
    text = et.summary_text(rep)
    assert "@bob" in text and "carol" not in text and "1 over the priority rule" in text
    fix = rep["members"][0]["findings"][0]["fix"]
    assert "renice -n 19 -u bob" in fix


def test_gpu_allowance_is_wider_outside_working_hours():
    apps = "\n".join(f"GPU-{i}, 102" for i in range(6, 8))   # two idle GPUs held
    run, _ = fake_server(["bob 102 19 100.0 7200"], GPUS, apps)
    rep = et.check(policy=POLICY, run=run, now=SUNDAY_NOON,
                   logins={"bob": SimpleNamespace(handle="@bob")})
    assert rep["members"] == []


def _report(*kinds):
    return {"members": [{"handle": "bob", "login": "bob", "findings": [
        {"kind": k, "seen": f"{k} seen.", "why": "Why.", "fix": "do this"} for k in kinds]}]}


def test_escalation_ladder():
    state = {}
    m1, state = et.plan_messages(_report(et.PRIORITY), state, "2026-10-19")
    assert [m["to"] for m in m1] == ["person"] and et.HOW_TO in m1[0]["text"]
    again, state = et.plan_messages(_report(et.PRIORITY), state, "2026-10-19")
    assert again == []                                    # same day: no escalation
    m2, state = et.plan_messages(_report(et.PRIORITY), state, "2026-10-20")
    assert [m["to"] for m in m2] == ["channel"] and "@bob" in m2[0]["text"]
    m3, state = et.plan_messages(_report(et.PRIORITY), state, "2026-10-21")
    assert [m["to"] for m in m3] == ["pi"]
    clean, state = et.plan_messages({"members": []}, state, "2026-10-22")
    assert clean == [] and state == {}                    # a clean day starts over
    m5, _ = et.plan_messages(_report(et.CORES), state, "2026-10-23")
    assert m5[0]["to"] == "person"


def test_how_to_link_sent_once():
    _, state = et.plan_messages(_report(et.PRIORITY), {}, "2026-10-19")
    m, _ = et.plan_messages(_report(et.PRIORITY, et.CORES), {"bob": {
        **state["bob"], "priority": {"days": 0}}}, "2026-10-20")
    assert all(et.HOW_TO not in x["text"] for x in m)


def test_notify_sends_through_the_lab_bot(monkeypatch):
    from murmurent.core import membership, project_unit
    monkeypatch.setattr(project_unit, "this_machine_lab", lambda: "mh")
    monkeypatch.setattr(membership, "get", lambda h: SimpleNamespace(slack="", email=f"{h}@x"))
    monkeypatch.setattr("murmurent.core.lab.pi_handle", lambda: "@the_pi")
    monkeypatch.setattr(et, "_lab_channel", lambda lab: "")
    sent = []
    done = et.notify(_report(et.PRIORITY), today="2026-10-19",
                     send_dm=lambda lab, text, slack, email: sent.append((email, text)) or (True, "ok"))
    assert [e for e, _ in sent] == ["bob@x", "the_pi@x"]   # the person, then the PI's summary
    assert any("message to @bob: sent" in d for d in done)


def test_schedule_units_and_record(monkeypatch, tmp_path):
    monkeypatch.setattr(et, "_program", lambda: "/usr/bin/murmurent")
    svc, timer = et.unit_texts(et.calendar("11:00"), notify_people=False, env={})
    assert "etiquette check'" in svc and "--notify" not in svc and "Nice=19" in svc
    assert "OnCalendar=Mon..Fri *-*-* 11:00:00" in timer
    with pytest.raises(ValueError):
        et.calendar("25:00")
    lab = tmp_path / "lab"
    from murmurent.core import millwright_policy
    monkeypatch.setattr(millwright_policy, "lab_policy_path", lambda env=None: lab / "policy" / "millwright.yaml")
    path = et.record(et.calendar("11:00"), True)
    text = path.read_text()
    assert "Server etiquette check" in text and "never command lines" in text
    et.record("", False)
    assert "Server etiquette check" not in path.read_text()


def test_policy_init_copies_the_template_once(tmp_path):
    from murmurent.core import millwright_policy as mp
    path, created = mp.write_default_policy(tmp_path / "lab-mgmt")
    assert created and "max_cores_per_person" in path.read_text()
    path.write_text("priority: 19\n")
    assert mp.write_default_policy(tmp_path / "lab-mgmt") == (path, False)
    assert path.read_text() == "priority: 19\n"
