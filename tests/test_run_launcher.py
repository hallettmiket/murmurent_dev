"""``murmurent run`` and ``murmurent jobs`` (#151, step 1).

The machine, tmux and Slack are fakes (tests/run_fakes.py): no tmux session is
started, nvidia-smi is never called, and nothing reaches the network.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import run_cards as cards
from murmurent.core import run_launcher as rl
from murmurent.core.millwright_policy import ALL_IDLE_GPUS, Policy

from .run_fakes import FRIDAY_MORNING, FRIDAY_NIGHT, GB, FakePoster, FakeProbes, FakeTmux, gpu

POLICY = Policy()


def _request(tmp_path: Path, **kw) -> rl.ResourceRequest:
    base = {
        "cores": None,
        "gpus": 0,
        "memory_bytes": None,
        "expect_disk_bytes": None,
        "disk_path": tmp_path,
        "exception": None,
    }
    base.update(kw)
    return rl.ResourceRequest(**base)


def _options(tmp_path: Path, **kw) -> rl.LaunchOptions:
    base = {"command": ["Rscript", "fit.R"], "workdir": tmp_path}
    base.update(kw)
    return rl.LaunchOptions(**base)


# ---------------------------------------------------------------------------
# Reading what people type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2G", 2 * GB),
        ("1.5TB", int(1.5 * 1024**4)),
        ("64GiB", 64 * GB),
        ("500", 500),
        ("100MB", 100 * 1024**2),
        ("10 g", 10 * GB),
    ],
)
def test_parse_size(text, expected):
    assert rl.parse_size(text) == expected


def test_parse_size_refuses_words():
    with pytest.raises(rl.LaunchError, match="not a size"):
        rl.parse_size("lots")


def test_parse_time_clock_means_the_next_time_it_comes_round():
    assert rl.parse_time("22:00", FRIDAY_MORNING) == FRIDAY_MORNING.replace(hour=22)
    tomorrow = rl.parse_time("08:00", FRIDAY_MORNING.replace(hour=9))
    assert tomorrow.date() == dt.date(2026, 10, 17) and tomorrow.hour == 8


def test_parse_time_dates_and_mistakes():
    assert rl.parse_time("2026-10-17 06:30", FRIDAY_MORNING).day == 17
    with pytest.raises(rl.LaunchError, match="already passed"):
        rl.parse_time("2026-10-15 06:30", FRIDAY_MORNING)
    with pytest.raises(rl.LaunchError, match="not a time"):
        rl.parse_time("tonight", FRIDAY_MORNING)


@pytest.mark.parametrize("bad", ["/data/patient_7.csv", "a\\b", "x" * 61, "-dash-first", ""])
def test_job_names_that_look_like_paths_are_refused(bad):
    with pytest.raises(rl.LaunchError, match="no slashes"):
        rl.check_job_name(bad)


def test_ordinary_job_names_pass():
    assert rl.check_job_name(" gate d_2.v1 ") == "gate d_2.v1"


def test_parse_nvidia_smi_reads_numbers_and_unknowns():
    text = "0, 35, 1024, 81920\n1, [N/A], [N/A], 81920\nbad line\n"
    gpus = rl.parse_nvidia_smi(text)
    assert [g.index for g in gpus] == [0, 1]
    assert gpus[0].load_percent == 35
    assert gpus[1].load_percent == 100  # unknown counts as busy


# ---------------------------------------------------------------------------
# Deciding cores
# ---------------------------------------------------------------------------


def test_a_job_that_does_not_ask_gets_the_default_cores(tmp_path):
    plan = rl.plan_resources(_request(tmp_path), POLICY, FakeProbes())
    assert plan.ok and plan.cores == POLICY.default_cores


def test_cores_are_capped_by_the_per_person_allowance(tmp_path):
    plan = rl.plan_resources(_request(tmp_path, cores=40), POLICY, FakeProbes(), held=(10, 0, 0))
    assert plan.ok and plan.cores == POLICY.max_cores_per_person - 10
    assert any("your other jobs hold 10" in n for n in plan.notes)


def test_no_cores_left_in_the_allowance_means_wait(tmp_path):
    plan = rl.plan_resources(_request(tmp_path, cores=4), POLICY, FakeProbes(), held=(16, 0, 0))
    assert not plan.ok and plan.can_wait
    assert "already use 16 cores" in plan.refusals[0]


def test_an_exception_lifts_the_allowance_but_not_the_load_rule(tmp_path):
    exception = {
        "reason": "deadline",
        "until": cards.to_iso(FRIDAY_MORNING + dt.timedelta(hours=2)),
    }
    plan = rl.plan_resources(
        _request(tmp_path, cores=60, exception=exception), POLICY, FakeProbes(load=10.0)
    )
    assert plan.ok and plan.cores == 60
    capped = rl.plan_resources(
        _request(tmp_path, cores=90, exception=exception), POLICY, FakeProbes(load=10.0)
    )
    assert capped.cores == 70  # 100 cores x 0.8 - load 10


def test_an_expired_exception_does_not_count(tmp_path):
    exception = {"reason": "old", "until": cards.to_iso(FRIDAY_MORNING - dt.timedelta(hours=1))}
    plan = rl.plan_resources(
        _request(tmp_path, cores=60, exception=exception), POLICY, FakeProbes()
    )
    assert plan.cores == POLICY.max_cores_per_person


def test_cores_are_capped_by_how_busy_the_server_is(tmp_path):
    policy = dataclasses.replace(POLICY, max_cores_per_person=100)
    plan = rl.plan_resources(_request(tmp_path, cores=20), policy, FakeProbes(load=70.0))
    assert plan.ok and plan.cores == 10
    assert any("server is busy" in n for n in plan.notes)


def test_a_busy_server_holds_new_work(tmp_path):
    plan = rl.plan_resources(_request(tmp_path), POLICY, FakeProbes(load=85.0))
    assert not plan.ok and plan.can_wait
    assert "load is 85 on 100 cores" in plan.refusals[0]


def test_unknown_load_is_said_not_assumed(tmp_path):
    plan = rl.plan_resources(_request(tmp_path, cores=4), POLICY, FakeProbes(load=None))
    assert plan.ok and plan.cores == 4
    assert any("does not report its load" in n for n in plan.notes)


# ---------------------------------------------------------------------------
# Memory and disk
# ---------------------------------------------------------------------------


def test_low_memory_holds_new_work(tmp_path):
    plan = rl.plan_resources(_request(tmp_path), POLICY, FakeProbes(memory=(100 * GB, 15 * GB)))
    assert not plan.ok and plan.can_wait and "Memory is low" in plan.refusals[0]


def test_a_job_that_would_leave_too_little_memory_waits(tmp_path):
    plan = rl.plan_resources(
        _request(tmp_path, memory_bytes=100 * GB), POLICY, FakeProbes(memory=(400 * GB, 150 * GB))
    )
    assert not plan.ok and plan.can_wait and "would leave less than 20%" in plan.refusals[0]


def test_memory_above_the_personal_allowance_needs_an_exception(tmp_path):
    probes = FakeProbes(memory=(100 * GB, 90 * GB))
    plan = rl.plan_resources(_request(tmp_path, memory_bytes=30 * GB), POLICY, probes)
    assert not plan.ok and not plan.can_wait and "--exception" in plan.refusals[0]
    exception = {
        "reason": "big join",
        "until": cards.to_iso(FRIDAY_MORNING + dt.timedelta(hours=1)),
    }
    allowed = rl.plan_resources(
        _request(tmp_path, memory_bytes=30 * GB, exception=exception), POLICY, probes
    )
    assert allowed.ok


def test_expected_output_that_does_not_fit_is_refused(tmp_path):
    probes = FakeProbes(disk=(1000 * GB, 900 * GB, 100 * GB))
    plan = rl.plan_resources(_request(tmp_path, expect_disk_bytes=200 * GB), POLICY, probes)
    assert not plan.ok and not plan.can_wait and "100.0 GB free" in plan.refusals[0]
    fills = rl.plan_resources(_request(tmp_path, expect_disk_bytes=80 * GB), POLICY, probes)
    assert not fills.ok and "past 95%" in fills.refusals[0]


def test_a_nearly_full_disk_is_a_warning_without_an_estimate(tmp_path):
    probes = FakeProbes(disk=(1000 * GB, 980 * GB, 20 * GB))
    plan = rl.plan_resources(_request(tmp_path / "out"), POLICY, probes)
    assert plan.ok and any("98% full" in n for n in plan.notes)
    assert probes.disk_paths == [tmp_path / "out"]


# ---------------------------------------------------------------------------
# GPUs
# ---------------------------------------------------------------------------

EIGHT_GPUS = [
    gpu(0, 90),
    gpu(1, 0),
    gpu(2, 50),
    gpu(3, 0, used=40_000),
    gpu(4, 2),
    gpu(5, 0),
    gpu(6, 100),
    gpu(7, 1),
]


def test_the_least_busy_gpus_are_chosen(tmp_path):
    policy = dataclasses.replace(POLICY, gpus_per_person_working_hours=4)
    plan = rl.plan_resources(_request(tmp_path, gpus=3), policy, FakeProbes(gpus=EIGHT_GPUS))
    assert plan.ok and plan.gpus == [1, 5, 7]


def test_working_hours_limit_needs_an_exception(tmp_path):
    plan = rl.plan_resources(_request(tmp_path, gpus=2), POLICY, FakeProbes(gpus=EIGHT_GPUS))
    assert not plan.ok and not plan.can_wait
    assert "in working hours one person may hold 1" in plan.refusals[0]
    exception = {
        "reason": "nobody else on",
        "until": cards.to_iso(FRIDAY_MORNING + dt.timedelta(hours=3)),
    }
    allowed = rl.plan_resources(
        _request(tmp_path, gpus=2, exception=exception), POLICY, FakeProbes(gpus=EIGHT_GPUS)
    )
    assert allowed.ok and allowed.gpus == [1, 5]


def test_outside_working_hours_every_idle_gpu_may_be_used(tmp_path):
    policy = dataclasses.replace(
        POLICY, gpus_per_person_working_hours=4, gpus_per_person_outside_hours=ALL_IDLE_GPUS
    )
    idle_eight = [gpu(i, 0) for i in range(8)]
    plan = rl.plan_resources(
        _request(tmp_path, gpus=8), policy, FakeProbes(now=FRIDAY_NIGHT, gpus=idle_eight)
    )
    assert plan.ok and plan.gpus == list(range(8))
    # With only four idle, eight is worth waiting for, not a rule broken.
    busy = rl.plan_resources(
        _request(tmp_path, gpus=8), policy, FakeProbes(now=FRIDAY_NIGHT, gpus=EIGHT_GPUS)
    )
    assert not busy.ok and busy.can_wait and "are idle now" in busy.refusals[0]


def test_gpus_held_by_other_jobs_count(tmp_path):
    policy = dataclasses.replace(POLICY, gpus_per_person_working_hours=4)
    plan = rl.plan_resources(
        _request(tmp_path, gpus=2), policy, FakeProbes(gpus=EIGHT_GPUS), held=(0, 3, 0)
    )
    assert not plan.ok and "your other jobs hold 3" in plan.refusals[0]


def test_no_gpus_on_the_machine(tmp_path):
    plan = rl.plan_resources(_request(tmp_path, gpus=1), POLICY, FakeProbes(gpus=None))
    assert not plan.ok and not plan.can_wait and "reports none" in plan.refusals[0]


def test_sharing_a_busy_gpu_is_said(tmp_path):
    policy = dataclasses.replace(POLICY, gpus_per_person_working_hours=4)
    plan = rl.plan_resources(
        _request(tmp_path, gpus=1), policy, FakeProbes(gpus=[gpu(0, 80), gpu(1, 95)])
    )
    assert plan.ok and plan.gpus == [0]
    assert any("GPU 0 (80% in use)" in n for n in plan.notes)


def test_thread_environment():
    env = rl.thread_environment(8, [2, 5], wants_gpus=True)
    for name in rl.THREAD_VARIABLES:
        assert env[name] == "8"
    assert env["CUDA_VISIBLE_DEVICES"] == "2,5"
    assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert rl.thread_environment(1, [], wants_gpus=False)["CUDA_VISIBLE_DEVICES"] == ""


# ---------------------------------------------------------------------------
# Launching
# ---------------------------------------------------------------------------


def test_launch_writes_a_card_and_starts_the_supervisor_in_tmux(tmp_path):
    tmux = FakeTmux()
    result = rl.launch(
        _options(tmp_path, cores=4, name="gate d"),
        probes=FakeProbes(),
        policy=POLICY,
        tmux=tmux,
        environ={"PATH": "/x", "SECRET": "s"},
    )
    card = result.card
    assert result.started_now and card.cores == 4 and card.state == cards.STATE_WAITING
    assert card.env_set["OMP_NUM_THREADS"] == "4"
    saved = cards.read_card(cards.card_path(card.id))
    assert saved is not None and saved.command == ["Rscript", "fit.R"]
    assert "SECRET" not in cards.card_path(card.id).read_text()
    [started] = tmux.started
    assert started["session"] == f"run-{card.id}" and started["window"] == "gate_d"
    assert started["command"].startswith("nice -n 19 ")
    assert " -P -m murmurent.core.run_supervisor " in started["command"]
    assert str(cards.card_path(card.id)) in started["command"]
    snapshot = rl.environment_snapshot_path(card.id)
    assert json.loads(snapshot.read_text())["SECRET"] == "s"
    assert stat.S_IMODE(snapshot.stat().st_mode) == 0o600
    assert stat.S_IMODE(cards.card_path(card.id).stat().st_mode) == 0o600
    assert stat.S_IMODE(cards.runs_dir().stat().st_mode) == 0o700


def test_launch_says_plainly_when_tmux_is_missing(tmp_path):
    with pytest.raises(rl.LaunchError, match="tmux is not installed"):
        rl.launch(
            _options(tmp_path),
            probes=FakeProbes(tmux=False),
            policy=POLICY,
            tmux=FakeTmux(),
            environ={},
        )


def test_launch_needs_a_command(tmp_path):
    with pytest.raises(rl.LaunchError, match="after --"):
        rl.launch(
            _options(tmp_path, command=[]),
            probes=FakeProbes(),
            policy=POLICY,
            tmux=FakeTmux(),
            environ={},
        )


def test_a_busy_server_refuses_and_says_how_to_wait(tmp_path):
    tmux = FakeTmux()
    with pytest.raises(rl.LaunchError, match="Add --wait"):
        rl.launch(
            _options(tmp_path), probes=FakeProbes(load=95.0), policy=POLICY, tmux=tmux, environ={}
        )
    assert tmux.started == [] and cards.list_cards() == []


def test_wait_creates_a_waiting_job(tmp_path):
    tmux = FakeTmux()
    result = rl.launch(
        _options(tmp_path, wait=True),
        probes=FakeProbes(load=95.0),
        policy=POLICY,
        tmux=tmux,
        environ={},
    )
    assert not result.started_now and result.card.cores == 0
    assert result.card.waiting_for == "room on the server"
    assert len(tmux.started) == 1


def test_a_rule_breach_is_refused_even_with_wait(tmp_path):
    with pytest.raises(rl.LaunchError, match="--exception"):
        rl.launch(
            _options(tmp_path, gpus=3, wait=True),
            probes=FakeProbes(gpus=EIGHT_GPUS),
            policy=POLICY,
            tmux=FakeTmux(),
            environ={},
        )


def test_a_later_start_is_checked_against_the_rules_at_that_time(tmp_path):
    policy = dataclasses.replace(
        POLICY, gpus_per_person_working_hours=1, gpus_per_person_outside_hours=ALL_IDLE_GPUS
    )
    result = rl.launch(
        _options(tmp_path, gpus=6, at="22:00"),
        probes=FakeProbes(gpus=[gpu(i, 0) for i in range(8)]),
        policy=policy,
        tmux=FakeTmux(),
        environ={},
    )
    assert not result.started_now
    assert result.card.requested["at"].startswith("2026-10-16T22:00")
    assert "the start time 2026-10-16 22:00" in result.card.waiting_for


def test_a_later_start_ignores_how_busy_the_server_is_now(tmp_path):
    result = rl.launch(
        _options(tmp_path, when_load_below=50.0),
        probes=FakeProbes(load=95.0),
        policy=POLICY,
        tmux=FakeTmux(),
        environ={},
    )
    assert "load to fall below 50" in result.card.waiting_for


def test_dry_run_starts_nothing_and_writes_nothing(tmp_path):
    tmux = FakeTmux()
    result = rl.launch(
        _options(tmp_path, dry_run=True), probes=FakeProbes(), policy=POLICY, tmux=tmux, environ={}
    )
    assert result.lines[0].startswith("Dry run")
    assert tmux.started == [] and cards.list_cards() == []


def test_a_named_session_gets_a_new_window(tmp_path):
    tmux = FakeTmux(existing={"survival_runs"})
    rl.launch(
        _options(tmp_path, session="survival_runs"),
        probes=FakeProbes(),
        policy=POLICY,
        tmux=tmux,
        environ={},
    )
    assert tmux.started[0]["session"] == "survival_runs" and tmux.started[0]["new_window"]


def test_an_exception_needs_a_reason_and_an_end(tmp_path):
    with pytest.raises(rl.LaunchError, match="both a reason and an end time"):
        rl.launch(
            _options(tmp_path, exception="deadline"),
            probes=FakeProbes(),
            policy=POLICY,
            tmux=FakeTmux(),
            environ={},
        )
    result = rl.launch(
        _options(tmp_path, gpus=2, exception="nobody else on", until="12:00"),
        probes=FakeProbes(gpus=EIGHT_GPUS),
        policy=POLICY,
        tmux=FakeTmux(),
        environ={},
    )
    assert result.card.exception["reason"] == "nobody else on"
    assert result.card.exception["until"].startswith("2026-10-16T12:00")
    assert result.card.gpus == [1, 5]


def test_a_tmux_failure_is_recorded_and_reported(tmp_path):
    with pytest.raises(rl.LaunchError, match="no server"):
        rl.launch(
            _options(tmp_path),
            probes=FakeProbes(),
            policy=POLICY,
            tmux=FakeTmux(fail="no server"),
            environ={},
        )
    [card] = cards.list_cards()
    assert card.state == cards.STATE_FAILED
    assert not rl.environment_snapshot_path(card.id).exists()


def test_relative_out_and_log_are_read_from_the_working_folder(tmp_path):
    result = rl.launch(
        _options(tmp_path, out="results", log="logs/run.txt"),
        probes=FakeProbes(),
        policy=POLICY,
        tmux=FakeTmux(),
        environ={},
    )
    assert result.card.out == str(tmp_path.resolve() / "results")
    assert result.card.log == str(tmp_path.resolve() / "logs" / "run.txt")
    assert result.card.watch == result.card.log


def test_running_jobs_count_against_the_allowance(tmp_path, monkeypatch):
    other = _card("20261016-080000-aaaa", state=cards.STATE_RUNNING, cores=14)
    cards.write_card(other)
    monkeypatch.setattr(cards, "supervisor_alive", lambda c: True)
    result = rl.launch(
        _options(tmp_path, cores=8), probes=FakeProbes(), policy=POLICY, tmux=FakeTmux(), environ={}
    )
    assert result.card.cores == 2


def test_an_earlier_run_gives_a_time_estimate(tmp_path):
    workdir = str(tmp_path.resolve())
    done = _card(
        "20261015-080000-aaaa",
        state=cards.STATE_FINISHED,
        workdir=workdir,
        command=["Rscript", "fit.R"],
        started_at="2026-10-15T08:00:00-04:00",
        ended_at="2026-10-15T09:30:00-04:00",
    )
    cards.write_card(done)
    result = rl.launch(
        _options(tmp_path), probes=FakeProbes(), policy=POLICY, tmux=FakeTmux(), environ={}
    )
    assert result.card.estimates == {"duration_seconds": 5400.0, "duration_runs": 1}
    assert any("about 1 h 30 min" in line for line in result.lines)


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


def _repo(tmp_path: Path, marker: dict) -> Path:
    import yaml

    repo = tmp_path / "proj_x"
    repo.mkdir()
    (repo / ".murmurent.yaml").write_text(yaml.safe_dump(marker), encoding="utf-8")
    return repo


def test_no_project_means_no_notice(tmp_path):
    target = rl.resolve_notify_target(tmp_path)
    assert target.project == "" and target.channel == ""
    assert "not part of a murmurent project" in target.reason


def test_the_channel_comes_from_the_update_me_setting(tmp_path):
    repo = _repo(
        tmp_path,
        {"murmurent": 1, "lab": "lab_zz", "name": "proj_x", "update_me": {"channel": "CTEST0001"}},
    )
    (repo / "exp").mkdir()
    target = rl.resolve_notify_target(repo / "exp")
    assert (target.project, target.channel, target.slack_group) == ("proj_x", "CTEST0001", "zz")


def test_the_channel_comes_from_the_project_record(tmp_path, monkeypatch):
    repo = _repo(tmp_path, {"murmurent": 1, "lab": "zz"})
    record = cp.CertProject(name="proj_x", lab="zz", slack_channel_id="CTEST0002")
    monkeypatch.setattr(cp, "get", lambda name, env=None: record if name == "proj_x" else None)
    target = rl.resolve_notify_target(repo)
    assert (target.project, target.channel) == ("proj_x", "CTEST0002")


def test_a_project_without_a_channel_says_so(tmp_path):
    repo = _repo(tmp_path, {"murmurent": 1, "lab": "zz", "name": "proj_x"})
    target = rl.resolve_notify_target(repo)
    assert target.channel == "" and "no Slack channel is recorded" in target.reason


def _card(job_id: str, **kw) -> cards.JobCard:
    base = {
        "id": job_id,
        "name": kw.pop("name", job_id),
        "user": "tester",
        "host": cards.this_host(),
        "command": ["Rscript", "/data/governed/patient_123_fit.R"],
        "workdir": "/tmp/w",
        "log": "/tmp/w/log",
        "watch": "/tmp/w/log",
        "created_at": "2026-10-16T08:00:00-04:00",
    }
    base.update(kw)
    return cards.JobCard(**base)


@pytest.mark.parametrize(
    "state,code,expect",
    [
        (cards.STATE_FINISHED, 0, "finished after 2 h 5 min. Exit code 0."),
        (cards.STATE_FAILED, 1, "failed after 2 h 5 min. Exit code 1."),
        (cards.STATE_STALLED, None, "has written no new output for 60 min"),
    ],
)
def test_the_notice_carries_no_command_or_path(state, code, expect):
    card = _card(
        "20261016-080000-aaaa",
        name="fit",
        state=state,
        exit_code=code,
        started_at="2026-10-16T08:00:00-04:00",
        ended_at="2026-10-16T10:05:00-04:00",
        out="/data/governed/out",
        project="proj_x",
    )
    if state == cards.STATE_STALLED:
        card.ended_at = None
    text = rl.notice_text(card)
    assert expect in text and text.startswith("Job fit (tester)")
    for leak in ("/data", "patient", "Rscript", ".R", "/tmp"):
        assert leak not in text
    assert "\u2014" not in text


def test_post_notice_records_every_outcome():
    poster = FakePoster()
    card = _card(
        "j1",
        state=cards.STATE_FINISHED,
        exit_code=0,
        started_at="2026-10-16T08:00:00-04:00",
        ended_at="2026-10-16T08:10:00-04:00",
        notify={"enabled": True, "channel": "CTEST0001", "slack_group": "zz"},
    )
    assert rl.post_notice(card, poster=poster, token_resolver=lambda p, g: "xoxb-test")
    assert poster.calls[0]["channel"] == "CTEST0001" and poster.calls[0]["token"] == "xoxb-test"
    assert card.notify["posted"][0]["ok"] is True

    off = _card("j2", notify={"enabled": False, "channel": "CTEST0001"})
    assert not rl.post_notice(off, poster=poster) and len(poster.calls) == 1

    no_channel = _card("j3", notify={"enabled": True, "channel": "", "reason": "no project"})
    assert not rl.post_notice(no_channel, poster=poster)
    assert no_channel.notify["skipped"] == "no project"

    no_token = _card("j4", notify={"enabled": True, "channel": "CTEST0001"})
    assert not rl.post_notice(no_token, poster=poster, token_resolver=lambda p, g: "")
    assert "no Slack token" in no_token.notify["skipped"]

    def broken(*_a, **_k):
        raise RuntimeError("network down")

    failing = _card("j5", notify={"enabled": True, "channel": "CTEST0001"})
    assert not rl.post_notice(failing, poster=broken, token_resolver=lambda p, g: "t")
    assert failing.notify["skipped"] == "Slack did not accept the message"


def test_restart_keeps_the_request_and_drops_an_expired_exception():
    card = _card(
        "20261016-080000-aaaa",
        name="fit",
        state=cards.STATE_FAILED,
        requested={
            "cores": 8,
            "gpus": 2,
            "memory_bytes": 4 * GB,
            "session": "s1",
            "log_given": False,
        },
        exception={"reason": "old", "until": "2026-01-01T00:00:00-05:00"},
        notify={"enabled": True},
    )
    options = rl.restart_options(card, wait=True)
    assert options.command == card.command and options.cores == 8 and options.gpus == 2
    assert rl.parse_size(options.memory) == 4 * GB
    assert options.exception == "" and options.until == ""
    assert options.session == "s1" and options.wait and options.restarted_from == card.id
    assert options.log == ""  # a new log for the new run


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


def test_cards_round_trip_and_are_found_by_id_prefix_or_name():
    first = _card("20261016-080000-aaaa", name="fit")
    second = _card("20261016-090000-bbbb", name="fit", created_at="2026-10-16T09:00:00-04:00")
    third = _card("20261016-090000-cccc", name="other", created_at="2026-10-16T09:00:01-04:00")
    for card in (first, second, third):
        cards.write_card(card)
    assert cards.find_card("20261016-080000-aaaa").id == first.id
    assert cards.find_card("20261016-0800").id == first.id
    assert cards.find_card("fit").id == second.id  # the newest with that name
    assert cards.find_card("20261016-0900") is None  # two match: ambiguous
    assert cards.find_card("nothing") is None


def test_environment_copies_are_not_read_as_cards(tmp_path):
    cards.write_card(_card("20261016-080000-aaaa"))
    (cards.runs_dir() / "20261016-080000-aaaa.env.json").write_text(json.dumps({"id": "x"}))
    assert [c.id for c in cards.list_cards()] == ["20261016-080000-aaaa"]


def test_a_card_whose_supervisor_died_is_marked_failed():
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    card = _card("20261016-080000-aaaa", state=cards.STATE_RUNNING, supervisor_pid=dead.pid)
    cards.write_card(card)
    [after] = cards.mark_lost_cards(cards.list_cards())
    assert (
        after.state == cards.STATE_FAILED and "without recording an end" in after.notes[-1]["text"]
    )


def test_a_card_just_launched_is_not_marked_lost():
    card = _card(
        "20261016-080000-aaaa",
        state=cards.STATE_WAITING,
        created_at=cards.to_iso(cards.now_local()),
    )
    cards.write_card(card)
    [after] = cards.mark_lost_cards(cards.list_cards())
    assert after.state == cards.STATE_WAITING


def test_a_card_from_another_machine_is_left_alone():
    card = _card(
        "20261016-080000-aaaa", state=cards.STATE_RUNNING, host="elsewhere", supervisor_pid=1
    )
    assert cards.supervisor_alive(card) is None
    assert cards.mark_lost_cards([card])[0].state == cards.STATE_RUNNING


def test_the_time_estimate_is_the_median_of_matching_runs():
    def done(job_id: str, minutes: int, **kw) -> cards.JobCard:
        start = dt.datetime(2026, 10, 1, 8, 0).astimezone()
        return _card(
            job_id,
            state=kw.pop("state", cards.STATE_FINISHED),
            started_at=cards.to_iso(start),
            ended_at=cards.to_iso(start + dt.timedelta(minutes=minutes)),
            **kw,
        )

    history = [
        done("a", 10),
        done("b", 30),
        done("c", 20),
        done("d", 999, workdir="/elsewhere"),
        done("e", 999, state=cards.STATE_FAILED),
        done("f", 999, command=["python", "other.py"]),
    ]
    seconds, runs = cards.estimate_duration(
        history, ["Rscript", "/data/governed/patient_123_fit.R"], "/tmp/w"
    )
    assert (seconds, runs) == (20 * 60, 3)
    assert cards.estimate_duration([], ["x"], "/tmp") == (None, 0)


def test_formatting():
    assert cards.format_duration(None) == "unknown"
    assert cards.format_duration(30) == "less than a minute"
    assert cards.format_duration(3 * 3600 + 12 * 60) == "3 h 12 min"
    assert cards.format_duration(2 * 86400 + 5 * 3600) == "2 d 5 h"
    assert cards.format_size(512) == "512 bytes"
    assert cards.format_size(1.5 * GB) == "1.5 GB"


# ---------------------------------------------------------------------------
# The commands
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_machine(monkeypatch):
    tmux = FakeTmux()
    monkeypatch.setattr(rl, "SystemProbes", lambda: FakeProbes(now=cards.now_local()))
    monkeypatch.setattr(rl, "TmuxRunner", lambda: tmux)
    monkeypatch.setattr(rl, "load_policy", lambda: POLICY)
    return tmux


def test_run_command_starts_a_job(tmp_path, monkeypatch, fake_machine):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "run",
            "--cores",
            "2",
            "--name",
            "fit",
            "--no-notify",
            "--",
            "Rscript",
            "fit.R",
            "--vanilla",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Started job fit on 2 cores, at priority nice 19." in result.output
    [card] = cards.list_cards()
    assert card.command == ["Rscript", "fit.R", "--vanilla"] and not card.notify["enabled"]
    assert len(fake_machine.started) == 1


def test_run_command_reports_a_refusal_plainly(tmp_path, monkeypatch, fake_machine):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["run", "--name", "/data/x", "--", "echo"])
    assert result.exit_code != 0 and "no slashes" in result.output


def test_jobs_lists_nothing_politely():
    result = CliRunner().invoke(cli, ["jobs"])
    assert result.exit_code == 0 and "no jobs" in result.output


def test_jobs_lists_running_and_ended_jobs_in_plain_english(monkeypatch):
    now = cards.now_local()
    running = _card(
        "20261016-080000-aaaa",
        name="fit",
        state=cards.STATE_RUNNING,
        cores=8,
        gpus=[2, 3],
        started_at=cards.to_iso(now - dt.timedelta(hours=1)),
        created_at=cards.to_iso(now - dt.timedelta(hours=1)),
        estimates={
            "duration_seconds": 3 * 3600,
            "duration_runs": 2,
            "disk_growth_bytes_per_hour": 10 * GB,
            "hours_until_disk_full": 1.0,
            "disk_measured_minutes": 10,
        },
    )
    failed = _card(
        "20261016-070000-bbbb",
        name="prep",
        state=cards.STATE_FAILED,
        exit_code=2,
        started_at=cards.to_iso(now - dt.timedelta(hours=3)),
        ended_at=cards.to_iso(now - dt.timedelta(hours=2)),
        created_at=cards.to_iso(now - dt.timedelta(hours=3)),
    )
    cards.write_card(running)
    cards.write_card(failed)
    monkeypatch.setattr(cards, "supervisor_alive", lambda c: True)
    out = CliRunner().invoke(cli, ["jobs"]).output
    assert "fit [20261016-080000-aaaa]: running for 1 h on 8 cores and GPUs 2, 3." in out
    assert "left, finishing around" in out and "(an estimate from 2 earlier run(s))" in out
    assert "The disk may fill before the job finishes." in out
    assert "prep [20261016-070000-bbbb]: failed" in out and "(exit code 2)" in out
    assert "\u2014" not in out


def test_jobs_show_gives_the_detail(monkeypatch):
    card = _card(
        "20261016-080000-aaaa",
        name="fit",
        state=cards.STATE_FINISHED,
        exit_code=0,
        cores=4,
        started_at="2026-10-16T08:00:00-04:00",
        ended_at="2026-10-16T08:30:00-04:00",
        requested={"cores": 8},
        env_set={"OMP_NUM_THREADS": "4", "CUDA_VISIBLE_DEVICES": ""},
        notify={"enabled": True, "channel": "C1", "posted": [{"state": "finished", "ok": True}]},
    )
    card.add_note("You asked for 8 cores; the server is busy.")
    cards.write_card(card)
    out = CliRunner().invoke(cli, ["jobs", "show", "fit"]).output
    assert "Job fit [20261016-080000-aaaa]" in out
    assert "Command: Rscript /data/governed/patient_123_fit.R" in out
    assert "Cores: 4 (asked for 8)" in out
    assert "CUDA_VISIBLE_DEVICES=(none)" in out
    assert "Slack: posted when it finished." in out
    assert "the server is busy" in out


def test_jobs_show_unknown_job():
    result = CliRunner().invoke(cli, ["jobs", "show", "nope"])
    assert result.exit_code != 0 and "No job matches 'nope'" in result.output


def test_jobs_restart_refuses_a_running_job_and_relaunches_an_ended_one(
    tmp_path, monkeypatch, fake_machine
):
    monkeypatch.setattr(cards, "supervisor_alive", lambda c: True)
    running = _card(
        "20261016-080000-aaaa", name="fit", state=cards.STATE_RUNNING, workdir=str(tmp_path)
    )
    cards.write_card(running)
    refused = CliRunner().invoke(cli, ["jobs", "restart", "fit"])
    assert refused.exit_code != 0 and "still running" in refused.output

    running.state = cards.STATE_FAILED
    running.requested = {"cores": 3}
    running.notify = {"enabled": False}
    cards.write_card(running)
    again = CliRunner().invoke(cli, ["jobs", "restart", "20261016-080000-aaaa"])
    assert again.exit_code == 0, again.output
    newest = cards.list_cards()[0]
    assert newest.restarted_from == running.id and newest.cores == 3
    assert newest.command == running.command and newest.workdir == str(tmp_path.resolve())


def test_jobs_stop_on_an_ended_job_says_so():
    cards.write_card(_card("20261016-080000-aaaa", name="fit", state=cards.STATE_FINISHED))
    out = CliRunner().invoke(cli, ["jobs", "stop", "fit"]).output
    assert "is not running; it finished" in out


def test_jobs_stop_signals_the_supervisor(monkeypatch):
    sent = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr(cards, "supervisor_alive", lambda c: True)
    cards.write_card(
        _card("20261016-080000-aaaa", name="fit", state=cards.STATE_RUNNING, supervisor_pid=4242)
    )
    out = CliRunner().invoke(cli, ["jobs", "stop", "fit"]).output
    assert "Asked job fit" in out and sent and sent[0][0] == 4242


def test_jobs_policy_prints_the_rules():
    out = CliRunner().invoke(cli, ["jobs", "policy"]).output
    assert out.startswith("Rules from: built-in defaults")
    assert "nice 19" in out


@pytest.mark.parametrize(
    "kw,message",
    [
        ({"stall_after": 0}, "at least 1 minute"),
        ({"when_load_below": 0.0}, "more than 0"),
        ({"cores": 0}, "at least 1"),
        ({"at": "22:00", "exception": "x", "until": "21:00"}, "before the job starts"),
    ],
)
def test_nonsense_values_are_refused(tmp_path, kw, message):
    with pytest.raises(rl.LaunchError, match=message):
        rl.launch(
            _options(tmp_path, **kw),
            probes=FakeProbes(),
            policy=POLICY,
            tmux=FakeTmux(),
            environ={},
        )


def test_a_dry_run_says_would_start(tmp_path):
    result = rl.launch(
        _options(tmp_path, dry_run=True, cores=2),
        probes=FakeProbes(),
        policy=POLICY,
        tmux=FakeTmux(),
        environ={},
    )
    assert result.lines[1].startswith("Would start job")


def test_estimates_read_naturally():
    assert cards.about(30) == "less than a minute"
    assert cards.about(7200) == "about 2 h"
    assert cards.about(None) == "unknown"
