"""
Purpose: Build Slurm job scripts and read what Slurm's commands print. Pure
         functions: no SSH, no files, so each one is tested on captured output.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-12
Input:   Text from ``sacct``, ``squeue``, ``sinfo``, ``sacctmgr``, ``sshare``,
         ``diskusage_report`` and ``df``, run with the fixed formats below.
Output:  Lists of dicts with plain keys, and the sbatch script text.

Slurm is the scheduler on the Alliance clusters: a person asks it for cores,
memory, GPUs and a time limit, and it runs the job on a compute node when the
resources are free. Every command here asks Slurm for machine-readable output
(``-P`` for pipe-separated, ``-h`` or ``-n`` for no header) so a wording change
in the human tables does not break the parsers.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

# The formats the client runs. Kept here so the parser and the command agree.
SACCT_FIELDS = ("JobID", "JobName", "State", "ExitCode", "Elapsed", "Start", "End",
                "NodeList", "MaxRSS", "ReqMem", "AllocCPUS", "Partition", "Account",
                "Timelimit", "Reason")
SACCT_FORMAT = ",".join(SACCT_FIELDS)

SQUEUE_FIELDS = ("id", "name", "user", "account", "partition", "state", "elapsed",
                 "time_limit", "nodes", "cpus", "gres", "reason")
SQUEUE_FORMAT = "%i|%j|%u|%a|%P|%T|%M|%l|%D|%C|%b|%R"

SINFO_FIELDS = ("nodes", "cpus", "memory_mb", "gres", "state", "cpu_states")
SINFO_FORMAT = "%N|%c|%m|%G|%T|%C"

USAGE_FIELDS = ("User", "AllocCPUS", "ElapsedRaw", "AllocTRES", "Partition")
USAGE_FORMAT = ",".join(USAGE_FIELDS)

#: Slurm job states grouped by what they mean for a job card.
WAITING_STATES = {"PENDING", "CONFIGURING", "REQUEUED", "RESIZING", "SUSPENDED"}
RUNNING_STATES = {"RUNNING", "COMPLETING", "STAGE_OUT"}
FINISHED_STATES = {"COMPLETED"}
STOPPED_STATES = {"CANCELLED", "DEADLINE", "PREEMPTED", "REVOKED"}
FAILED_STATES = {"FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL"}


def card_state(slurm_state: str) -> str:
    """The job-card state (waiting, running, finished, stopped, failed) for a Slurm state."""
    state = slurm_state.split()[0].upper() if slurm_state else ""
    if not state or state in WAITING_STATES:
        return "waiting"
    if state in RUNNING_STATES:
        return "running"
    if state in FINISHED_STATES:
        return "finished"
    if state.startswith("CANCELLED") or state in STOPPED_STATES:
        return "stopped"
    return "failed"


def why_it_ended(slurm_state: str, exit_code: str = "") -> str:
    """A plain sentence for a job that did not finish well."""
    state = slurm_state.split()[0].upper() if slurm_state else ""
    if state == "TIMEOUT":
        return "It ran out of the time it asked for. Ask for a longer --time."
    if state == "OUT_OF_MEMORY":
        return "It ran out of memory. Ask for more with --memory."
    if state == "NODE_FAIL":
        return "The compute node failed. The job can be submitted again as it was."
    if state.startswith("CANCELLED"):
        return "It was cancelled."
    if state == "FAILED":
        return f"The program ended with an error (exit code {exit_code or 'unknown'}). Read its log."
    return ""


# ---------------------------------------------------------------------------
# The job script
# ---------------------------------------------------------------------------


def slurm_time(text: str) -> str:
    """Accept ``2h``, ``90m``, ``3d``, ``1-12:00:00`` or ``HH:MM:SS`` and return Slurm's form."""
    text = text.strip()
    m = re.fullmatch(r"(\d+)\s*([dhm])", text)
    if not m:
        return text
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return f"{n}-00:00:00"
    if unit == "h":
        return f"{n:02d}:00:00"
    return f"{n // 60:02d}:{n % 60:02d}:00"


def sbatch_script(
    command: list[str] | str,
    *,
    name: str,
    account: str,
    partition: str,
    time: str,
    cores: int = 1,
    memory: str = "",
    gpus: int = 0,
    gpu_type: str = "",
    log: str = "slurm-%j.out",
    modules: tuple[str, ...] = (),
    setup: tuple[str, ...] = (),
    workdir: str = "",
    out_dir: str = "",
) -> str:
    """The text of a job script Slurm will accept.

    ``command`` runs inside the staged directory, with ``$MURMURENT_OUT`` set to
    the directory whose contents come back when the job ends.
    """
    lines = ["#!/bin/bash", f"#SBATCH --job-name={name}"]
    if account:
        lines.append(f"#SBATCH --account={account}")
    if partition:
        lines.append(f"#SBATCH --partition={partition}")
    lines.append(f"#SBATCH --time={slurm_time(time)}")
    lines.append(f"#SBATCH --cpus-per-task={max(1, int(cores))}")
    lines.append("#SBATCH --ntasks=1")
    if memory:
        lines.append(f"#SBATCH --mem={memory}")
    if gpus > 0:
        spec = f"{gpu_type}:{gpus}" if gpu_type else str(gpus)
        lines.append(f"#SBATCH --gpus-per-node={spec}")
    lines.append(f"#SBATCH --output={log}")
    lines.append("")
    lines.append("set -euo pipefail")
    if workdir:
        lines.append(f"cd {shlex.quote(workdir)}")
    if out_dir:
        lines.append(f"export MURMURENT_OUT={shlex.quote(out_dir)}")
        lines.append('mkdir -p "$MURMURENT_OUT"')
    lines.append('export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"')
    lines.append('export MKL_NUM_THREADS="$OMP_NUM_THREADS" OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"')
    for module in modules:
        lines.append(f"module load {module}")
    for line in setup:
        lines.append(line)
    lines.append('echo "murmurent: job $SLURM_JOB_ID started on $(hostname) at $(date -Is)"')
    if isinstance(command, str):
        lines.append(command)
    else:
        lines.append(" ".join(shlex.quote(c) for c in command))
    lines.append('echo "murmurent: job $SLURM_JOB_ID ended at $(date -Is)"')
    return "\n".join(lines) + "\n"


def submitted_job_id(sbatch_output: str) -> int | None:
    """The job id from what ``sbatch`` prints, or None."""
    m = re.search(r"Submitted batch job (\d+)", sbatch_output)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _split(text: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        rows.append({name: (parts[i].strip() if i < len(parts) else "")
                     for i, name in enumerate(fields)})
    return rows


def parse_sacct(text: str) -> list[dict[str, str]]:
    """Rows of ``sacct -P -n --format=<SACCT_FORMAT>``, keys in lower case."""
    return [{k.lower(): v for k, v in row.items()} for row in _split(text, SACCT_FIELDS)]


def job_summary(rows: list[dict[str, str]], job_id: int | str) -> dict[str, str] | None:
    """The one row for the job itself (not its ``.batch`` or ``.extern`` steps)."""
    wanted = str(job_id)
    for row in rows:
        if row.get("jobid") == wanted:
            return row
    return None


def parse_squeue(text: str) -> list[dict[str, str]]:
    """Rows of ``squeue -h -o SQUEUE_FORMAT``."""
    return _split(text, SQUEUE_FIELDS)


def parse_sinfo(text: str) -> list[dict[str, Any]]:
    """Rows of ``sinfo -h -o SINFO_FORMAT``, with the CPU split as numbers.

    ``cpu_states`` is Slurm's ``allocated/idle/other/total``.
    """
    rows = []
    for row in _split(text, SINFO_FIELDS):
        parts = row["cpu_states"].split("/")
        numbers = [int(p) if p.isdigit() else 0 for p in parts] + [0, 0, 0, 0]
        rows.append({
            "nodes": row["nodes"],
            "cpus": int(row["cpus"]) if row["cpus"].isdigit() else 0,
            "memory_mb": int(row["memory_mb"]) if row["memory_mb"].isdigit() else 0,
            "gres": row["gres"],
            "state": row["state"],
            "cpus_allocated": numbers[0],
            "cpus_idle": numbers[1],
            "cpus_other": numbers[2],
            "cpus_total": numbers[3],
        })
    return rows


def queue_summary(queue: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Per user, what is running and what is waiting, kept apart.

    A waiting job's cores and GPUs are what it asked for, not what it holds,
    so adding them to the running ones overstates use (the scan once did,
    and the per-user cores came to more than the nodes have). One row per
    user, sorted by running cores then waiting cores, largest first.
    """
    rows: dict[str, dict[str, Any]] = {}
    for job in queue:
        row = rows.setdefault(job.get("user", ""), {
            "user": job.get("user", ""), "running": 0, "running_cores": 0, "running_gpus": 0,
            "waiting": 0, "waiting_cores": 0, "waiting_gpus": 0, "reasons": {},
        })
        cores = int(job["cpus"]) if str(job.get("cpus", "")).isdigit() else 0
        gpus = gpu_count(job.get("gres", ""))
        if job.get("state") == "RUNNING":
            row["running"] += 1
            row["running_cores"] += cores
            row["running_gpus"] += gpus
        else:
            row["waiting"] += 1
            row["waiting_cores"] += cores
            row["waiting_gpus"] += gpus
            reason = (job.get("reason") or "").strip("() ")
            if reason:
                row["reasons"][reason] = row["reasons"].get(reason, 0) + 1
    return sorted(rows.values(), key=lambda r: (-r["running_cores"], -r["waiting_cores"], r["user"]))


def gpu_count(gres: str) -> int:
    """How many GPUs a ``gres`` field names (``gpu:l40s:4`` is 4; ``gpu:2`` is 2)."""
    total = 0
    for part in (gres or "").split(","):
        m = re.match(r"gpu(?::[^:(]+)?:(\d+)", part.strip())
        if m:
            total += int(m.group(1))
    return total


def parse_associations(text: str) -> list[dict[str, str]]:
    """Rows of ``sacctmgr -n -P show assoc format=account,user,partition``."""
    return _split(text, ("account", "user", "partition"))


def accounts_of(rows: list[dict[str, str]], user: str) -> set[str]:
    return {r["account"] for r in rows if r.get("user") == user and r.get("account")}


def has_account(accounts: set[str], account: str) -> bool:
    """Whether the lab's account (``ctb-lab``) covers one of a person's associations.

    The Alliance splits an account into ``<name>_cpu`` and ``<name>_gpu``
    behind the scenes, and rewrites a submission to the right one.
    """
    return any(a == account or a.startswith(account + "_") for a in accounts)


_SIZE_RE = re.compile(r"([\d.]+)\s*([KMGTP]i?B?|B)?", re.I)
_UNITS = {"": 1, "B": 1,
          "K": 1024, "KIB": 1024, "KB": 1000,
          "M": 1024**2, "MIB": 1024**2, "MB": 1000**2,
          "G": 1024**3, "GIB": 1024**3, "GB": 1000**3,
          "T": 1024**4, "TIB": 1024**4, "TB": 1000**4,
          "P": 1024**5, "PIB": 1024**5, "PB": 1000**5}


def parse_size(text: str) -> int | None:
    """``2832MiB``, ``50GiB`` or ``1.2P`` as bytes."""
    m = _SIZE_RE.search(text or "")
    if not m or not m.group(1):
        return None
    unit = (m.group(2) or "").upper()
    return int(float(m.group(1)) * _UNITS.get(unit, 1))


def _count(text: str) -> int | None:
    m = re.fullmatch(r"([\d.]+)([KM]?)", text.strip())
    if not m:
        return None
    return int(float(m.group(1)) * {"": 1, "K": 1000, "M": 1_000_000}[m.group(2)])


def parse_diskusage_report(text: str) -> list[dict[str, Any]]:
    """The Alliance's ``diskusage_report`` table.

    Each row is a filesystem line such as::

        /home (user hallett)      2832MiB/  50GiB       36K/ 500K
        /scratch/hallett (...)                           Unable to retrieve quota
        /project (project def-lab-ab)  101GiB/ 931GiB   301K/ 500K
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(/\S*)\s+\(([^)]*)\)\s*(.*)$", line)
        if not m:
            continue
        path, owner, rest = m.group(1), m.group(2), m.group(3)
        row: dict[str, Any] = {"path": path, "owner": owner, "used": None, "quota": None,
                               "files": None, "files_quota": None, "note": ""}
        if "unable" in rest.lower() or not rest.strip():
            row["note"] = rest.strip() or "no quota information"
        else:
            sizes = re.findall(r"([\d.]+\s*[KMGTP]i?B)", rest)
            if len(sizes) >= 2:
                row["used"], row["quota"] = parse_size(sizes[0]), parse_size(sizes[1])
            counts = re.findall(r"(\d+[KM]?)\s*/\s*(\d+[KM]?)(?![\d.]*\s*[KMGTP]i?B)", rest)
            if counts:
                files, files_quota = counts[-1]
                row["files"], row["files_quota"] = _count(files), _count(files_quota)
        rows.append(row)
    return rows


def parse_df(text: str) -> list[dict[str, Any]]:
    """Rows of ``df -P`` (POSIX format: 1K blocks)."""
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            rows.append({
                "filesystem": parts[0],
                "size": int(parts[1]) * 1024,
                "used": int(parts[2]) * 1024,
                "available": int(parts[3]) * 1024,
                "mounted_on": parts[5],
            })
        except ValueError:
            continue
    return rows


def parse_sshare(text: str) -> list[dict[str, str]]:
    """Rows of ``sshare -P -n -o Account,User,RawShares,NormShares,RawUsage,EffectvUsage,FairShare``."""
    return _split(text, ("account", "user", "raw_shares", "norm_shares", "raw_usage",
                         "effective_usage", "fairshare"))


def parse_user_usage(text: str) -> list[dict[str, Any]]:
    """Core-hours and GPU-hours per user from ``sacct -a -P -n -X --format=USAGE_FORMAT``.

    One row per job in the period; summed here per user, largest first.
    """
    totals: dict[str, dict[str, float]] = {}
    for row in _split(text, tuple(f.lower() for f in USAGE_FIELDS)):
        user = row["user"] or "(unknown)"
        try:
            cpus = int(row["alloccpus"] or 0)
            seconds = int(row["elapsedraw"] or 0)
        except ValueError:
            continue
        gpus = 0
        m = re.search(r"gres/gpu(?::[^=,]*)?=(\d+)", row["alloctres"])
        if m:
            gpus = int(m.group(1))
        t = totals.setdefault(user, {"jobs": 0, "core_hours": 0.0, "gpu_hours": 0.0})
        t["jobs"] += 1
        t["core_hours"] += cpus * seconds / 3600
        t["gpu_hours"] += gpus * seconds / 3600
    return [{"user": u, **v} for u, v in sorted(totals.items(), key=lambda kv: -kv[1]["core_hours"])]
