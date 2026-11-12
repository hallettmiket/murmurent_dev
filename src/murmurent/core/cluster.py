"""
Purpose: Send work to a Slurm cluster over SSH, watch it, bring the results
         back, move files, and report storage and processor use. Every call
         crosses the SSH boundary through :class:`core.remote.Remote`, so it is
         audited like any other remote operation.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-12
Input:   A :class:`~murmurent.core.cluster_policy.Cluster` (the lab's policy)
         and the member's own connection row in ``hosts.yaml``.
Output:  Job cards under ``~/.murmurent/runs/`` (the same store ``murmurent
         jobs`` reads), files staged to and from the cluster, and reports.

How a job travels
-----------------
1. The experiment folder is copied with ``rsync`` to a staging directory on
   the cluster's scratch tier: ``<work_root>/<project>/<name>-<card id>/stage``.
2. A job script is written beside it and handed to ``sbatch``. The script runs
   the command inside ``stage`` with ``$MURMURENT_OUT`` pointing at ``../out``.
3. The watcher asks ``sacct`` every few minutes. When the job ends, ``out`` and
   the scheduler log come back to the caller's machine, into the output folder
   named at submission (by default the experiment's output folder, the
   ``append_only`` or ``modifiable`` tier it chose; core/output_tier.py),
   with ``--ignore-existing`` so nothing there is ever overwritten.
4. One line goes to the project's Slack channel, through the same route
   ``murmurent run`` uses.

Nothing here deletes on the cluster, and nothing writes to a ``nearline``
tier: those are decisions for a person.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import cluster_policy as _cp
from . import hosts as _hosts
from . import remote as _remote
from . import run_cards as _cards
from . import output_tier as _tier
from . import slurm as _slurm

SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15"]
RSYNC_TIMEOUT = 6 * 3600
MIN_POLL_SECONDS = 60


class ClusterError(RuntimeError):
    """Something the person has to fix before the cluster can be used."""


# ---------------------------------------------------------------------------
# Finding the cluster and the member's connection
# ---------------------------------------------------------------------------


def known_clusters(env: dict[str, str] | None = None) -> _cp.ClusterPolicy:
    return _cp.load_clusters(env)


def find_cluster(name: str, env: dict[str, str] | None = None) -> _cp.Cluster:
    policy = known_clusters(env)
    cluster = policy.get(name)
    if cluster is None:
        known = ", ".join(policy.names()) or "none"
        raise ClusterError(
            f"no cluster named {name!r} in the lab's policy (known: {known}). "
            "The PI adds one in policy/clusters.yaml of the lab records repository; "
            "templates/clusters.yaml is a commented example."
        )
    return cluster


def connection(cluster: _cp.Cluster, env: dict[str, str] | None = None) -> _hosts.Host:
    """The member's own SSH row for this cluster, else one built from the policy."""
    rows = _hosts.read(env)
    host = rows.get(cluster.name)
    if host is not None and host.is_remote():
        return host
    if not cluster.ssh_host:
        raise ClusterError(
            f"no connection for cluster {cluster.name!r}: run "
            f"murmurent cluster add {cluster.name} --ssh-host <login>@<address>"
        )
    return _hosts.Host(name=cluster.name, kind="ssh", ssh_host=cluster.ssh_host,
                       description=f"cluster {cluster.name} (from the lab's policy)")


def register_connection(cluster: _cp.Cluster, ssh_host: str, user: str = "",
                        env: dict[str, str] | None = None) -> Path:
    """Record the member's login for a cluster in their own hosts.yaml."""
    if "@" in ssh_host and not user:
        user = ssh_host.split("@", 1)[0]
    host = _hosts.Host(name=cluster.name, kind="ssh", ssh_host=ssh_host, remote_user=user,
                       description=cluster.description or f"cluster {cluster.name}")
    rows = _hosts.read(env)
    rows[cluster.name] = host
    return _hosts.write(rows, env)


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------


@dataclass
class TierUsage:
    tier: _cp.StorageTier
    path: str
    used: int | None = None
    quota: int | None = None
    files: int | None = None
    files_quota: int | None = None
    note: str = ""

    def line(self) -> str:
        if self.used is None and not self.note:
            return f"{self.tier.name}: {self.path}: no figure available"
        if self.used is None:
            return f"{self.tier.name}: {self.path}: {self.note}"
        text = f"{self.tier.name}: {self.path}: {_cards.format_size(self.used)}"
        if self.quota:
            pct = 100 * self.used / self.quota
            text += f" of {_cards.format_size(self.quota)} ({pct:.0f}%)"
        if self.files is not None and self.files_quota:
            text += f", {self.files:,} of {self.files_quota:,} files"
        return text


@dataclass
class UsageReport:
    cluster: str
    user: str
    tiers: list[TierUsage] = field(default_factory=list)
    queued: list[dict[str, str]] = field(default_factory=list)
    recent: list[dict[str, str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def warnings(self) -> list[str]:
        """Plain sentences about anything close to a limit."""
        out = []
        for t in self.tiers:
            if t.used is not None and t.quota:
                share = t.used / t.quota
                if share >= 0.9:
                    out.append(f"{t.tier.name} is {share:.0%} full; a job writing there will fail soon.")
            if t.files is not None and t.files_quota and t.files / t.files_quota >= 0.9:
                out.append(f"{t.tier.name} holds {t.files / t.files_quota:.0%} of its allowed "
                           "number of files; many small files count as much as large ones.")
        return out


@dataclass
class ScanReport:
    cluster: str
    partition: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    queue: list[dict[str, str]] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    usage: list[dict[str, Any]] = field(default_factory=list)
    shares: list[dict[str, str]] = field(default_factory=list)
    group_storage: list[TierUsage] = field(default_factory=list)
    days: int = 30
    problems: list[str] = field(default_factory=list)

    def idle_members(self) -> list[str]:
        seen = {u["user"] for u in self.usage}
        return [m for m in self.members if m not in seen]


class ClusterClient:
    """One cluster, one member, one SSH connection."""

    def __init__(self, cluster: _cp.Cluster, host: _hosts.Host | None = None,
                 env: dict[str, str] | None = None):
        self.cluster = cluster
        self.env = env
        self.host = host or connection(cluster, env)
        self.remote = _remote.Remote(self.host)
        self._user = self.host.remote_user or ""
        self._tiers: dict[str, str] | None = None

    # -- basics ---------------------------------------------------------------

    def run(self, command: str, *, timeout: int = 60, check: bool = True) -> _remote.RemoteResult:
        return self.remote.run(command, timeout=timeout, check=check)

    @property
    def user(self) -> str:
        if not self._user:
            self._user = self.run("whoami", timeout=20).stdout.strip()
        return self._user

    @property
    def tiers(self) -> dict[str, str]:
        if self._tiers is None:
            self._tiers = _cp.expanded_tiers(self.cluster, user=self.user)
        return self._tiers

    @property
    def work_root(self) -> str:
        return _cp.expand_path(self.cluster.work_root, user=self.user,
                               account=self.cluster.account,
                               group=self.cluster.group or self.cluster.account,
                               tiers=self.tiers)

    def probe(self) -> tuple[bool, str]:
        result = self.run("echo ok && hostname", timeout=20, check=False)
        if not result.ok:
            return False, (result.stderr.strip().splitlines() or ["no answer"])[-1]
        return True, result.stdout.strip().splitlines()[-1]

    def check_access(self) -> tuple[bool, str]:
        """Whether this member may charge the lab's account on this cluster."""
        if not self.cluster.account:
            return True, "no account is required by the policy"
        result = self.run(
            f"sacctmgr -n -P show assoc user={shlex.quote(self.user)} format=account,user,partition",
            timeout=30, check=False)
        if not result.ok:
            return False, "could not ask the scheduler about your accounts: " + result.stderr.strip()
        accounts = _slurm.accounts_of(_slurm.parse_associations(result.stdout), self.user)
        if _slurm.has_account(accounts, self.cluster.account):
            return True, f"you may charge {self.cluster.account}"
        who = f" (the group {self.cluster.group})" if self.cluster.group else ""
        return False, (
            f"your login {self.user} is not in the lab's account {self.cluster.account}{who} "
            f"on {self.cluster.name}. Ask the PI to add you on the Alliance's website; "
            f"accounts you do have: {', '.join(sorted(accounts)) or 'none'}."
        )

    # -- files ----------------------------------------------------------------

    def _rsync(self, source: str, destination: str, *, ignore_existing: bool = False,
               excludes: tuple[str, ...] = ()) -> None:
        argv = ["rsync", "-az", "--partial", "-e", "ssh " + " ".join(SSH_OPTIONS)]
        if ignore_existing:
            argv.append("--ignore-existing")
        for pattern in excludes:
            argv += ["--exclude", pattern]
        argv += [source, destination]
        start = _dt.datetime.now()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=RSYNC_TIMEOUT,
                                  check=False)
        except subprocess.TimeoutExpired as exc:
            raise ClusterError(f"copy timed out: {source} -> {destination}") from exc
        _remote._append_audit(host=self.host, command=" ".join(argv[:1] + argv[-2:]),
                              returncode=proc.returncode,
                              duration_ms=int((_dt.datetime.now() - start).total_seconds() * 1000))
        if proc.returncode != 0:
            raise ClusterError(f"copy failed ({proc.returncode}): {proc.stderr.strip()}")

    def remote_spec(self, path: str) -> str:
        return f"{self.host.ssh_host}:{path}"

    def push(self, local: str | Path, remote_path: str, *, excludes: tuple[str, ...] = ()) -> None:
        """Copy a local file or folder to the cluster. A folder copies its contents."""
        local = Path(local).expanduser()
        if not local.exists():
            raise ClusterError(f"nothing to copy: {local} does not exist")
        self.refuse_nearline(remote_path)
        self.run(f"mkdir -p {shlex.quote(remote_path)}", timeout=30)
        source = str(local) + ("/" if local.is_dir() else "")
        self._rsync(source, self.remote_spec(remote_path), excludes=excludes)

    def pull(self, remote_path: str, local: str | Path, *, ignore_existing: bool = True,
             contents: bool = True) -> None:
        """Copy a cluster folder's contents (or, with ``contents=False``, a file or the
        folder itself) into ``local``. By default nothing already here is overwritten."""
        local = Path(local).expanduser()
        local.mkdir(parents=True, exist_ok=True)
        source = remote_path.rstrip("/") + ("/" if contents else "")
        self._rsync(self.remote_spec(source), str(local) + "/", ignore_existing=ignore_existing)

    def refuse_nearline(self, remote_path: str) -> None:
        tier = self.cluster.tier("nearline")
        if tier is None:
            return
        root = self.tiers.get("nearline", "")
        if root and remote_path.startswith(root.rstrip("/")):
            raise ClusterError(
                "murmurent does not write to the nearline (tape archive) tier. "
                "A person copies finished work there, with the PI's agreement."
            )

    def exists(self, remote_path: str) -> bool:
        return self.run(f"test -e {shlex.quote(remote_path)}", timeout=20, check=False).ok

    # -- jobs -----------------------------------------------------------------

    def submit_script(self, script_text: str, remote_dir: str, *, script_name: str = "job.sh") -> int:
        """Write a job script into ``remote_dir`` on the cluster and submit it."""
        path = f"{remote_dir.rstrip('/')}/{script_name}"
        self.run(f"mkdir -p {shlex.quote(remote_dir)} && cat > {shlex.quote(path)} <<'MURMURENT_EOF'\n"
                 f"{script_text}MURMURENT_EOF", timeout=60)
        result = self.run(f"cd {shlex.quote(remote_dir)} && sbatch {shlex.quote(path)}", timeout=60,
                          check=False)
        job_id = _slurm.submitted_job_id(result.stdout)
        if not result.ok or job_id is None:
            raise ClusterError("the scheduler refused the job: " +
                               (result.stderr.strip() or result.stdout.strip()))
        return job_id

    def job_state(self, job_id: int) -> dict[str, str] | None:
        result = self.run(f"sacct -P -n -j {int(job_id)} --format={_slurm.SACCT_FORMAT}",
                          timeout=60, check=False)
        if not result.ok:
            return None
        return _slurm.job_summary(_slurm.parse_sacct(result.stdout), job_id)

    def cancel(self, job_id: int) -> None:
        self.run(f"scancel {int(job_id)}", timeout=30)

    def queue(self, *, user: str = "", partition: str = "") -> list[dict[str, str]]:
        parts = ["squeue", "-h", "-o", shlex.quote(_slurm.SQUEUE_FORMAT)]
        if user:
            parts += ["-u", shlex.quote(user)]
        if partition:
            parts += ["-p", shlex.quote(partition)]
        result = self.run(" ".join(parts), timeout=60, check=False)
        return _slurm.parse_squeue(result.stdout) if result.ok else []

    def recent_jobs(self, user: str, days: int = 7) -> list[dict[str, str]]:
        result = self.run(
            f"sacct -P -n -X -u {shlex.quote(user)} -S now-{int(days)}days --format={_slurm.SACCT_FORMAT}",
            timeout=60, check=False)
        return _slurm.parse_sacct(result.stdout) if result.ok else []

    # -- reports --------------------------------------------------------------

    def usage(self) -> UsageReport:
        """This member's storage on each tier, and their jobs."""
        report = UsageReport(cluster=self.cluster.name, user=self.user)
        quota_rows: list[dict[str, Any]] = []
        if self.cluster.usage_command:
            result = self.run(self.cluster.usage_command, timeout=90, check=False)
            if result.ok:
                quota_rows = _slurm.parse_diskusage_report(result.stdout)
            else:
                report.problems.append(f"{self.cluster.usage_command} failed: {result.stderr.strip()[:200]}")
        # A tier that does not exist for this member (no nearline yet, say) makes
        # df exit non-zero; the rows it did print are still wanted.
        df_result = self.run("df -P " + " ".join(shlex.quote(p) for p in self.tiers.values())
                             + " 2>/dev/null; true", timeout=60, check=False)
        df_rows = _slurm.parse_df(df_result.stdout)

        for tier in self.cluster.tiers:
            path = self.tiers[tier.name]
            usage = TierUsage(tier=tier, path=path)
            for row in quota_rows:
                if _same_tier(row["path"], path, tier.name):
                    usage.used, usage.quota = row["used"], row["quota"]
                    usage.files, usage.files_quota = row["files"], row["files_quota"]
                    usage.note = row["note"]
                    break
            if usage.used is None:
                # No per-person quota (scratch, say): show the whole filesystem.
                best = _mount_for(df_rows, path)
                if best is not None:
                    usage.used, usage.quota = best["used"], best["size"]
                    usage.note = "whole filesystem, shared by everyone"
            report.tiers.append(usage)
        report.queued = self.queue(user=self.user)
        report.recent = [r for r in self.recent_jobs(self.user, 7)
                         if r.get("state", "").split()[0] not in ("RUNNING", "PENDING")]
        return report

    def scan(self, days: int = 30) -> ScanReport:
        """The lab's partition as a whole: nodes, queue, members, who used what."""
        partition = self.cluster.partition_cpu or self.cluster.partition_gpu
        account = self.cluster.account
        report = ScanReport(cluster=self.cluster.name, partition=partition, days=days)

        # -N: one row per node, so the PI sees each node's cores and GPUs rather
        # than one line for the pair.
        result = self.run(f"sinfo -h -N -p {shlex.quote(partition)} -o {shlex.quote(_slurm.SINFO_FORMAT)}",
                          timeout=60, check=False)
        if result.ok:
            report.nodes = _slurm.parse_sinfo(result.stdout)
        else:
            report.problems.append("sinfo failed: " + result.stderr.strip()[:200])

        report.queue = self.queue(partition=partition)

        if account:
            result = self.run(
                f"sacctmgr -n -P show assoc account={shlex.quote(account)}_cpu,{shlex.quote(account)}_gpu,"
                f"{shlex.quote(account)} format=account,user,partition", timeout=60, check=False)
            if result.ok:
                report.members = sorted({r["user"] for r in _slurm.parse_associations(result.stdout)
                                         if r.get("user")})
            result = self.run(
                f"sacct -a -P -n -X -A {shlex.quote(account)}_cpu,{shlex.quote(account)}_gpu,"
                f"{shlex.quote(account)} -S now-{int(days)}days --format={_slurm.USAGE_FORMAT}",
                timeout=120, check=False)
            if result.ok:
                report.usage = _slurm.parse_user_usage(result.stdout)
            else:
                report.problems.append("the scheduler would not list other members' jobs: "
                                       + result.stderr.strip()[:200])
            result = self.run(
                f"sshare -P -n -A {shlex.quote(account)}_cpu,{shlex.quote(account)}_gpu "
                "-o Account,User,RawShares,NormShares,RawUsage,EffectvUsage,FairShare",
                timeout=60, check=False)
            if result.ok:
                report.shares = [r for r in _slurm.parse_sshare(result.stdout) if not r["user"]]

        usage = self.usage()
        report.group_storage = [t for t in usage.tiers if t.tier.name in ("project", "nearline")]
        report.problems += usage.problems
        return report


def _same_tier(reported: str, path: str, tier_name: str) -> bool:
    reported = reported.rstrip("/")
    path = path.rstrip("/")
    if reported == path or path.startswith(reported + "/") or reported.startswith(path + "/"):
        return True
    return reported.split("/")[1:2] == [tier_name] if "/" in reported else False


def _mount_for(df_rows: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    best = None
    for row in df_rows:
        mount = row["mounted_on"].rstrip("/") or "/"
        if path == mount or path.startswith(mount + "/") or mount == "/":
            if best is None or len(mount) > len(best["mounted_on"].rstrip("/")):
                best = row
    return best


# ---------------------------------------------------------------------------
# Submitting a job and recording its card
# ---------------------------------------------------------------------------


@dataclass
class SubmitOptions:
    command: list[str]
    folder: Path
    name: str = ""
    cores: int = 1
    gpus: int = 0
    memory: str = ""
    time: str = ""
    out: str = ""
    stage: str = ""
    script: str = ""
    notify: bool = True
    output_tier: str = ""   # "" = the experiment's own choice
    excludes: tuple[str, ...] = (".git", "__pycache__", ".venv", "*.pyc")


def _safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text[:40] or "job"


def submit(client: ClusterClient, options: SubmitOptions,
           *, moment: _dt.datetime | None = None) -> _cards.JobCard:
    """Stage the folder, submit the job, and write its card. Returns the card."""
    from . import run_launcher as _rl

    cluster = client.cluster
    ok, why = client.check_access()
    if not ok:
        raise ClusterError(why)

    moment = moment or _cards.now_local()
    job_id = _cards.new_job_id(moment)
    name = _safe_name(options.name or (options.command[0] if options.command else "job"))
    project, marker = _rl.project_for_folder(options.folder)
    tier = (_tier.normalise_tier(options.output_tier)
            or _tier.resolve_output_tier(options.folder, marker).tier)
    remote_dir = f"{client.work_root}/{project or 'jobs'}/{name}-{job_id}"
    stage_dir = f"{remote_dir}/stage"
    out_dir = f"{remote_dir}/out"
    partition = cluster.partition_for(options.gpus)
    time_limit = options.time or cluster.default_time

    stage_source = Path(options.stage).expanduser() if options.stage else options.folder
    client.push(stage_source, stage_dir, excludes=options.excludes)

    if options.script:
        script_text = Path(options.script).expanduser().read_text(encoding="utf-8")
    else:
        script_text = _slurm.sbatch_script(
            options.command, name=name, account=cluster.account, partition=partition,
            time=time_limit, cores=options.cores, memory=options.memory, gpus=options.gpus,
            gpu_type=cluster.gpu_type, log=f"{remote_dir}/slurm-%j.out",
            modules=cluster.modules, setup=cluster.setup, workdir=stage_dir, out_dir=out_dir,
        )
    slurm_id = client.submit_script(script_text, remote_dir)

    local_out = options.out
    if not local_out:
        local_out = _default_out(project, options.folder, tier)
    runs = _cards.runs_dir()
    card = _cards.JobCard(
        id=job_id,
        name=name,
        user=os.environ.get("USER", "") or client.user,
        host=cluster.name,
        command=list(options.command) if options.command else [options.script],
        workdir=str(options.folder),
        log=str(runs / f"{job_id}.slurm.out"),
        watch="",
        out=local_out,
        project=project,
        requested={
            "cluster": cluster.name,
            "slurm_job_id": slurm_id,
            "remote_dir": remote_dir,
            "partition": partition,
            "account": cluster.account,
            "time": time_limit,
            "cores": options.cores,
            "gpus": options.gpus,
            "memory": options.memory,
            "login": client.user,
            "output_tier": tier,
        },
        cores=options.cores,
        gpus=list(range(options.gpus)),
        state=_cards.STATE_WAITING,
        waiting_for="the scheduler to start it",
        created_at=_cards.to_iso(moment),
    )
    target = _rl.resolve_notify_target(options.folder)
    card.notify = {"enabled": bool(options.notify), "channel": target.channel,
                   "slack_group": target.slack_group, "reason": target.reason}
    card.add_note(f"Submitted to {cluster.name} as Slurm job {slurm_id} on partition {partition}, "
                  f"account {cluster.account or 'default'}, time limit {time_limit}.", moment)
    _cards.write_card(card)
    return card


def _default_out(project: str, folder: Path, tier: str = "") -> str:
    """The experiment's output folder in its tier when the project is known,
    else ``cluster_out`` beside the code."""
    try:
        if project:
            return str(_tier.experiment_output_dir(project, folder.name, tier))
    except Exception:  # noqa: BLE001
        pass
    return str(folder / "cluster_out")


# ---------------------------------------------------------------------------
# Watching
# ---------------------------------------------------------------------------


def _exit_code(text: str) -> int | None:
    m = re.match(r"(\d+)", text or "")
    return int(m.group(1)) if m else None


def _slurm_time_to_iso(text: str) -> str | None:
    if not text or text in ("Unknown", "None"):
        return None
    try:
        # Slurm prints the cluster's local time without a zone; treat it as this
        # machine's, which is right when both sit in the same province.
        return _cards.to_iso(_dt.datetime.fromisoformat(text).astimezone())
    except ValueError:
        return None


def refresh(client: ClusterClient, card: _cards.JobCard, *,
            moment: _dt.datetime | None = None) -> bool:
    """Ask the scheduler about the card's job once. Returns True when the job has ended.

    On an end, pulls the results and the log, records why, and posts the notice.
    """
    from . import run_launcher as _rl

    moment = moment or _cards.now_local()
    slurm_id = int(card.requested.get("slurm_job_id", 0))
    row = client.job_state(slurm_id)
    if row is None:
        return False
    state = _slurm.card_state(row.get("state", ""))
    card.started_at = card.started_at or _slurm_time_to_iso(row.get("start", ""))
    if state == "running" and card.state == _cards.STATE_WAITING:
        card.state = _cards.STATE_RUNNING
        card.waiting_for = ""
        card.add_note(f"Running on {row.get('nodelist') or 'a compute node'}.", moment)
    elif state == "waiting":
        card.waiting_for = row.get("reason") or "the scheduler to start it"
    if state not in ("finished", "failed", "stopped"):
        _cards.write_card(card)
        return False

    card.ended_at = _slurm_time_to_iso(row.get("end", "")) or _cards.to_iso(moment)
    card.exit_code = _exit_code(row.get("exitcode", ""))
    card.state = {"finished": _cards.STATE_FINISHED, "failed": _cards.STATE_FAILED,
                  "stopped": _cards.STATE_STOPPED}[state]
    card.requested["slurm_state"] = row.get("state", "")
    card.requested["max_rss"] = row.get("maxrss", "")
    card.requested["elapsed"] = row.get("elapsed", "")
    why = _slurm.why_it_ended(row.get("state", ""), row.get("exitcode", ""))
    if why:
        card.add_note(why, moment)

    remote_dir = str(card.requested.get("remote_dir", ""))
    if remote_dir:
        try:
            client.pull(f"{remote_dir}/slurm-{slurm_id}.out", Path(card.log).parent, contents=False)
            pulled_log = Path(card.log).parent / f"slurm-{slurm_id}.out"
            if pulled_log.is_file():
                card.log = str(pulled_log)
        except ClusterError as exc:
            card.add_note(f"The scheduler log could not be copied back: {exc}", moment)
        if card.out and client.exists(f"{remote_dir}/out"):
            overwrite = card.requested.get("output_tier") == "modifiable"
            try:
                client.pull(f"{remote_dir}/out", card.out, ignore_existing=not overwrite)
                card.add_note(f"Results copied to {card.out} "
                              + ("(modifiable tier: files of the same name replaced)."
                                 if overwrite else "(existing files left untouched)."), moment)
            except ClusterError as exc:
                card.add_note(f"Results could not be copied back: {exc}", moment)
    _cards.write_card(card)
    try:
        _rl.post_notice(card)
    except Exception as exc:  # noqa: BLE001 - Slack never fails a job
        card.notify["skipped"] = f"posting failed: {exc.__class__.__name__}"
    _cards.write_card(card)
    return True


def watch(client: ClusterClient, card: _cards.JobCard, *, poll_seconds: int | None = None,
          sleep: Callable[[float], None] = time.sleep, max_polls: int | None = None) -> _cards.JobCard:
    """Poll until the job ends. Never asks the scheduler more than once a minute."""
    interval = max(MIN_POLL_SECONDS, poll_seconds or client.cluster.poll_minutes * 60)
    card.supervisor_pid = os.getpid()
    _cards.write_card(card)
    polls = 0
    while True:
        if refresh(client, card):
            return card
        polls += 1
        if max_polls is not None and polls >= max_polls:
            return card
        sleep(interval)


def cluster_cards(env: dict[str, str] | None = None) -> list[_cards.JobCard]:
    """Every card that belongs to a cluster job."""
    return [c for c in _cards.list_cards(env) if c.requested.get("cluster")]
