"""The supervisor that runs a job inside tmux (#151, step 1).

The supervisor is driven directly, never through tmux. Jobs are tiny Python
one-liners; the clock is a fake wherever waiting is involved, so these tests
take moments.
"""

from __future__ import annotations

import datetime as dt
import json
import signal
import sys
import time
from pathlib import Path

import pytest

from murmurent.core import run_cards as cards
from murmurent.core import run_launcher as rl
from murmurent.core import run_supervisor as rs
from murmurent.core.millwright_policy import Policy

from .run_fakes import FRIDAY_MORNING, GB, FakeClock, FakePoster, FakeProbes, gpu

POLICY = Policy()


def _card(tmp_path: Path, command: list[str], **kw) -> Path:
    log = tmp_path / "job.log"
    base = {
        "id": "20261016-090000-abcd",
        "name": "fit",
        "user": "tester",
        "host": cards.this_host(),
        "command": command,
        "workdir": str(tmp_path),
        "log": str(log),
        "watch": str(log),
        "cores": 2,
        "env_set": rl.thread_environment(2, [], wants_gpus=False),
        "created_at": cards.to_iso(FRIDAY_MORNING),
        "notify": {"enabled": True, "channel": "CTEST0001", "slack_group": "zz"},
    }
    base.update(kw)
    card = cards.JobCard(**base)
    return cards.write_card(card)


def _supervisor(
    card_file: Path,
    *,
    probes=None,
    clock: FakeClock | None = None,
    poster: FakePoster | None = None,
    **kw,
) -> rs.Supervisor:
    if clock is not None:
        kw.setdefault("sleep", clock.sleep)
        kw.setdefault("monotonic", clock.monotonic)
    else:
        kw.setdefault("sleep", lambda s: time.sleep(0.01))
    return rs.Supervisor(
        card_file,
        {"PATH": "/usr/bin:/bin", "LAB_VAR": "kept"},
        probes=probes or FakeProbes(),
        policy=kw.pop("policy", POLICY),
        poster=poster or FakePoster(),
        token_resolver=lambda project, group: "xoxb-test",
        out=kw.pop("out", None) or _Sink(),
        **kw,
    )


class _Sink:
    def __init__(self) -> None:
        self.text = ""

    def write(self, text: str) -> int:
        self.text += text
        return len(text)

    def flush(self) -> None:
        pass


def py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


# ---------------------------------------------------------------------------
# Running to the end
# ---------------------------------------------------------------------------


def test_a_job_that_succeeds_is_recorded_and_announced(tmp_path):
    card_file = _card(tmp_path, py("print('hello from the job')"))
    poster = FakePoster()
    sink = _Sink()
    code = _supervisor(card_file, poster=poster, out=sink).run()
    card = cards.read_card(card_file)
    assert code == 0 and card.state == cards.STATE_FINISHED and card.exit_code == 0
    assert card.started_at and card.ended_at and card.supervisor_pid
    log = Path(card.log).read_text()
    assert log.startswith("=== murmurent run 20261016-090000-abcd started")
    assert "hello from the job" in log and "hello from the job" in sink.text
    [call] = poster.calls
    assert call["channel"] == "CTEST0001" and call["token"] == "xoxb-test"
    assert call["text"].startswith("Job fit (tester) finished after")
    assert card.notify["posted"][0]["ok"] is True


def test_a_failing_job_is_recorded_and_announced(tmp_path):
    card_file = _card(tmp_path, py("import sys; sys.exit(3)"))
    poster = FakePoster()
    code = _supervisor(card_file, poster=poster).run()
    card = cards.read_card(card_file)
    assert code == 3 and card.state == cards.STATE_FAILED and card.exit_code == 3
    assert "failed after" in poster.calls[0]["text"] and "Exit code 3" in poster.calls[0]["text"]


def test_a_missing_program_fails_plainly(tmp_path):
    card_file = _card(tmp_path, ["no_such_program_murmurent_test"])
    _supervisor(card_file).run()
    card = cards.read_card(card_file)
    assert card.state == cards.STATE_FAILED and card.exit_code == 127
    assert "could not be started" in card.notes[-1]["text"]


def test_the_job_gets_the_thread_limits_and_the_persons_environment(tmp_path):
    code = (
        "import os; print(os.environ['OMP_NUM_THREADS'], os.environ['LAB_VAR'], "
        "repr(os.environ['CUDA_VISIBLE_DEVICES']))"
    )
    card_file = _card(tmp_path, py(code))
    _supervisor(card_file).run()
    assert "2 kept ''" in Path(cards.read_card(card_file).log).read_text()


def test_notices_off_means_nothing_is_posted(tmp_path):
    card_file = _card(tmp_path, py("pass"), notify={"enabled": False})
    poster = FakePoster()
    _supervisor(card_file, poster=poster).run()
    assert poster.calls == []


def test_a_job_ended_by_a_signal_gets_a_hint(tmp_path):
    card_file = _card(tmp_path, py("pass"))
    supervisor = _supervisor(card_file)
    supervisor.card.started_at = cards.to_iso(FRIDAY_MORNING)
    supervisor.record_end(-signal.SIGKILL)
    card = cards.read_card(card_file)
    assert card.state == cards.STATE_FAILED and "SIGKILL" in card.notes[-1]["text"]
    assert "ran out of memory" in card.notes[-1]["text"]


# ---------------------------------------------------------------------------
# Stopping
# ---------------------------------------------------------------------------


def test_stopping_a_running_job(tmp_path):
    card_file = _card(tmp_path, py("import time; time.sleep(30)"))
    poster = FakePoster()
    supervisor = _supervisor(card_file, poster=poster)
    real_sleep = supervisor.sleep

    def sleep_then_stop(seconds: float) -> None:
        real_sleep(seconds)
        supervisor.request_stop()

    supervisor.sleep = sleep_then_stop
    started = time.monotonic()
    supervisor.run()
    card = cards.read_card(card_file)
    assert card.state == cards.STATE_STOPPED
    assert time.monotonic() - started < 20
    assert poster.calls == []  # the person stopped it; no notice


def test_stopping_before_the_start(tmp_path):
    card_file = _card(
        tmp_path,
        py("pass"),
        cores=0,
        requested={"at": cards.to_iso(FRIDAY_MORNING + dt.timedelta(hours=3))},
    )
    clock = FakeClock()
    supervisor = _supervisor(card_file, probes=FakeProbes(clock=clock), clock=clock)
    supervisor.request_stop()
    assert supervisor.run() == 1
    assert cards.read_card(card_file).state == cards.STATE_STOPPED


# ---------------------------------------------------------------------------
# Waiting
# ---------------------------------------------------------------------------


def test_waiting_for_a_start_time(tmp_path):
    start = FRIDAY_MORNING + dt.timedelta(hours=2)
    card_file = _card(
        tmp_path, py("pass"), cores=0, env_set={}, requested={"at": cards.to_iso(start), "cores": 4}
    )
    clock = FakeClock()
    supervisor = _supervisor(card_file, probes=FakeProbes(clock=clock), clock=clock)
    assert supervisor.wait_until_ready()
    assert clock.now() >= start
    assert supervisor.card.cores == 4 and supervisor.card.env_set["OMP_NUM_THREADS"] == "4"


def test_waiting_for_the_load_to_fall(tmp_path):
    card_file = _card(tmp_path, py("pass"), cores=0, env_set={}, requested={"when_load_below": 50})
    clock = FakeClock()
    probes = FakeProbes(clock=clock, load=lambda t: 90.0 if t < 600 else 30.0)
    supervisor = _supervisor(card_file, probes=probes, clock=clock)
    assert supervisor.wait_until_ready()
    assert clock.t >= 600
    assert supervisor.card.cores == POLICY.default_cores


def test_waiting_for_room_when_the_server_is_busy(tmp_path):
    card_file = _card(tmp_path, py("pass"), cores=0, env_set={}, requested={"cores": 8})
    clock = FakeClock()
    probes = FakeProbes(clock=clock, load=lambda t: 95.0 if t < 300 else 20.0)
    supervisor = _supervisor(card_file, probes=probes, clock=clock)
    assert supervisor.wait_until_ready()
    assert supervisor.card.cores == 8


def test_a_rule_broken_at_start_time_fails_and_says_why(tmp_path):
    card_file = _card(tmp_path, py("pass"), cores=0, env_set={}, requested={"gpus": 3})
    clock = FakeClock()
    poster = FakePoster()
    probes = FakeProbes(clock=clock, gpus=[gpu(i, 0) for i in range(4)])
    supervisor = _supervisor(card_file, probes=probes, clock=clock, poster=poster)
    assert supervisor.run() == 1
    card = cards.read_card(card_file)
    assert card.state == cards.STATE_FAILED and card.notes[-1]["text"].startswith("Could not start")
    assert poster.calls and poster.calls[0]["text"] == "Job fit (tester) could not start."


def test_gpus_chosen_at_start_time(tmp_path):
    card_file = _card(tmp_path, py("pass"), cores=0, env_set={}, requested={"gpus": 1})
    clock = FakeClock()
    probes = FakeProbes(clock=clock, gpus=[gpu(0, 70), gpu(1, 3)])
    supervisor = _supervisor(card_file, probes=probes, clock=clock)
    assert supervisor.wait_until_ready()
    assert supervisor.card.gpus == [1]
    assert supervisor.card.env_set["CUDA_VISIBLE_DEVICES"] == "1"


# ---------------------------------------------------------------------------
# Stalls, disk, exceptions
# ---------------------------------------------------------------------------


def test_a_quiet_log_is_reported_as_stalled_and_recovers(tmp_path):
    log = tmp_path / "job.log"
    log.write_text("start\n")
    card_file = _card(
        tmp_path,
        py("pass"),
        stall_minutes=30,
        state=cards.STATE_RUNNING,
        started_at=cards.to_iso(FRIDAY_MORNING),
    )
    poster = FakePoster()
    supervisor = _supervisor(card_file, poster=poster)
    supervisor.check_stall(FRIDAY_MORNING + dt.timedelta(minutes=1))
    supervisor.check_stall(FRIDAY_MORNING + dt.timedelta(minutes=20))
    assert supervisor.card.state == cards.STATE_RUNNING
    supervisor.check_stall(FRIDAY_MORNING + dt.timedelta(minutes=31))
    assert supervisor.card.state == cards.STATE_STALLED
    assert "No new output for 31 min" in supervisor.card.notes[-1]["text"]
    assert len(poster.calls) == 1 and "may be stuck" in poster.calls[0]["text"]
    supervisor.check_stall(FRIDAY_MORNING + dt.timedelta(minutes=40))
    assert len(poster.calls) == 1  # one notice per stall, not one a minute
    with log.open("a") as handle:
        handle.write("more\n")
    supervisor.check_stall(FRIDAY_MORNING + dt.timedelta(minutes=41))
    assert supervisor.card.state == cards.STATE_RUNNING
    assert "no longer stalled" in supervisor.card.notes[-1]["text"]


def test_the_output_folder_growth_gives_a_disk_estimate(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    card_file = _card(
        tmp_path,
        py("pass"),
        out=str(out),
        state=cards.STATE_RUNNING,
        started_at=cards.to_iso(FRIDAY_MORNING),
    )
    probes = FakeProbes(disk=(1000 * GB, 400 * GB, 600 * GB))
    supervisor = _supervisor(card_file, probes=probes)
    supervisor.sample_disk(FRIDAY_MORNING)
    (out / "part1.bin").write_bytes(b"x" * 6000)
    supervisor.sample_disk(FRIDAY_MORNING + dt.timedelta(seconds=30))  # not due yet
    assert len(supervisor.card.disk_samples) == 1
    supervisor.sample_disk(FRIDAY_MORNING + dt.timedelta(minutes=1))
    estimates = supervisor.card.estimates
    assert estimates["disk_growth_bytes_per_hour"] == pytest.approx(6000 * 60)
    assert estimates["hours_until_disk_full"] == pytest.approx(600 * GB / (6000 * 60))
    assert len(supervisor.card.disk_samples) == 2


def test_a_huge_output_folder_is_not_walked(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    for i in range(5):
        (out / f"f{i}").write_text("x")
    assert rs.folder_size(out, max_entries=3) is None
    assert rs.folder_size(out) == 5
    monkeypatch.setattr(rs, "folder_size", lambda path: None)
    card_file = _card(tmp_path, py("pass"), out=str(out), started_at=cards.to_iso(FRIDAY_MORNING))
    supervisor = _supervisor(card_file)
    supervisor.sample_disk(FRIDAY_MORNING)
    assert "too many files" in supervisor.card.estimates["disk"]


def test_the_end_of_an_exception_is_noted_once(tmp_path):
    until = FRIDAY_MORNING + dt.timedelta(hours=1)
    card_file = _card(
        tmp_path, py("pass"), exception={"reason": "deadline", "until": cards.to_iso(until)}
    )
    supervisor = _supervisor(card_file)
    supervisor.check_exception(FRIDAY_MORNING)
    assert supervisor.card.notes == []
    supervisor.check_exception(until + dt.timedelta(minutes=1))
    supervisor.check_exception(until + dt.timedelta(minutes=2))
    assert len(supervisor.card.notes) == 1 and "exception ended" in supervisor.card.notes[0]["text"]


def test_a_failing_routine_check_never_stops_the_job(tmp_path):
    card_file = _card(tmp_path, py("pass"), started_at=cards.to_iso(FRIDAY_MORNING))
    supervisor = _supervisor(card_file)

    def broken(now):
        raise RuntimeError("disk vanished")

    supervisor.sample_disk = broken  # type: ignore[method-assign]
    supervisor.housekeeping()
    assert "A routine check failed" in supervisor.card.notes[-1]["text"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def test_the_environment_copy_is_read_once_and_deleted(tmp_path):
    card_file = _card(tmp_path, py("pass"))
    snapshot = card_file.with_name(card_file.stem + ".env.json")
    snapshot.write_text(json.dumps({"A": "1"}))
    assert rs.load_environment(card_file) == {"A": "1"}
    assert not snapshot.exists()
    assert rs.load_environment(card_file)  # falls back to this process's own


def test_main_needs_exactly_one_card(capsys):
    assert rs.main([]) == 2
    assert "usage" in capsys.readouterr().err
