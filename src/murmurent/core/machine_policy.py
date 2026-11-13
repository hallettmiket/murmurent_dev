"""
Purpose: The machines a person can reach, and three read-only questions every
         one of them answers the same way: is it up, how busy is it, how full
         is its storage.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-13
Input:   Built-in profiles (``laptop``, ``ssh_server``, ``alliance``); the lab's
         ``policy/machines.yaml`` in its records repository; the file named by
         ``$MURMURENT_MACHINES_FILE`` (tests, or trying a machine before the PI
         adopts it); the person's own logins in ``~/.murmurent/hosts.yaml``.
Output:  :class:`Machine` records; :class:`Status`, :class:`Load` and
         :class:`Usage` reports, one per machine, each saying "unreachable" with
         the reason rather than failing.

A machine is described in two layers, the way a cluster is in
:mod:`cluster_policy`:

1. A **profile** in this module holds what is true of every machine of that
   family and how to ask it questions. ``laptop`` is this computer. ``ssh_server``
   is a Linux server reached by ssh: load from ``uptime`` and ``nproc``, GPUs
   from ``nvidia-smi`` when it is there, storage from ``df`` over the tiers of
   the lab folder protocol, people from ``who`` and ``ps``. ``alliance`` is a
   cluster of the Digital Research Alliance of Canada, and delegates to the
   cluster code (``murmurent cluster usage`` and ``scan``).
2. The lab's **machines.yaml** names each machine, picks its profile, and
   overrides facts: the address, the data root, the tiers, or for a cluster the
   name of its entry in ``clusters.yaml``, so that file stays the source for
   cluster facts.

Each person's login on a machine is not policy. It lives in their own
``hosts.yaml`` (``murmurent machine add``). A declared machine with no login
recorded is listed as "not set up" and is never probed.

Every probe is read-only, goes through ``ssh -o BatchMode=yes`` with a timeout,
and reports "unreachable: <why>" in its row instead of raising.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import os
import platform
import shutil
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import yaml

from . import hosts as _hosts
from . import remote as _remote

MACHINES_ENV = "MURMURENT_MACHINES_FILE"
MACHINES_RELATIVE_PATH = Path("policy") / "machines.yaml"
LAPTOP_NAME = "laptop"
PROFILE_NAMES = ("laptop", "ssh_server", "alliance")

STATUS_TIMEOUT = 20
LOAD_TIMEOUT = 45
USAGE_TIMEOUT = 60

#: A GPU counts as busy above this utilisation, or with this share of its
#: memory taken: a model loaded and waiting still blocks the card.
GPU_BUSY_UTILISATION = 5
GPU_BUSY_MEMORY_SHARE = 0.10

# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tier:
    """One storage folder on a machine, and what it is for."""

    name: str
    path: str
    purpose: str = ""
    quota: str = ""


@dataclass(frozen=True)
class Machine:
    """One declared machine, with the profile's facts filled in."""

    name: str
    profile: str = "ssh_server"
    description: str = ""
    ssh_host: str = ""
    data_root: str = ""
    cluster: str = ""
    tiers: tuple[Tier, ...] = ()
    notes: str = ""

    def is_local(self) -> bool:
        return self.profile == "laptop"


@dataclass
class MachinePolicy:
    """The machines a lab declares, with where they were read from."""

    machines: dict[str, Machine] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def get(self, name: str) -> Machine | None:
        return self.machines.get(name)

    def names(self) -> list[str]:
        """This computer first, then the rest in alphabetical order."""
        rest = sorted(n for n in self.machines if n != LAPTOP_NAME)
        return ([LAPTOP_NAME] if LAPTOP_NAME in self.machines else []) + rest


# The lab folder protocol (rules/data-storage.md): what an ssh_server holds
# under its data root unless the lab says otherwise.
LAB_FOLDERS: tuple[tuple[str, str], ...] = (
    ("immutable", "original data; read-only once placed"),
    ("append_only", "analyses and large intermediate files; added to, never overwritten"),
    ("modifiable", "a project's working data that may change"),
    ("mothballed", "files waiting to go to long-term storage"),
    ("release", "the lab's private copy of published papers and software"),
    ("cottage", "each person's large files, such as conda environments"),
    ("tools", "tools of general use to the lab"),
    ("db", "databases used by several people"),
)


def lab_folder_tiers(data_root: str) -> tuple[Tier, ...]:
    root = data_root.rstrip("/")
    return tuple(Tier(name=n, path=f"{root}/{n}", purpose=p) for n, p in LAB_FOLDERS)


PROFILES: dict[str, dict[str, Any]] = {
    "laptop": {"description": "this computer"},
    "ssh_server": {"description": "a Linux server reached by ssh"},
    "alliance": {"description": "a cluster of the Digital Research Alliance of Canada"},
}


# ---------------------------------------------------------------------------
# Reading the lab's file
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return None, f"{path}: could not read it ({exc.__class__.__name__})"
    if not isinstance(data, dict):
        return None, f"{path}: expected a mapping at the top"
    return data, None


def _tiers_from(raw: Any, base: tuple[Tier, ...], where: str, problems: list[str]) -> tuple[Tier, ...]:
    if not isinstance(raw, dict):
        problems.append(f"{where}.tiers: expected a mapping of tier name to settings")
        return base
    tiers = {t.name: t for t in base}
    for name, settings in raw.items():
        name = str(name)
        if isinstance(settings, str):
            settings = {"path": settings}
        if not isinstance(settings, dict):
            problems.append(f"{where}.tiers.{name}: a tier is a path, or a mapping with a path")
            continue
        tier = tiers.get(name, Tier(name=name, path=""))
        changes = {k: str(settings[k]) for k in ("path", "purpose", "quota")
                   if k in settings and settings[k] is not None}
        tier = replace(tier, **changes)
        if not tier.path:
            problems.append(f"{where}.tiers.{name}: a tier needs a path")
            continue
        tiers[name] = tier
    return tuple(tiers.values())


def _machine_from(name: str, raw: dict[str, Any], where: str, problems: list[str]) -> Machine:
    profile = str(raw.get("profile") or "ssh_server")
    if profile not in PROFILES:
        problems.append(f"{where}: unknown profile {profile!r}; using 'ssh_server'")
        profile = "ssh_server"
    machine = Machine(name=name, profile=profile, description=PROFILES[profile]["description"])
    changes: dict[str, Any] = {}
    for key in ("description", "ssh_host", "data_root", "cluster", "notes"):
        if key in raw and raw[key] is not None:
            changes[key] = str(raw[key])
    machine = replace(machine, **changes)
    if profile == "alliance":
        if not machine.cluster:
            machine = replace(machine, cluster=name)
        machine = _fill_from_cluster(machine, problems, where)
    elif profile == "ssh_server":
        base = lab_folder_tiers(machine.data_root) if machine.data_root else ()
        tiers = _tiers_from(raw["tiers"], base, where, problems) if raw.get("tiers") is not None else base
        if not tiers:
            problems.append(f"{where}: an ssh_server needs a data_root or a list of tiers to report storage")
        machine = replace(machine, tiers=tiers)
    return machine


def _fill_from_cluster(machine: Machine, problems: list[str], where: str) -> Machine:
    """An alliance machine takes its address and tiers from its cluster entry."""
    from . import cluster_policy as _cp

    cluster = _cp.load_clusters().get(machine.cluster)
    if cluster is None:
        problems.append(f"{where}: no cluster named {machine.cluster!r} in policy/clusters.yaml")
        return machine
    changes: dict[str, Any] = {}
    if not machine.ssh_host:
        changes["ssh_host"] = cluster.ssh_host
    if machine.description == PROFILES["alliance"]["description"] and cluster.description:
        changes["description"] = cluster.description
    changes["tiers"] = tuple(Tier(name=t.name, path=t.path, purpose=t.purpose, quota=t.quota)
                             for t in cluster.tiers)
    return replace(machine, **changes)


def _apply_file(policy: MachinePolicy, path: Path) -> None:
    data, problem = _read_yaml(path)
    if problem:
        policy.problems.append(problem)
        return
    policy.sources.append(str(path))
    machines = data.get("machines", data)
    if not isinstance(machines, dict):
        policy.problems.append(f"{path}: 'machines' must be a mapping of machine name to settings")
        return
    for name, raw in machines.items():
        if not isinstance(raw, dict):
            policy.problems.append(f"{path}: machine {name!r} must be a mapping")
            continue
        policy.machines[str(name)] = _machine_from(str(name), raw, f"{path}: {name}", policy.problems)


def lab_machines_path(env: dict[str, str] | None = None) -> Path | None:
    """``policy/machines.yaml`` in the lab's records repository, if that is known."""
    try:
        from .repo import lab_mgmt_repo_root

        return lab_mgmt_repo_root(env) / MACHINES_RELATIVE_PATH
    except Exception:  # noqa: BLE001 - no lab records on this machine
        return None


def _laptop(env: dict[str, str]) -> Machine:
    tiers = [Tier(name="home", path=str(Path.home()), purpose="your home folder")]
    data_root = env.get("MURMURENT_DATA_ROOT") or env.get("MURMURENT_LAB_VM_ROOT") or ""
    if data_root:
        tiers.append(Tier(name="data", path=data_root, purpose="this computer's data root"))
    return Machine(name=LAPTOP_NAME, profile="laptop", description=f"this computer ({socket.gethostname()})",
                   data_root=data_root, tiers=tuple(tiers))


def load_machines(env: dict[str, str] | None = None) -> MachinePolicy:
    """This computer, then the lab's file, then the override file."""
    env = os.environ if env is None else env
    policy = MachinePolicy()
    policy.machines[LAPTOP_NAME] = _laptop(env)
    lab_path = lab_machines_path(env)
    if lab_path is not None and lab_path.is_file():
        _apply_file(policy, lab_path)
    override = env.get(MACHINES_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            _apply_file(policy, path)
        else:
            policy.problems.append(f"${MACHINES_ENV} names {path}, which does not exist")
    return policy


# ---------------------------------------------------------------------------
# The person's set: which declared machines they have a login for
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Member:
    """One machine in a person's set: the declaration and their login, if any."""

    machine: Machine
    host: _hosts.Host | None

    @property
    def name(self) -> str:
        return self.machine.name

    @property
    def set_up(self) -> bool:
        return self.machine.is_local() or (self.host is not None and self.host.is_remote())

    @property
    def login(self) -> str:
        if self.machine.is_local():
            return getpass.getuser()
        return self.host.ssh_host if self.host is not None and self.host.is_remote() else ""


def login_for(machine: Machine, rows: dict[str, _hosts.Host]) -> _hosts.Host | None:
    """The person's own row for a machine: under its name, else its cluster's name."""
    for key in (machine.name, machine.cluster):
        host = rows.get(key) if key else None
        if host is not None and host.is_remote():
            return host
    return None


def person_set(policy: MachinePolicy | None = None, env: dict[str, str] | None = None) -> list[Member]:
    policy = policy or load_machines(env)
    rows = _hosts.read(env)
    out = []
    for name in policy.names():
        machine = policy.machines[name]
        host = rows[_hosts.LOCAL_NAME] if machine.is_local() else login_for(machine, rows)
        out.append(Member(machine=machine, host=host))
    return out


def register_login(machine: Machine, ssh_host: str, user: str = "",
                   env: dict[str, str] | None = None) -> Path:
    """Record the person's login for a machine in their own hosts.yaml."""
    if "@" in ssh_host and not user:
        user = ssh_host.split("@", 1)[0]
    host = _hosts.Host(name=machine.name, kind="ssh", ssh_host=ssh_host, remote_user=user,
                       description=machine.description or f"machine {machine.name}")
    rows = _hosts.read(env)
    rows[machine.name] = host
    return _hosts.write(rows, env)


def setup_hint(machine: Machine) -> str:
    address = machine.ssh_host or "<address>"
    return f"not set up: run murmurent machine add {machine.name} --ssh-host <login>@{address}"


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Status:
    name: str
    profile: str
    set_up: bool = True
    reachable: bool = False
    checked_at: str = ""
    detail: str = ""
    problem: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Load:
    name: str
    profile: str
    set_up: bool = True
    reachable: bool = False
    checked_at: str = ""
    problem: str = ""
    cores_busy: int | None = None
    cores_total: int | None = None
    gpus_busy: int | None = None
    gpus_total: int | None = None
    jobs: int | None = None
    sessions: int | None = None
    who: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TierUse:
    name: str
    path: str
    used: int | None = None
    quota: int | None = None
    files: int | None = None
    files_quota: int | None = None
    note: str = ""

    @property
    def percent(self) -> float | None:
        if self.used is None or not self.quota:
            return None
        return 100.0 * self.used / self.quota

    @property
    def files_percent(self) -> float | None:
        if self.files is None or not self.files_quota:
            return None
        return 100.0 * self.files / self.files_quota

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["percent"] = None if self.percent is None else round(self.percent, 1)
        d["files_percent"] = None if self.files_percent is None else round(self.files_percent, 1)
        return d


@dataclass
class Usage:
    name: str
    profile: str
    set_up: bool = True
    reachable: bool = False
    checked_at: str = ""
    problem: str = ""
    tiers: list[TierUse] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def nearest_limit(self) -> TierUse | None:
        """The tier closest to running out, by space or by number of files."""
        best, best_share = None, -1.0
        for t in self.tiers:
            share = max(t.percent or -1.0, t.files_percent or -1.0)
            if share > best_share:
                best, best_share = t, share
        return best if best_share >= 0 else None

    def to_dict(self) -> dict[str, Any]:
        nearest = self.nearest_limit()
        return {
            "name": self.name, "profile": self.profile, "set_up": self.set_up,
            "reachable": self.reachable, "checked_at": self.checked_at, "problem": self.problem,
            "tiers": [t.to_dict() for t in self.tiers],
            "nearest_limit": None if nearest is None else {
                "tier": nearest.name,
                "percent": round(max(nearest.percent or 0.0, nearest.files_percent or 0.0), 1),
            },
            "problems": list(self.problems),
        }


# ---------------------------------------------------------------------------
# Running commands: one chokepoint, replaceable in tests
# ---------------------------------------------------------------------------

#: ``runner(host, command, timeout) -> (returncode, stdout, stderr)``.
Runner = Callable[[_hosts.Host, str, int], tuple[int, str, str]]


def ssh_runner(host: _hosts.Host, command: str, timeout: int) -> tuple[int, str, str]:
    """Run over ``ssh -o BatchMode=yes`` through :class:`core.remote.Remote`; never raises."""
    try:
        result = _remote.Remote(host).run(command, timeout=timeout, check=False)
    except _remote.RemoteError:
        return 124, "", f"no answer within {timeout} seconds"
    except (OSError, ValueError) as exc:
        return 255, "", str(exc)
    return result.returncode, result.stdout, result.stderr


def _why(returncode: int, stderr: str) -> str:
    text = (stderr.strip().splitlines() or [""])[-1]
    if returncode == 124:
        return text or "timed out"
    if returncode == 255 and not text:
        return "ssh could not connect"
    return text or f"exit code {returncode}"


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


class Probe:
    """The three questions. Each profile answers them its own way."""

    def __init__(self, member: Member, runner: Runner | None = None, env: dict[str, str] | None = None):
        self.member = member
        self.machine = member.machine
        self.runner = runner or ssh_runner
        self.env = os.environ if env is None else env

    def status(self) -> Status:
        raise NotImplementedError

    def load(self) -> Load:
        raise NotImplementedError

    def usage(self) -> Usage:
        raise NotImplementedError

    def _run(self, command: str, timeout: int) -> tuple[int, str, str]:
        assert self.member.host is not None
        return self.runner(self.member.host, command, timeout)


class LaptopProbe(Probe):
    """This computer: no ssh, answers from the operating system."""

    def status(self) -> Status:
        return Status(name=self.machine.name, profile="laptop", reachable=True,
                      checked_at=_now(), detail=socket.gethostname())

    def load(self) -> Load:
        total = os.cpu_count() or 0
        try:
            busy = min(total, round(os.getloadavg()[0]))
        except (OSError, AttributeError):
            busy = None
        return Load(name=self.machine.name, profile="laptop", reachable=True, checked_at=_now(),
                    cores_busy=busy, cores_total=total, gpus_busy=0, gpus_total=0,
                    jobs=None, sessions=1, who=[getpass.getuser()])

    def usage(self) -> Usage:
        report = Usage(name=self.machine.name, profile="laptop", reachable=True, checked_at=_now())
        seen_disks: dict[int, str] = {}
        for tier in self.machine.tiers:
            use = TierUse(name=tier.name, path=tier.path)
            try:
                disk = shutil.disk_usage(tier.path)
                device = os.stat(tier.path).st_dev
            except OSError as exc:
                use.note = f"not found ({exc.__class__.__name__})"
                report.tiers.append(use)
                continue
            use.used, use.quota = disk.used, disk.total
            use.note = f"same disk as {seen_disks[device]}" if device in seen_disks else "whole disk"
            seen_disks.setdefault(device, tier.name)
            report.tiers.append(use)
        return report


_SERVER_LOAD_SCRIPT = (
    "echo '==nproc'; nproc 2>/dev/null || getconf _NPROCESSORS_ONLN; "
    "echo '==uptime'; uptime; "
    "echo '==gpu'; nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total "
    "--format=csv,noheader,nounits 2>/dev/null; "
    "echo '==who'; who 2>/dev/null; "
    "echo '==ps'; ps -eo user=,pcpu= 2>/dev/null; "
    "echo '==end'"
)


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("=="):
            current = line[2:].strip()
            out[current] = []
        elif current:
            out[current].append(line)
    return out


def parse_uptime_load(text: str) -> float | None:
    """The one-minute load average from a line of ``uptime``."""
    import re

    m = re.search(r"load averages?:\s*([\d.]+)", " ".join(text.split()))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_nvidia_smi(lines: list[str]) -> tuple[int, int]:
    """(busy, total) from ``nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total``."""
    total = busy = 0
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        total += 1
        try:
            util = float(parts[1])
            used, size = float(parts[2]), float(parts[3])
        except ValueError:
            continue
        if util >= GPU_BUSY_UTILISATION or (size > 0 and used / size >= GPU_BUSY_MEMORY_SHARE):
            busy += 1
    return busy, total


def parse_ps_cores(lines: list[str]) -> dict[str, float]:
    """Cores in use per user, from ``ps -eo user=,pcpu=`` (100% is one core)."""
    cores: dict[str, float] = {}
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            cores[parts[0]] = cores.get(parts[0], 0.0) + float(parts[1]) / 100.0
        except ValueError:
            continue
    return cores


def describe_people(logged_in: list[str], cores: dict[str, float]) -> list[str]:
    """One phrase per person: the busy ones first, with their cores, then the idle ones."""
    busy = {u: c for u, c in cores.items() if c >= 0.5}
    out = [f"{u} ({c:.0f} core{'s' if round(c) != 1 else ''})"
           for u, c in sorted(busy.items(), key=lambda kv: -kv[1])]
    out += [f"{u} (logged in)" for u in sorted(set(logged_in)) if u not in busy]
    return out


class SshServerProbe(Probe):
    """A Linux server reached by ssh."""

    def status(self) -> Status:
        report = Status(name=self.machine.name, profile="ssh_server", checked_at=_now())
        code, out, err = self._run("hostname", STATUS_TIMEOUT)
        if code != 0:
            report.problem = "unreachable: " + _why(code, err)
            return report
        report.reachable, report.detail = True, out.strip().splitlines()[-1] if out.strip() else "up"
        return report

    def load(self) -> Load:
        report = Load(name=self.machine.name, profile="ssh_server", checked_at=_now())
        code, out, err = self._run(_SERVER_LOAD_SCRIPT, LOAD_TIMEOUT)
        if code != 0 and "==end" not in out:
            report.problem = "unreachable: " + _why(code, err)
            return report
        report.reachable = True
        parts = _sections(out)
        try:
            report.cores_total = int((parts.get("nproc") or ["0"])[0].strip())
        except ValueError:
            report.problems.append("nproc gave no number")
        load1 = parse_uptime_load("\n".join(parts.get("uptime", [])))
        if load1 is None:
            report.problems.append("uptime gave no load average")
        elif report.cores_total:
            report.cores_busy = min(report.cores_total, round(load1))
        gpu_lines = [l for l in parts.get("gpu", []) if l.strip()]
        report.gpus_busy, report.gpus_total = parse_nvidia_smi(gpu_lines) if gpu_lines else (0, 0)
        logged_in = [l.split()[0] for l in parts.get("who", []) if l.split()]
        # People, not terminals: one person with twelve tmux windows is one person.
        report.sessions = len(set(logged_in))
        report.who = describe_people(logged_in, parse_ps_cores(parts.get("ps", [])))
        return report

    def usage(self) -> Usage:
        from . import slurm as _slurm
        import shlex

        report = Usage(name=self.machine.name, profile="ssh_server", checked_at=_now())
        if not self.machine.tiers:
            report.problem = "no tiers declared for this machine"
            report.reachable = True
            return report
        paths = " ".join(shlex.quote(t.path) for t in self.machine.tiers)
        code, out, err = self._run(f"echo '==df'; df -P {paths} 2>/dev/null; echo '==end'", USAGE_TIMEOUT)
        if code != 0 and "==end" not in out:
            report.problem = "unreachable: " + _why(code, err)
            return report
        report.reachable = True
        rows = _slurm.parse_df("\n".join(_sections(out).get("df", [])))
        seen_mounts: dict[str, str] = {}
        for tier in self.machine.tiers:
            use = TierUse(name=tier.name, path=tier.path)
            best = _mount_for(rows, tier.path)
            if best is None:
                use.note = "not found"
            else:
                use.used, use.quota = best["used"], best["size"]
                mount = best["mounted_on"]
                if mount in seen_mounts:
                    use.note = f"same filesystem as {seen_mounts[mount]}"
                else:
                    seen_mounts[mount] = tier.name
                    use.note = f"filesystem {mount}" if mount.rstrip("/") != tier.path.rstrip("/") else ""
            report.tiers.append(use)
        return report


def _mount_for(df_rows: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    best = None
    for row in df_rows:
        mount = row["mounted_on"].rstrip("/") or "/"
        if path == mount or path.startswith(mount + "/") or mount == "/":
            if best is None or len(mount) > len(best["mounted_on"].rstrip("/")):
                best = row
    return best


class AllianceProbe(Probe):
    """A cluster: the cluster code already knows how to ask it."""

    def _client(self):
        from . import cluster as _cl

        cluster = _cl.find_cluster(self.machine.cluster or self.machine.name, self.env)
        return _cl.ClusterClient(cluster, self.member.host, self.env)

    def status(self) -> Status:
        report = Status(name=self.machine.name, profile="alliance", checked_at=_now())
        try:
            ok, where = self._client().probe()
        except Exception as exc:  # noqa: BLE001 - never fail the table
            ok, where = False, str(exc)
        if ok:
            report.reachable, report.detail = True, where
        else:
            report.problem = "unreachable: " + where
        return report

    def load(self) -> Load:
        from . import slurm as _slurm

        report = Load(name=self.machine.name, profile="alliance", checked_at=_now())
        try:
            client = self._client()
            ok, where = client.probe()
            if not ok:
                report.problem = "unreachable: " + where
                return report
            scan = client.scan(days=1)
        except Exception as exc:  # noqa: BLE001
            report.problem = "unreachable: " + str(exc)
            return report
        report.reachable = True
        report.cores_total = sum(int(n.get("cpus_total") or 0) for n in scan.nodes)
        report.cores_busy = sum(int(n.get("cpus_allocated") or 0) for n in scan.nodes)
        report.gpus_total = sum(_slurm.gpu_count(n.get("gres", "")) for n in scan.nodes)
        running = [j for j in scan.queue if j.get("state") == "RUNNING"]
        report.gpus_busy = min(report.gpus_total, sum(_slurm.gpu_count(j.get("gres", "")) for j in running))
        report.jobs = len(running)
        report.sessions = len(scan.queue) - len(running)
        for row in _slurm.queue_summary(scan.queue):
            if row["running"]:
                text = f"{row['user']} ({row['running_cores']} cores"
                if row["running_gpus"]:
                    text += f", {row['running_gpus']} GPU{'s' if row['running_gpus'] != 1 else ''}"
                text += ")"
            else:
                text = f"{row['user']} ({row['waiting']} waiting)"
            report.who.append(text)
        report.problems = list(scan.problems)
        return report

    def usage(self) -> Usage:
        report = Usage(name=self.machine.name, profile="alliance", checked_at=_now())
        try:
            client = self._client()
            ok, where = client.probe()
            if not ok:
                report.problem = "unreachable: " + where
                return report
            usage = client.usage()
        except Exception as exc:  # noqa: BLE001
            report.problem = "unreachable: " + str(exc)
            return report
        report.reachable = True
        for t in usage.tiers:
            report.tiers.append(TierUse(name=t.tier.name, path=t.path, used=t.used, quota=t.quota,
                                        files=t.files, files_quota=t.files_quota, note=t.note))
        report.problems = list(usage.problems)
        return report


PROBES: dict[str, type[Probe]] = {
    "laptop": LaptopProbe,
    "ssh_server": SshServerProbe,
    "alliance": AllianceProbe,
}


def probe_for(member: Member, runner: Runner | None = None, env: dict[str, str] | None = None) -> Probe:
    return PROBES[member.machine.profile](member, runner, env)


# ---------------------------------------------------------------------------
# Asking every set-up machine at once
# ---------------------------------------------------------------------------


def _not_set_up(member: Member, kind: str):
    cls = {"status": Status, "load": Load, "usage": Usage}[kind]
    return cls(name=member.name, profile=member.machine.profile, set_up=False,
               problem=setup_hint(member.machine))


def ask_all(members: list[Member], kind: str, runner: Runner | None = None,
            env: dict[str, str] | None = None, workers: int = 8) -> list[Any]:
    """``status``, ``load`` or ``usage`` of every machine in the set, in parallel.

    A machine the person has not set up gets a row saying so and is never
    probed. The rows come back in the set's order.
    """
    if kind not in ("status", "load", "usage"):
        raise ValueError(f"kind must be status, load or usage, not {kind!r}")

    def one(member: Member):
        if not member.set_up:
            return _not_set_up(member, kind)
        try:
            return getattr(probe_for(member, runner, env), kind)()
        except Exception as exc:  # noqa: BLE001 - a probe never takes the table down
            report = _not_set_up(member, kind)
            report.set_up = True
            report.problem = f"unreachable: {exc}"
            report.checked_at = _now()
            return report

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(members) or 1))) as pool:
        return list(pool.map(one, members))


# ---------------------------------------------------------------------------
# Remembering the last answer, for the listing
# ---------------------------------------------------------------------------


def state_file(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    home = Path(env.get("MURMURENT_HOME") or (Path.home() / ".murmurent")).expanduser()
    return home / "machines_state.json"


def read_state(env: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    import json

    path = state_file(env)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def remember(reports: list[Any], env: dict[str, str] | None = None) -> None:
    """Keep each machine's reachability and the time it was checked."""
    import json

    state = read_state(env)
    for r in reports:
        if not getattr(r, "set_up", True) or not r.checked_at:
            continue
        state[r.name] = {"reachable": r.reachable, "checked_at": r.checked_at,
                         "problem": r.problem, "detail": getattr(r, "detail", "")}
    path = state_file(env)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


__all__ = [
    "MACHINES_ENV", "LAPTOP_NAME", "PROFILE_NAMES", "PROFILES",
    "Tier", "Machine", "MachinePolicy", "Member",
    "Status", "Load", "Usage", "TierUse",
    "load_machines", "lab_machines_path", "person_set", "login_for", "register_login", "setup_hint",
    "Probe", "LaptopProbe", "SshServerProbe", "AllianceProbe", "probe_for", "ask_all",
    "ssh_runner", "read_state", "remember", "state_file",
    "parse_uptime_load", "parse_nvidia_smi", "parse_ps_cores", "describe_people", "lab_folder_tiers",
]
