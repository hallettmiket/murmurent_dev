"""Fakes for the run launcher's tests (#151): the machine, tmux and Slack.

Nothing here starts tmux, calls nvidia-smi or reaches the network.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from murmurent.core import run_launcher as rl

GB = 1024**3
#: A Friday, inside the default working hours.
FRIDAY_MORNING = dt.datetime(2026, 10, 16, 9, 0).astimezone()
FRIDAY_NIGHT = dt.datetime(2026, 10, 16, 22, 0).astimezone()


class FakeClock:
    """A clock that moves only when something sleeps on it."""

    def __init__(self, start: dt.datetime = FRIDAY_MORNING) -> None:
        self.start = start
        self.t = 0.0

    def sleep(self, seconds: float) -> None:
        self.t += seconds

    def monotonic(self) -> float:
        return self.t

    def now(self) -> dt.datetime:
        return self.start + dt.timedelta(seconds=self.t)


class FakeProbes(rl.SystemProbes):
    """A machine whose every reading the test sets.

    ``load`` may be a number or a function of the fake clock's time in seconds.
    """

    def __init__(
        self,
        *,
        now: dt.datetime = FRIDAY_MORNING,
        cpus: int = 100,
        load=10.0,
        memory: tuple[int, int] | None = (100 * GB, 80 * GB),
        gpus: list[rl.GpuState] | None = None,
        disk: tuple[int, int, int] | None = (1000 * GB, 100 * GB, 900 * GB),
        tmux: bool = True,
        clock: FakeClock | None = None,
    ) -> None:
        self._now = now
        self._cpus = cpus
        self._load = load
        self._memory = memory
        self._gpus = gpus
        self._disk = disk
        self._tmux = tmux
        self.clock = clock
        self.disk_paths: list[Path] = []

    def now(self) -> dt.datetime:
        return self.clock.now() if self.clock else self._now

    def cpu_count(self) -> int:
        return self._cpus

    def load_1min(self) -> float | None:
        if callable(self._load):
            return self._load(self.clock.t if self.clock else 0.0)
        return self._load

    def memory(self) -> tuple[int, int] | None:
        return self._memory

    def gpus(self) -> list[rl.GpuState] | None:
        return self._gpus

    def disk(self, path: Path) -> tuple[int, int, int] | None:
        self.disk_paths.append(Path(path))
        return self._disk

    def has_tmux(self) -> bool:
        return self._tmux


def gpu(index: int, util: float, used: float = 0.0, total: float = 80_000.0) -> rl.GpuState:
    """One fake GPU."""
    return rl.GpuState(index, util, used, total)


class FakeTmux(rl.TmuxRunner):
    """Records what would have been started."""

    def __init__(self, existing: set[str] | None = None, fail: str = "") -> None:
        self.existing = existing or set()
        self.fail = fail
        self.started: list[dict] = []

    def session_exists(self, session: str) -> bool:
        return session in self.existing

    def start(self, session: str, window: str, workdir: Path, command: str) -> None:
        if self.fail:
            raise rl.LaunchError(self.fail)
        self.started.append(
            {
                "session": session,
                "window": window,
                "workdir": Path(workdir),
                "command": command,
                "new_window": session in self.existing,
            }
        )


class FakePoster:
    """Stands in for the Slack post; records every message."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[dict] = []

    def __call__(self, channel: str, text: str, *, token: str | None = None) -> bool:
        self.calls.append({"channel": channel, "text": text, "token": token})
        return self.ok
