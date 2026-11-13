"""Tests for the machines registry: the two-layer merge, the person's set, the
three profiles behind one interface, an unreachable machine, and the JSON the
commands print. No network: ssh is answered by a fake runner, and the cluster
profile's Slurm calls by the same kind of fake the cluster tests use."""

from __future__ import annotations

import json
import subprocess

import pytest
import yaml
from click.testing import CliRunner

from murmurent.core import cluster_policy as _cp
from murmurent.core import hosts as _hosts
from murmurent.core import machine_policy as _mp
from murmurent.core import remote as _remote

UPTIME = " 11:02:17 up 41 days,  2:11, 3 users,  load average: 6.42, 5.90, 5.11\n"
NVIDIA = "0, 92, 20480, 24576\n1, 0, 10, 24576\n"
WHO = "mhallet  pts/0  2026-11-13 09:00 (10.0.0.2)\nfry      pts/1  2026-11-13 10:12 (10.0.0.3)\n"
PS = "root 0.0\nmhallet 310.5\nmhallet 95.0\nfry 0.3\n"
DF = ("Filesystem 1024-blocks Used Available Capacity Mounted on\n"
      "/dev/sdb1 20000000000 15000000000 5000000000 75% /data/lab_vm\n"
      "/dev/sda2 500000000 100000000 400000000 20% /home\n")


def server_answer(command: str) -> str:
    """What biodatsci would print for the one combined script of each probe."""
    if command == "hostname":
        return "biodatsci\n"
    if "==nproc" in command:
        return ("==nproc\n64\n==uptime\n" + UPTIME + "==gpu\n" + NVIDIA + "==who\n" + WHO
                + "==ps\n" + PS + "==end\n")
    if "==df" in command:
        return "==df\n" + DF + "==end\n"
    return ""


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "murmurent_home"))
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setenv("MURMURENT_REMOTE_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "nowhere"))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    clusters = tmp_path / "clusters.yaml"
    clusters.write_text(yaml.safe_dump({"clusters": {"dusky": {
        "ssh_host": "dusky.example.ca", "description": "the cluster", "account": "ctb-lab",
        "group": "ctb-lab", "partition_cpu": "biosharc", "partition_gpu": "biosharc",
    }}}))
    monkeypatch.setenv(_cp.CLUSTERS_ENV, str(clusters))
    machines = tmp_path / "machines.yaml"
    machines.write_text(yaml.safe_dump({"machines": {
        "biodatsci": {"profile": "ssh_server", "description": "the lab server",
                      "ssh_host": "biodatsci.example.ca", "data_root": "/data/lab_vm",
                      "tiers": {"home": {"path": "/home", "purpose": "home folders"},
                                "append_only": {"path": "/data/lab_vm/append_only", "quota": "none"}}},
        "dusky": {"profile": "alliance", "cluster": "dusky"},
    }}))
    monkeypatch.setenv(_mp.MACHINES_ENV, str(machines))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def fake_runner(answers: dict[str, str | tuple[int, str, str]]):
    calls: list[tuple[str, str]] = []

    def run(host, command, timeout):
        calls.append((host.name, command))
        answer = answers.get(host.name)
        if answer is None:
            return 255, "", "ssh: connect to host unknown: Connection refused"
        if isinstance(answer, tuple):
            return answer
        return 0, server_answer(command), ""

    run.calls = calls  # type: ignore[attr-defined]
    return run


# ---------------------------------------------------------------------------
# The two layers
# ---------------------------------------------------------------------------


def test_profile_fills_what_the_lab_file_leaves_out(world):
    policy = _mp.load_machines()
    assert policy.names() == ["laptop", "biodatsci", "dusky"]
    assert not policy.problems
    server = policy.get("biodatsci")
    names = [t.name for t in server.tiers]
    # the eight lab folders from the profile, plus the tier the lab added
    assert names[:8] == [n for n, _ in _mp.LAB_FOLDERS] and "home" in names
    assert {t.name: t.path for t in server.tiers}["immutable"] == "/data/lab_vm/immutable"
    assert {t.name: t.quota for t in server.tiers}["append_only"] == "none"
    cluster = policy.get("dusky")
    assert cluster.profile == "alliance" and cluster.cluster == "dusky"
    # address, description and tiers come from clusters.yaml
    assert cluster.ssh_host == "dusky.example.ca" and cluster.description == "the cluster"
    assert [t.name for t in cluster.tiers][:2] == ["home", "scratch"]
    laptop = policy.get("laptop")
    assert laptop.is_local() and [t.name for t in laptop.tiers] == ["home", "data"]


def test_bad_values_are_reported_and_the_table_still_stands(world, tmp_path):
    (tmp_path / "machines.yaml").write_text(yaml.safe_dump({"machines": {
        "odd": {"profile": "mainframe"},
        "bare": {"profile": "ssh_server"},
        "lost": {"profile": "alliance", "cluster": "nowhere"},
        "text": "not a mapping",
    }}))
    policy = _mp.load_machines()
    assert policy.get("odd").profile == "ssh_server"
    assert any("unknown profile" in p for p in policy.problems)
    assert any("needs a data_root" in p for p in policy.problems)
    assert any("no cluster named 'nowhere'" in p for p in policy.problems)
    assert any("must be a mapping" in p for p in policy.problems)
    assert "text" not in policy.machines


def test_template_is_valid(world, tmp_path, monkeypatch):
    from murmurent.core.commons import commons_root

    template = commons_root() / "templates" / "machines.yaml"
    monkeypatch.setenv(_mp.MACHINES_ENV, str(template))
    policy = _mp.load_machines()
    assert policy.names() == ["laptop", "biodatsci", "dusky"]
    assert policy.problems == []
    assert policy.get("biodatsci").data_root == "/data/lab_vm"
    assert policy.get("dusky").cluster == "dusky"


# ---------------------------------------------------------------------------
# The person's set
# ---------------------------------------------------------------------------


def test_set_is_this_computer_plus_machines_with_a_login(world):
    members = {m.name: m for m in _mp.person_set()}
    assert members["laptop"].set_up and members["laptop"].login
    assert not members["biodatsci"].set_up and members["biodatsci"].login == ""
    hint = _mp.setup_hint(members["biodatsci"].machine)
    assert hint.startswith("not set up: run murmurent machine add biodatsci --ssh-host <login>@biodatsci.example.ca")

    _mp.register_login(members["biodatsci"].machine, "mhallet@biodatsci.example.ca")
    _mp.register_login(members["dusky"].machine, "hallett@dusky.example.ca")
    row = _hosts.read()["biodatsci"]
    assert row.kind == "ssh" and row.remote_user == "mhallet"
    members = {m.name: m for m in _mp.person_set()}
    assert all(m.set_up for m in members.values())
    assert members["dusky"].login == "hallett@dusky.example.ca"


def test_a_cluster_login_recorded_under_the_cluster_name_counts(world, tmp_path):
    (tmp_path / "machines.yaml").write_text(yaml.safe_dump({"machines": {
        "the_cluster": {"profile": "alliance", "cluster": "dusky"},
    }}))
    policy = _mp.load_machines()
    _hosts.add(_hosts.Host(name="dusky", kind="ssh", ssh_host="hallett@dusky.example.ca"))
    members = {m.name: m for m in _mp.person_set(policy)}
    assert members["the_cluster"].set_up


# ---------------------------------------------------------------------------
# The profile interface
# ---------------------------------------------------------------------------


def test_every_profile_answers_the_three_questions(world):
    members = {m.name: m for m in _mp.person_set()}
    for member in members.values():
        probe = _mp.probe_for(member)
        for question in ("status", "load", "usage"):
            assert callable(getattr(probe, question))
    assert set(_mp.PROBES) == set(_mp.PROFILE_NAMES)


def test_laptop_answers_without_ssh(world):
    member = {m.name: m for m in _mp.person_set()}["laptop"]
    probe = _mp.probe_for(member, runner=fake_runner({}))
    status = probe.status()
    assert status.reachable and status.checked_at
    load = probe.load()
    assert load.cores_total and load.cores_total > 0 and load.gpus_total == 0 and load.who
    usage = probe.usage()
    by_name = {t.name: t for t in usage.tiers}
    assert by_name["home"].used is not None and by_name["data"].quota
    assert usage.nearest_limit() is not None


def test_ssh_server_reads_uptime_nproc_nvidia_who_and_df(world):
    policy = _mp.load_machines()
    _mp.register_login(policy.get("biodatsci"), "mhallet@biodatsci.example.ca")
    member = {m.name: m for m in _mp.person_set(policy)}["biodatsci"]
    runner = fake_runner({"biodatsci": "answers"})
    probe = _mp.probe_for(member, runner=runner)

    status = probe.status()
    assert status.reachable and status.detail == "biodatsci"

    load = probe.load()
    assert load.reachable and load.problem == ""
    assert (load.cores_busy, load.cores_total) == (6, 64)
    assert (load.gpus_busy, load.gpus_total) == (1, 2)
    assert load.sessions == 2
    assert load.who == ["mhallet (4 cores)", "fry (logged in)"]

    usage = probe.usage()
    by_name = {t.name: t for t in usage.tiers}
    assert by_name["immutable"].used == 15000000000 * 1024 and by_name["immutable"].quota == 20000000000 * 1024
    assert by_name["append_only"].note == "same filesystem as immutable"
    assert by_name["home"].used == 100000000 * 1024 and by_name["home"].note == ""
    assert usage.nearest_limit().name == "immutable"
    # every call went to this machine through the runner, and read only
    assert runner.calls and all(name == "biodatsci" for name, _c in runner.calls)
    assert not any(word in c for _n, c in runner.calls for word in ("rm ", "mv ", "chmod", "truncate"))


def test_parsers():
    assert _mp.parse_uptime_load("load average: 0.52, 0.58, 0.59") == 0.52
    assert _mp.parse_uptime_load("12:00  up 3 days, load averages: 2.10 1.80 1.50") == 2.10
    assert _mp.parse_uptime_load("nothing here") is None
    assert _mp.parse_nvidia_smi(["0, 0, 0, 24576", "1, 0, 4096, 24576", "2, 50, 0, 24576"]) == (2, 3)
    assert _mp.parse_ps_cores(["a 150.0", "a 50.0", "b 0.1", "junk"]) == {"a": 2.0, "b": 0.001}
    assert _mp.describe_people(["b", "a"], {"a": 2.0, "b": 0.001}) == ["a (2 cores)", "b (logged in)"]


@pytest.fixture
def fake_slurm(monkeypatch):
    """The cluster profile talks Slurm through core.remote; answer it from a script."""
    answers = {
        "whoami": "hallett\n",
        "echo ok && hostname": "ok\ndus241\n",
        "sinfo": "dus97|256|2312110|gpu:l40s:4|mix|12/244/0/256\ndus98|256|2312110|gpu:l40s:4|idle|0/256/0/256\n",
        "squeue": ("345600|train|emucaki|ctb-lab_gpu|biosharc|RUNNING|2:10:00|7-00:00:00|1|32|gpu:l40s:2|dus97\n"
                   "345601|qc|fryday|ctb-lab_cpu|biosharc|PENDING|0:00|12:00:00|1|64|N/A|(Priority)\n"),
        "diskusage_report": ("   Description   Space   # of files\n"
                             "  /home (user hallett)      2832MiB/  50GiB          36K/ 500K\n"
                             "  /project (project ctb-lab)       101GiB/ 931GiB         301K/ 500K\n"),
        "df -P": ("Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                  "ic:/export/scratch 32212254720 27917287424 5368709120 84% /scratch\n"),
    }

    def fake_run(argv, **kwargs):
        command = argv[-1]
        if command.startswith("bash -lc "):
            import shlex
            command = shlex.split(command)[2]
        for key, text in answers.items():
            if key in command:
                return subprocess.CompletedProcess(argv, 0, stdout=text, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(_remote.subprocess, "run", fake_run)
    return answers


def test_alliance_delegates_to_the_cluster_code(world, fake_slurm):
    policy = _mp.load_machines()
    _mp.register_login(policy.get("dusky"), "hallett@dusky.example.ca")
    member = {m.name: m for m in _mp.person_set(policy)}["dusky"]
    probe = _mp.probe_for(member)
    assert probe.status().detail == "dus241"
    load = probe.load()
    assert (load.cores_busy, load.cores_total) == (12, 512)
    assert (load.gpus_busy, load.gpus_total) == (2, 8)
    assert load.jobs == 1 and load.sessions == 1
    assert load.who == ["emucaki (32 cores, 2 GPUs)", "fryday (1 waiting)"]
    usage = probe.usage()
    by_name = {t.name: t for t in usage.tiers}
    assert by_name["home"].files == 36_000 and by_name["project"].quota == 931 * 1024**3
    assert usage.nearest_limit().name == "scratch"


# ---------------------------------------------------------------------------
# All at once: not set up, unreachable, and the JSON shape
# ---------------------------------------------------------------------------


def test_ask_all_skips_the_not_set_up_and_reports_the_unreachable(world):
    policy = _mp.load_machines()
    _mp.register_login(policy.get("biodatsci"), "mhallet@biodatsci.example.ca")
    members = _mp.person_set(policy)
    runner = fake_runner({"biodatsci": (255, "", "ssh: connect to host biodatsci.example.ca port 22: Operation timed out")})
    rows = {r.name: r for r in _mp.ask_all(members, "load", runner=runner)}
    assert rows["laptop"].reachable
    assert rows["biodatsci"].set_up and not rows["biodatsci"].reachable
    assert rows["biodatsci"].problem == "unreachable: ssh: connect to host biodatsci.example.ca port 22: Operation timed out"
    assert not rows["dusky"].set_up and rows["dusky"].problem.startswith("not set up: run murmurent machine add dusky")
    # the cluster was never probed: no call went to it
    assert all(name == "biodatsci" for name, _c in runner.calls)
    _mp.remember(list(rows.values()))
    state = _mp.read_state()
    assert state["biodatsci"]["reachable"] is False and "dusky" not in state


def test_a_timeout_is_reported_not_raised(world):
    policy = _mp.load_machines()
    _mp.register_login(policy.get("biodatsci"), "mhallet@biodatsci.example.ca")
    member = {m.name: m for m in _mp.person_set(policy)}["biodatsci"]
    runner = fake_runner({"biodatsci": (124, "", "no answer within 45 seconds")})
    usage = _mp.probe_for(member, runner=runner).usage()
    assert usage.problem == "unreachable: no answer within 45 seconds" and usage.tiers == []


def test_ssh_runner_turns_a_timeout_into_a_row(world, monkeypatch):
    def slow(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1))

    monkeypatch.setattr(_remote.subprocess, "run", slow)
    host = _hosts.Host(name="biodatsci", kind="ssh", ssh_host="mhallet@biodatsci.example.ca")
    code, out, err = _mp.ssh_runner(host, "hostname", 5)
    assert code == 124 and "5 seconds" in err


def test_commands_print_tables_and_json(world, monkeypatch):
    from murmurent.cli import cli

    policy = _mp.load_machines()
    _mp.register_login(policy.get("biodatsci"), "mhallet@biodatsci.example.ca")
    monkeypatch.setattr(_mp, "ssh_runner", fake_runner({"biodatsci": "answers"}))
    runner = CliRunner()

    result = runner.invoke(cli, ["machines"])
    assert result.exit_code == 0, result.output
    assert "biodatsci" in result.output and "reachable (biodatsci)" in result.output
    assert "not set up: run murmurent machine add dusky" in result.output

    result = runner.invoke(cli, ["machines", "--no-check", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    by_name = {m["name"]: m for m in data["machines"]}
    assert by_name["biodatsci"]["reachable"] is True and by_name["biodatsci"]["checked_at"]
    assert by_name["dusky"]["set_up"] is False

    result = runner.invoke(cli, ["machines", "load"])
    assert result.exit_code == 0, result.output
    assert "6 of 64" in result.output and "1 of 2" in result.output and "mhallet (4 cores)" in result.output

    result = runner.invoke(cli, ["machines", "load", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert set(data) == {"machines", "problems"}
    row = {m["name"]: m for m in data["machines"]}["biodatsci"]
    assert set(row) >= {"name", "profile", "set_up", "reachable", "checked_at", "problem",
                        "cores_busy", "cores_total", "gpus_busy", "gpus_total", "jobs", "sessions", "who"}
    assert row["cores_busy"] == 6 and row["gpus_total"] == 2

    result = runner.invoke(cli, ["machines", "usage", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    row = {m["name"]: m for m in data["machines"]}["biodatsci"]
    assert row["nearest_limit"] == {"tier": "immutable", "percent": 75.0}
    tier = {t["name"]: t for t in row["tiers"]}["home"]
    assert set(tier) == {"name", "path", "used", "quota", "files", "files_quota", "note", "percent", "files_percent"}
    assert tier["percent"] == 20.0
    dusky = {m["name"]: m for m in data["machines"]}["dusky"]
    assert dusky["set_up"] is False and dusky["tiers"] == []

    result = runner.invoke(cli, ["machines", "usage"])
    assert result.exit_code == 0, result.output
    assert "nearest its limit" in result.output and "not set up" in result.output


def test_machine_add_and_cluster_add_write_the_same_row(world):
    from murmurent.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["machine", "add", "biodatsci", "--ssh-host", "mhallet@biodatsci.example.ca"])
    assert result.exit_code == 0, result.output
    assert "Recorded mhallet@biodatsci.example.ca as your login for biodatsci" in result.output
    result = runner.invoke(cli, ["cluster", "add", "dusky", "--ssh-host", "hallett@dusky.example.ca"])
    assert result.exit_code == 0, result.output
    assert "Recorded hallett@dusky.example.ca as your login for dusky" in result.output
    assert "murmurent cluster test --cluster dusky" in result.output
    rows = _hosts.read()
    assert rows["biodatsci"].remote_user == "mhallet" and rows["dusky"].remote_user == "hallett"
    result = runner.invoke(cli, ["machine", "add", "nowhere", "--ssh-host", "x@y"])
    assert result.exit_code != 0 and "no machine named 'nowhere'" in result.output
    result = runner.invoke(cli, ["machine", "add", "laptop", "--ssh-host", "x@y"])
    assert result.exit_code != 0 and "needs no login" in result.output
