"""Stopping the dashboard: the top bar's button and `murmurent dashboard --stop`.

Closing the browser window leaves the dashboard running, and the dashboard
icon starts it with no terminal to press Ctrl+C in. No real dashboard is
stopped here: the button's kill is intercepted, and --stop is pointed at a
throwaway `sleep` process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from murmurent.commands import dashboard_cmd as dc
from murmurent.dashboard.server import create_app


@pytest.fixture
def no_kill(monkeypatch):
    """Record the delayed self-stop instead of running it."""
    started = []

    class FakeTimer:
        def __init__(self, delay, fn):
            started.append(delay)

        def start(self):
            pass

    monkeypatch.setattr(threading, "Timer", FakeTimer)
    return started


def test_stop_button_stops_a_personal_dashboard(no_kill, monkeypatch):
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    res = TestClient(create_app()).post("/api/dashboard/stop")
    assert res.status_code == 200 and res.json()["ok"] is True
    assert no_kill == [0.5]


def test_stop_button_refused_under_a_system_service(no_kill, monkeypatch):
    monkeypatch.setenv("INVOCATION_ID", "abc123")
    res = TestClient(create_app()).post("/api/dashboard/stop")
    assert res.status_code == 409 and "system service" in res.json()["detail"]
    assert no_kill == []


def test_cli_stop_ends_the_recorded_process(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path))
    # Detached, like a real dashboard started by the icon: not a child of this
    # test, so once stopped it is gone rather than waiting to be reaped.
    out = subprocess.run(["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $!"],
                         capture_output=True, text=True, check=True)
    pid = int(out.stdout.strip())
    try:
        pid_file = dc._pid_file(8799)
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(f"{pid}\n")
        assert dc.stop_dashboard(8799) == 0
        assert not dc._alive(pid)
        assert not pid_file.exists()
    finally:
        if dc._alive(pid):
            os.kill(pid, 9)


def test_cli_stop_with_nothing_running(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path))
    monkeypatch.setattr(dc, "_pid_listening_on", lambda port: None)
    stale = dc._pid_file(8799)
    stale.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    stale.write_text(f"{proc.pid}\n")   # a process that has already ended
    assert dc.stop_dashboard(8799) == 0
    assert "No dashboard is running" in capsys.readouterr().out
    assert not stale.exists()
