"""
Purpose: ``murmurent cluster``: send work to a Slurm cluster, watch it, bring
         results back, move files, and report storage and processor use.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-12
Input:   The command line; the lab's ``policy/clusters.yaml``; the member's
         ``hosts.yaml``; job cards under ``~/.murmurent/runs/``.
Output:  Text in the terminal. The logic is in ``core/cluster.py``.

Guide: ``docs/cluster.md``.
"""

from __future__ import annotations

import datetime as _dt
import os
import shlex
from pathlib import Path

import click

from ..core import cluster as _cl
from ..core import cluster_policy as _cp
from ..core import run_cards as _cards


def _cluster_or_fail(name: str) -> _cp.Cluster:
    try:
        return _cl.find_cluster(name)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc


def _client_or_fail(name: str) -> _cl.ClusterClient:
    cluster = _cluster_or_fail(name)
    try:
        return _cl.ClusterClient(cluster)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc


def _default_cluster() -> str:
    policy = _cl.known_clusters()
    names = policy.names()
    if len(names) == 1:
        return names[0]
    if not names:
        raise click.ClickException(
            "the lab's policy names no cluster. The PI adds one in policy/clusters.yaml "
            "of the lab records repository (templates/clusters.yaml is an example)."
        )
    raise click.ClickException(f"name the cluster with --cluster: {', '.join(names)}")


def _resolve(name: str | None) -> str:
    return name or _default_cluster()


def _card_or_fail(key: str) -> _cards.JobCard:
    card = _cards.find_card(key)
    if card is None or not card.requested.get("cluster"):
        raise click.ClickException(f"no cluster job matches {key!r}. List them: murmurent cluster jobs")
    return card


@click.group("cluster", invoke_without_command=True)
@click.pass_context
def cluster_group(ctx: click.Context) -> None:
    """Send work to a compute cluster and bring the results back."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# -- setup ------------------------------------------------------------------------


@cluster_group.command("list")
def cluster_list() -> None:
    """The clusters the lab's policy names, and whether you have a login for each."""
    policy = _cl.known_clusters()
    if not policy.clusters:
        click.echo("The lab's policy names no cluster. See templates/clusters.yaml.")
    from ..core import hosts as _hosts

    rows = _hosts.read()
    for name in policy.names():
        cluster = policy.clusters[name]
        host = rows.get(name)
        login = f"login {host.ssh_host}" if host is not None and host.is_remote() else "no login recorded (murmurent cluster add)"
        click.echo(f"{name}: {cluster.description or cluster.profile}; {login}")
    for problem in policy.problems:
        click.echo(f"problem: {problem}")


@cluster_group.command("policy")
@click.option("--cluster", "name", default=None, help="Which cluster; the only one when unsaid.")
def cluster_policy(name: str | None) -> None:
    """The cluster's settings as murmurent understands them."""
    policy = _cl.known_clusters()
    cluster = _cluster_or_fail(_resolve(name))
    for line in _cp.describe_cluster(cluster):
        click.echo(line)
    click.echo("read from: " + (", ".join(policy.sources) or "built-in profile only"))
    for problem in policy.problems:
        click.echo(f"problem: {problem}")


@cluster_group.command("add")
@click.argument("name")
@click.option("--ssh-host", required=True, help="login@address, or an alias from ~/.ssh/config.")
@click.option("--user", default="", help="Your login on the cluster, when the address does not say.")
def cluster_add(name: str, ssh_host: str, user: str) -> None:
    """Record your own login for a cluster the lab's policy names."""
    cluster = _cluster_or_fail(name)
    path = _cl.register_connection(cluster, ssh_host, user)
    click.echo(f"Recorded {ssh_host} as your login for {name} in {path}.")
    click.echo(f"Check it: murmurent cluster test --cluster {name}")


@cluster_group.command("test")
@click.option("--cluster", "name", default=None)
def cluster_test(name: str | None) -> None:
    """Log in, and check that you may charge the lab's account."""
    client = _client_or_fail(_resolve(name))
    ok, where = client.probe()
    if not ok:
        raise click.ClickException(f"could not log in to {client.cluster.name}: {where}")
    click.echo(f"Logged in to {client.cluster.name} as {client.user} (login node {where}).")
    ok, why = client.check_access()
    click.echo(("Access: " if ok else "No access: ") + why)
    click.echo(f"Jobs are staged under {client.work_root}.")
    if not ok:
        raise SystemExit(1)


# -- jobs -------------------------------------------------------------------------


@cluster_group.command("submit", context_settings={"ignore_unknown_options": True})
@click.option("--cluster", "name", default=None)
@click.option("--name", "job_name", default="", help="A short name for the job.")
@click.option("--cores", default=1, show_default=True, type=int)
@click.option("--gpus", default=0, show_default=True, type=int)
@click.option("--memory", default="", help="Total memory, e.g. 32G. The cluster's default when unsaid.")
@click.option("--time", "time_limit", default="", help="Time limit: 2h, 3d, or 1-12:00:00. The cluster's default when unsaid.")
@click.option("--out", default="", help="Where results land here. Default: the experiment's append_only folder.")
@click.option("--stage", default="", help="The folder copied to the cluster. Default: the current folder.")
@click.option("--script", default="", help="Submit this job script as it is, instead of building one.")
@click.option("--watch/--no-watch", default=True, show_default=True, help="Start a watcher in tmux.")
@click.option("--no-notify", is_flag=True, default=False, help="Do not post to the project's Slack channel.")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cluster_submit(name: str | None, job_name: str, cores: int, gpus: int, memory: str,
                   time_limit: str, out: str, stage: str, script: str, watch: bool,
                   no_notify: bool, command: tuple[str, ...]) -> None:
    """Copy this folder to the cluster and run COMMAND there as a job.

    Put your command after two dashes: murmurent cluster submit --cores 8 -- python run_all.py
    """
    if not command and not script:
        raise click.ClickException("say what to run after --, or give --script")
    client = _client_or_fail(_resolve(name))
    options = _cl.SubmitOptions(
        command=list(command), folder=Path.cwd(), name=job_name, cores=cores, gpus=gpus,
        memory=memory, time=time_limit, out=out, stage=stage, script=script, notify=not no_notify,
    )
    try:
        card = _cl.submit(client, options)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc
    req = card.requested
    click.echo(f"Submitted {card.name} to {client.cluster.name} as job {req['slurm_job_id']} "
               f"(partition {req['partition']}, account {req['account'] or 'default'}, "
               f"{cores} core{'s' if cores != 1 else ''}"
               + (f", {gpus} GPU{'s' if gpus != 1 else ''}" if gpus else "")
               + f", time limit {req['time']}).")
    click.echo(f"  Staged in: {req['remote_dir']}")
    click.echo(f"  Results will come back to: {card.out}")
    click.echo(f"  Check on it: murmurent cluster status {card.id}")
    if watch:
        _start_watcher(card)
    else:
        click.echo(f"  Watch it later: murmurent cluster watch {card.id}")


def _start_watcher(card: _cards.JobCard) -> None:
    from ..core import run_launcher as _rl

    session = f"cluster-{card.id}"
    runner = _rl.TmuxRunner()
    try:
        runner.start(session, card.name, Path(card.workdir),
                     f"murmurent cluster watch {shlex.quote(card.id)}")
    except Exception as exc:  # noqa: BLE001
        click.echo(f"  Could not start the watcher in tmux ({exc}). Run it yourself: "
                   f"murmurent cluster watch {card.id}")
        return
    card.tmux_session = session
    _cards.write_card(card)
    click.echo(f"  A watcher polls the scheduler every {max(1, _cl.MIN_POLL_SECONDS // 60)}+ min in "
               f"tmux session {session}; it copies the results back and posts to Slack when the job ends.")


@cluster_group.command("watch")
@click.argument("job")
@click.option("--once", is_flag=True, default=False, help="Ask once and stop.")
def cluster_watch(job: str, once: bool) -> None:
    """Poll the scheduler until the job ends, then bring the results back."""
    card = _card_or_fail(job)
    client = _client_or_fail(str(card.requested["cluster"]))
    if card.state not in _cards.ACTIVE_STATES:
        click.echo(f"{card.name} already ended: {card.state}.")
        return
    if once:
        _cl.refresh(client, card)
    else:
        _cl.watch(client, card)
    for line in _status_lines(card):
        click.echo(line)


@cluster_group.command("status")
@click.argument("job", required=False)
@click.option("--all", "show_all", is_flag=True, default=False, help="Include jobs that ended long ago.")
def cluster_status(job: str | None, show_all: bool) -> None:
    """Where a job stands (asks the scheduler), or every cluster job when no JOB is named."""
    if job:
        card = _card_or_fail(job)
        if card.state in _cards.ACTIVE_STATES:
            client = _client_or_fail(str(card.requested["cluster"]))
            _cl.refresh(client, card)
        for line in _status_lines(card):
            click.echo(line)
        return
    cards = _cl.cluster_cards()
    if not show_all:
        cutoff = _cards.now_local() - _dt.timedelta(days=14)
        cards = [c for c in cards if c.state in _cards.ACTIVE_STATES
                 or (_cards.from_iso(c.ended_at or c.created_at) or cutoff) >= cutoff]
    if not cards:
        click.echo("No cluster jobs" + ("." if show_all else " in the last 14 days."))
        return
    for card in sorted(cards, key=lambda c: c.created_at or c.id):
        click.echo(_status_lines(card)[0])


def _status_lines(card: _cards.JobCard) -> list[str]:
    req = card.requested
    head = f"{card.name} [{card.id}] on {req.get('cluster')} (job {req.get('slurm_job_id')}): {card.state}"
    if card.state == _cards.STATE_WAITING and card.waiting_for:
        head += f", waiting for {card.waiting_for}"
    elif card.state == _cards.STATE_RUNNING:
        head += f" for {_cards.format_duration(card.duration_seconds())}"
    elif card.ended_at:
        head += f" after {req.get('elapsed') or _cards.format_duration(card.duration_seconds())}"
        if card.exit_code is not None:
            head += f", exit code {card.exit_code}"
    lines = [head]
    for note in card.notes[-3:]:
        lines.append(f"    {note['text']}")
    if card.state not in _cards.ACTIVE_STATES and Path(card.log).is_file():
        lines.append(f"    Log: {card.log}")
    return lines


@cluster_group.command("jobs")
@click.option("--all", "show_all", is_flag=True, default=False)
@click.pass_context
def cluster_jobs(ctx: click.Context, show_all: bool) -> None:
    """Every cluster job, newest last."""
    ctx.invoke(cluster_status, job=None, show_all=show_all)


@cluster_group.command("cancel")
@click.argument("job")
def cluster_cancel(job: str) -> None:
    """Ask the scheduler to stop a job."""
    card = _card_or_fail(job)
    client = _client_or_fail(str(card.requested["cluster"]))
    try:
        client.cancel(int(card.requested["slurm_job_id"]))
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"could not cancel: {exc}") from exc
    card.add_note("Cancelled on request.")
    _cards.write_card(card)
    click.echo(f"Asked {client.cluster.name} to cancel job {card.requested['slurm_job_id']}. "
               f"Its final state: murmurent cluster status {card.id}")


@cluster_group.command("fetch")
@click.argument("job")
@click.option("--to", "destination", default="", help="Where to put the results. Default: the card's output folder.")
def cluster_fetch(job: str, destination: str) -> None:
    """Copy a job's results and log back here, leaving existing files untouched."""
    card = _card_or_fail(job)
    client = _client_or_fail(str(card.requested["cluster"]))
    remote_dir = str(card.requested.get("remote_dir", ""))
    target = destination or card.out
    try:
        client.pull(f"{remote_dir}/out", target)
        client.pull(f"{remote_dir}/slurm-{card.requested['slurm_job_id']}.out", Path(card.log).parent,
                    contents=False)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc
    card.add_note(f"Results copied to {target} on request.")
    _cards.write_card(card)
    click.echo(f"Copied the results of {card.name} to {target}.")


# -- files ------------------------------------------------------------------------


@cluster_group.command("push")
@click.argument("local", type=click.Path(exists=True))
@click.argument("remote_path")
@click.option("--cluster", "name", default=None)
def cluster_push(local: str, remote_path: str, name: str | None) -> None:
    """Copy a file or folder to the cluster. REMOTE_PATH may use {scratch}, {project}, {home}."""
    client = _client_or_fail(_resolve(name))
    target = _cp.expand_path(remote_path, user=client.user, account=client.cluster.account,
                             group=client.cluster.group, tiers=client.tiers)
    try:
        client.push(local, target)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Copied {local} to {client.cluster.name}:{target}.")


@cluster_group.command("pull")
@click.argument("remote_path")
@click.argument("local", type=click.Path())
@click.option("--cluster", "name", default=None)
@click.option("--overwrite", is_flag=True, default=False, help="Replace files already here. Refused under append_only.")
def cluster_pull(remote_path: str, local: str, name: str | None, overwrite: bool) -> None:
    """Copy a file or folder from the cluster. Existing files here are left as they are."""
    client = _client_or_fail(_resolve(name))
    source = _cp.expand_path(remote_path, user=client.user, account=client.cluster.account,
                             group=client.cluster.group, tiers=client.tiers)
    if overwrite:
        from ..core.lab_vm import is_under_raw

        try:
            from ..core.lab_vm import append_only_root

            under_append = Path(local).expanduser().resolve().is_relative_to(append_only_root().resolve())
        except Exception:  # noqa: BLE001
            under_append = False
        if under_append or is_under_raw(local):
            raise click.ClickException("--overwrite is refused under the governed data folders")
    try:
        client.pull(source, local, ignore_existing=not overwrite)
    except _cl.ClusterError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Copied {client.cluster.name}:{source} to {local}.")


# -- reports ----------------------------------------------------------------------


@cluster_group.command("usage")
@click.option("--cluster", "name", default=None)
def cluster_usage(name: str | None) -> None:
    """Your storage on each tier, with what each tier is for, and your jobs."""
    client = _client_or_fail(_resolve(name))
    report = client.usage()
    click.echo(f"Storage on {report.cluster} for {report.user}:")
    for t in report.tiers:
        click.echo("  " + t.line())
        click.echo(f"      {t.tier.describe()}")
        if t.tier.notes:
            click.echo(f"      {t.tier.notes}")
    for warning in report.warnings():
        click.echo(f"  Warning: {warning}")
    if report.queued:
        click.echo("Your jobs now:")
        for j in report.queued:
            click.echo(f"  {j['id']} {j['name']}: {j['state'].lower()} for {j['elapsed']} "
                       f"on {j['partition']} ({j['cpus']} cores{', ' + j['gres'] if j['gres'] not in ('', 'N/A') else ''})")
    else:
        click.echo("You have no job queued or running.")
    if report.recent:
        click.echo("Ended in the last 7 days:")
        for j in report.recent[-10:]:
            click.echo(f"  {j['jobid']} {j['jobname']}: {j['state'].lower()} after {j['elapsed']}")
    for problem in report.problems:
        click.echo(f"problem: {problem}")


@cluster_group.command("scan")
@click.option("--cluster", "name", default=None)
@click.option("--days", default=30, show_default=True, type=int, help="Period for the usage table.")
def cluster_scan(name: str | None, days: int) -> None:
    """The lab's partition as a whole: nodes, queue, members, who used what. Report only."""
    client = _client_or_fail(_resolve(name))
    report = client.scan(days=days)
    click.echo(f"Partition {report.partition} on {report.cluster}:")
    for n in report.nodes:
        gpus = _gpu_text(n["gres"])
        click.echo(f"  {n['nodes']}: {n['state']}, {n['cpus_allocated']} of {n['cpus_total']} cores in use, "
                   f"{n['memory_mb'] // 1024} GB memory{gpus}")
    if report.queue:
        click.echo(f"Queue ({len(report.queue)} jobs):")
        by_user: dict[str, list[dict[str, str]]] = {}
        for j in report.queue:
            by_user.setdefault(j["user"], []).append(j)
        for user, jobs in sorted(by_user.items()):
            running = sum(1 for j in jobs if j["state"] == "RUNNING")
            cores = sum(int(j["cpus"]) for j in jobs if j["cpus"].isdigit())
            gpus = sum(_cl._slurm.gpu_count(j["gres"]) for j in jobs)
            click.echo(f"  {user}: {running} running, {len(jobs) - running} waiting; "
                       f"{cores} cores" + (f", {gpus} GPUs" if gpus else ""))
    else:
        click.echo("Queue: empty.")
    if report.usage:
        click.echo(f"Use in the last {days} days (core-hours, GPU-hours, jobs):")
        for u in report.usage:
            click.echo(f"  {u['user']:<12} {u['core_hours']:>9.0f} {u['gpu_hours']:>7.0f} {u['jobs']:>5}")
    if report.members:
        idle = report.idle_members()
        click.echo(f"Members of the account ({len(report.members)}): " + ", ".join(report.members))
        if report.usage and idle:
            click.echo(f"  ran nothing in the last {days} days: " + ", ".join(idle))
    for s in report.shares:
        line = f"Fair share {s['account']}: {s['raw_shares']} shares, raw usage {s['raw_usage']}"
        if s["fairshare"]:
            line += f", fair-share factor {s['fairshare']}"
        click.echo(line)
    if report.group_storage:
        click.echo("Group storage:")
        for t in report.group_storage:
            click.echo("  " + t.line())
    for problem in report.problems:
        click.echo(f"problem: {problem}")


def _gpu_text(gres: str) -> str:
    n = _cl._slurm.gpu_count(gres)
    return f", {n} GPUs ({gres})" if n else ""
