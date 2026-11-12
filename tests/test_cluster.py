"""Tests for the cluster layer: the policy file, the Slurm parsers, and the client
with SSH and rsync replaced by fakes. The captured text is what Dusky printed on
2026-11-12."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from murmurent.core import cluster as _cl
from murmurent.core import cluster_policy as _cp
from murmurent.core import hosts as _hosts
from murmurent.core import remote as _remote
from murmurent.core import run_cards as _cards
from murmurent.core import slurm as _slurm

SACCT = """345437|murmurent_smoke|COMPLETED|0:0|00:00:01|2026-11-12T08:21:28|2026-11-12T08:21:29|dus97||1G|1|biosharc|ctb-hallett_cpu|00:05:00|None
345437.batch|batch|COMPLETED|0:0|00:00:01|2026-11-12T08:21:28|2026-11-12T08:21:29|dus97|1200K||1|||00:05:00|
345437.extern|extern|COMPLETED|0:0|00:00:01|2026-11-12T08:21:28|2026-11-12T08:21:29|dus97|0||1|||00:05:00|
"""

SACCT_RUNNING = "345500|fit|RUNNING|0:0|01:02:03|2026-11-12T09:00:00|Unknown|dus98||32G|8|biosharc|ctb-hallett_gpu|1-00:00:00|None\n"
SACCT_TIMEOUT = "345501|fit|TIMEOUT|0:0|01:00:05|2026-11-12T09:00:00|2026-11-12T10:00:05|dus98||32G|8|biosharc|ctb-hallett_cpu|01:00:00|None\n"

DISKUSAGE = """                            Description                Space         # of files
                   /home (user hallett)      2832MiB/  50GiB          36K/ 500K
      /scratch/hallett (hallett/hallett)                                     Unable to retrieve quota
      /project (project def-hallett-ab)       101GiB/ 931GiB         301K/ 500K
--
On some clusters, a break down per user may be available by adding the option '--per_user'.
"""

SINFO = "dus[97-98]|256|2312110|gpu:l40s:4|mix|12/500/0/512\n"
SQUEUE = ("345600|train|emucaki|ctb-hallett_gpu|biosharc|RUNNING|2:10:00|7-00:00:00|1|32|gpu:l40s:2|dus97\n"
          "345601|qc|fryday|ctb-hallett_cpu|biosharc|PENDING|0:00|12:00:00|1|64|N/A|(Priority)\n")
ASSOC = "ctb-hallett_cpu|hallett|\nctb-hallett_gpu|hallett|\ndef-hallett-ab_cpu|hallett|\n"
USAGE = ("emucaki|32|7200|cpu=32,gres/gpu=2,gres/gpu:l40s=2,mem=64G,node=1|biosharc\n"
         "emucaki|16|3600|cpu=16,mem=32G,node=1|biosharc\n"
         "fryday|64|1800|cpu=64,mem=128G,node=1|biosharc\n")
DF = ("Filesystem 1024-blocks Used Available Capacity Mounted on\n"
      "10.36.8.8:/home 214748364800 173946175488 40802189312 81% /home\n"
      "ic:/export/scratch 32212254720 27917287424 5368709120 84% /scratch\n")


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def test_profile_fills_what_the_lab_file_leaves_out(tmp_path, monkeypatch):
    path = tmp_path / "clusters.yaml"
    path.write_text(yaml.safe_dump({"clusters": {"dusky": {
        "ssh_host": "dusky.example.ca", "account": "ctb-lab", "partition_cpu": "lab",
        "tiers": {"project": {"notes": "shared quota"}},
    }}}))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "nowhere"))
    monkeypatch.setenv(_cp.CLUSTERS_ENV, str(path))
    policy = _cp.load_clusters()
    assert policy.problems == []
    cluster = policy.get("dusky")
    assert cluster.usage_command == "diskusage_report"
    assert [t.name for t in cluster.tiers] == ["home", "scratch", "project", "nearline", "local"]
    project = cluster.tier("project")
    assert project.path == "/project/{account}" and project.backed_up and project.notes == "shared quota"
    assert cluster.partition_for(gpus=0) == "lab" and cluster.partition_for(gpus=2) == "lab"
    tiers = _cp.expanded_tiers(cluster, user="ann")
    assert tiers["scratch"] == "/scratch/ann" and tiers["project"] == "/project/ctb-lab"
    assert _cp.expand_path(cluster.work_root, user="ann", tiers=tiers) == "/scratch/ann/murmurent"


def test_bad_values_are_reported_and_defaults_kept(tmp_path, monkeypatch):
    path = tmp_path / "clusters.yaml"
    path.write_text(yaml.safe_dump({"clusters": {"c": {
        "profile": "nonsense", "poll_minutes": 0, "modules": 5,
        "tiers": {"scratch": {"purged": "yes"}, "extra": {"purpose": "no path"}},
    }}}))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "nowhere"))
    monkeypatch.setenv(_cp.CLUSTERS_ENV, str(path))
    policy = _cp.load_clusters()
    cluster = policy.get("c")
    assert cluster.profile == "alliance" and cluster.poll_minutes == 2 and cluster.modules == ()
    assert cluster.tier("scratch").purged is True
    assert cluster.tier("extra") is None
    joined = "\n".join(policy.problems)
    for word in ("profile", "poll_minutes", "modules", "purged", "needs a path"):
        assert word in joined


def test_template_is_valid(monkeypatch, tmp_path):
    template = Path(__file__).resolve().parents[1] / "templates" / "clusters.yaml"
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "nowhere"))
    monkeypatch.setenv(_cp.CLUSTERS_ENV, str(template))
    policy = _cp.load_clusters()
    assert policy.problems == []
    dusky = policy.get("dusky")
    assert dusky.account == "ctb-hallett" and dusky.partition_gpu == "biosharc"
    assert any("storage" in line for line in _cp.describe_cluster(dusky))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def test_sbatch_script_carries_the_labs_account_and_partition():
    text = _slurm.sbatch_script(["python", "run all.py"], name="fit", account="ctb-lab",
                                partition="lab", time="2h", cores=8, memory="32G", gpus=1,
                                gpu_type="l40s", workdir="/scratch/ann/x/stage",
                                out_dir="/scratch/ann/x/out", modules=("python/3.11",))
    assert "#SBATCH --account=ctb-lab" in text
    assert "#SBATCH --partition=lab" in text
    assert "#SBATCH --time=02:00:00" in text
    assert "#SBATCH --gpus-per-node=l40s:1" in text
    assert "module load python/3.11" in text
    assert "python 'run all.py'" in text
    assert "export MURMURENT_OUT=/scratch/ann/x/out" in text


@pytest.mark.parametrize("given,expected", [("90m", "01:30:00"), ("3d", "3-00:00:00"),
                                            ("1-12:00:00", "1-12:00:00"), ("00:05:00", "00:05:00")])
def test_time_forms(given, expected):
    assert _slurm.slurm_time(given) == expected


def test_sacct_rows_and_states():
    rows = _slurm.parse_sacct(SACCT)
    job = _slurm.job_summary(rows, 345437)
    assert job["state"] == "COMPLETED" and job["nodelist"] == "dus97" and job["account"] == "ctb-hallett_cpu"
    assert _slurm.card_state("COMPLETED") == "finished"
    assert _slurm.card_state("CANCELLED by 123") == "stopped"
    assert _slurm.card_state("OUT_OF_MEMORY") == "failed"
    assert _slurm.card_state("PENDING") == "waiting"
    assert "longer --time" in _slurm.why_it_ended("TIMEOUT")
    assert _slurm.submitted_job_id("Submitted batch job 345437\nsbatch: changed account") == 345437


def test_diskusage_report_rows():
    rows = {r["path"]: r for r in _slurm.parse_diskusage_report(DISKUSAGE)}
    home = rows["/home"]
    assert home["used"] == 2832 * 1024**2 and home["quota"] == 50 * 1024**3
    assert home["files"] == 36_000 and home["files_quota"] == 500_000
    assert rows["/scratch/hallett"]["used"] is None and "Unable" in rows["/scratch/hallett"]["note"]
    assert rows["/project"]["quota"] == 931 * 1024**3 and rows["/project"]["files"] == 301_000


def test_sinfo_squeue_assoc_usage_df():
    node = _slurm.parse_sinfo(SINFO)[0]
    assert node["cpus_total"] == 512 and node["cpus_allocated"] == 12 and _slurm.gpu_count(node["gres"]) == 4
    queue = _slurm.parse_squeue(SQUEUE)
    assert queue[0]["user"] == "emucaki" and _slurm.gpu_count(queue[0]["gres"]) == 2
    assert queue[1]["reason"] == "(Priority)"
    accounts = _slurm.accounts_of(_slurm.parse_associations(ASSOC), "hallett")
    assert _slurm.has_account(accounts, "ctb-hallett") and not _slurm.has_account(accounts, "ctb-other")
    usage = _slurm.parse_user_usage(USAGE)
    assert usage[0]["user"] == "emucaki" and usage[0]["core_hours"] == 80 and usage[0]["gpu_hours"] == 4
    assert usage[1]["user"] == "fryday" and usage[1]["jobs"] == 1
    df = _slurm.parse_df(DF)
    assert df[1]["mounted_on"] == "/scratch" and df[1]["size"] == 32212254720 * 1024


# ---------------------------------------------------------------------------
# Client, with SSH and rsync faked
# ---------------------------------------------------------------------------


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "murmurent_home"))
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setenv("MURMURENT_REMOTE_AUDIT_LOG", str(tmp_path / "audit.log"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "nowhere"))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    policy = tmp_path / "clusters.yaml"
    policy.write_text(yaml.safe_dump({"clusters": {"dusky": {
        "ssh_host": "dusky.example.ca", "account": "ctb-hallett", "group": "ctb-hallett",
        "partition_cpu": "biosharc", "partition_gpu": "biosharc", "gpu_type": "l40s",
    }}}))
    monkeypatch.setenv(_cp.CLUSTERS_ENV, str(policy))
    return tmp_path


@pytest.fixture
def fake_cluster(monkeypatch):
    """Answer SSH commands from a script; record every argv, including rsync."""
    calls: list[list[str]] = []
    answers: dict[str, str] = {
        "whoami": "hallett\n",
        "sacctmgr -n -P show assoc user=hallett": ASSOC,
        "sbatch": "Submitted batch job 345437\nsbatch: changed CPU job account from ctb-hallett to ctb-hallett_cpu\n",
        "sacct -P -n -j 345437": SACCT,
        "diskusage_report": DISKUSAGE,
        "df -P": DF,
        "squeue": SQUEUE,
        "sacct -P -n -X -u": "",
        "sinfo": SINFO,
        "sacctmgr -n -P show assoc account=": "ctb-hallett_cpu|hallett|\nctb-hallett_cpu|emucaki|\nctb-hallett_gpu|fryday|\nctb-hallett_cpu|zz_idle|\n",
        "sacct -a -P -n -X -A": USAGE,
        "sshare": "ctb-hallett_cpu||256|0.015|4017175796|0.43|0.035\nctb-hallett_cpu|hallett|1|0.03|0|0|0.17\n",
    }

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if argv[0] == "rsync":
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        command = argv[-1]
        if command.startswith("bash -lc "):
            import shlex
            command = shlex.split(command)[2]
        for key, text in answers.items():
            if key in command:
                return subprocess.CompletedProcess(argv, 0, stdout=text, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(_remote.subprocess, "run", fake_run)
    monkeypatch.setattr(_cl.subprocess, "run", fake_run)
    return calls, answers


def test_register_connection_and_access_check(world, fake_cluster):
    cluster = _cl.find_cluster("dusky")
    _cl.register_connection(cluster, "hallett@dusky.sharcnet.ca")
    host = _hosts.read()["dusky"]
    assert host.kind == "ssh" and host.ssh_host == "hallett@dusky.sharcnet.ca" and host.remote_user == "hallett"
    client = _cl.ClusterClient(cluster)
    ok, why = client.check_access()
    assert ok and "ctb-hallett" in why
    assert client.tiers["scratch"] == "/scratch/hallett"
    assert client.work_root == "/scratch/hallett/murmurent"


def test_member_without_the_account_is_refused(world, fake_cluster):
    calls, answers = fake_cluster
    answers["sacctmgr -n -P show assoc user=hallett"] = "def-hallett-ab_cpu|hallett|\n"
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    ok, why = client.check_access()
    assert not ok and "ctb-hallett" in why and "Ask the PI" in why
    exp = world / "exp"
    exp.mkdir()
    with pytest.raises(_cl.ClusterError):
        _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp))


def test_submit_stages_the_folder_and_writes_a_card(world, fake_cluster):
    calls, _answers = fake_cluster
    exp = world / "1_fit"
    exp.mkdir()
    (exp / "run_all.py").write_text("print(1)\n")
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    card = _cl.submit(client, _cl.SubmitOptions(command=["python", "run_all.py"], folder=exp,
                                                 name="fit", cores=8, gpus=1, time="2h",
                                                 out=str(world / "results")))
    assert card.host == "dusky" and card.state == _cards.STATE_WAITING
    assert card.requested["slurm_job_id"] == 345437
    assert card.requested["partition"] == "biosharc" and card.requested["account"] == "ctb-hallett"
    assert card.requested["remote_dir"].startswith("/scratch/hallett/murmurent/jobs/fit-")
    assert card.cores == 8 and card.gpus == [0]
    rsyncs = [c for c in calls if c[0] == "rsync"]
    assert len(rsyncs) == 1 and rsyncs[0][-2] == str(exp) + "/" and "--exclude" in rsyncs[0]
    assert rsyncs[0][-1] == f"dusky.example.ca:{card.requested['remote_dir']}/stage"
    script_call = next(c[-1] for c in calls if "MURMURENT_EOF" in c[-1])
    assert "#SBATCH --account=ctb-hallett" in script_call and "--gpus-per-node=l40s:1" in script_call
    assert _cards.find_card(card.id) is not None
    # The card belongs to the cluster, so the local liveness check says nothing about it.
    assert _cards.supervisor_alive(card) is None


def test_refresh_pulls_results_and_marks_the_end(world, fake_cluster):
    calls, answers = fake_cluster
    exp = world / "1_fit"
    exp.mkdir()
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    out = world / "results"
    card = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp, out=str(out)))
    answers["sacct -P -n -j 345437"] = SACCT_RUNNING.replace("345500", "345437")
    assert _cl.refresh(client, card) is False
    assert card.state == _cards.STATE_RUNNING and card.started_at
    answers["sacct -P -n -j 345437"] = SACCT
    del calls[:]
    assert _cl.refresh(client, card) is True
    assert card.state == _cards.STATE_FINISHED and card.exit_code == 0
    pulls = [c for c in calls if c[0] == "rsync"]
    assert any(c[-2].endswith("/out/") and c[-1] == str(out) + "/" and "--ignore-existing" in c for c in pulls)
    assert any(c[-2].endswith("slurm-345437.out") for c in pulls)
    assert card.requested["slurm_state"] == "COMPLETED"


def test_refresh_explains_a_timeout(world, fake_cluster):
    calls, answers = fake_cluster
    exp = world / "e"
    exp.mkdir()
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    card = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp, out=str(world / "r")))
    answers["sacct -P -n -j 345437"] = SACCT_TIMEOUT.replace("345501", "345437")
    assert _cl.refresh(client, card) is True
    assert card.state == _cards.STATE_FAILED
    assert any("longer --time" in n["text"] for n in card.notes)


def test_watch_polls_no_faster_than_once_a_minute(world, fake_cluster):
    calls, answers = fake_cluster
    exp = world / "e"
    exp.mkdir()
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    card = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp, out=str(world / "r")))
    answers["sacct -P -n -j 345437"] = SACCT_RUNNING.replace("345500", "345437")
    naps: list[float] = []
    _cl.watch(client, card, poll_seconds=5, sleep=naps.append, max_polls=3)
    assert naps == [60, 60]


def test_usage_report_names_each_tier(world, fake_cluster):
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    report = client.usage()
    by_name = {t.tier.name: t for t in report.tiers}
    assert by_name["home"].used == 2832 * 1024**2 and by_name["home"].quota == 50 * 1024**3
    assert by_name["project"].files == 301_000
    # scratch has no quota, so the whole filesystem's figure is used with a note
    assert by_name["scratch"].used == 27917287424 * 1024 and "shared" in by_name["scratch"].note
    assert "backed up" in by_name["home"].line() or "backed up" in by_name["home"].tier.describe()
    assert report.queued[0]["user"] == "emucaki"


def test_scan_reports_nodes_queue_members_and_idle(world, fake_cluster):
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    report = client.scan(days=30)
    assert report.partition == "biosharc" and report.nodes[0]["cpus_total"] == 512
    assert {j["user"] for j in report.queue} == {"emucaki", "fryday"}
    assert report.members == ["emucaki", "fryday", "hallett", "zz_idle"]
    assert report.idle_members() == ["hallett", "zz_idle"]
    assert report.shares[0]["raw_shares"] == "256"
    assert [t.tier.name for t in report.group_storage] == ["project", "nearline"]


def test_push_refuses_the_nearline_tier(world, fake_cluster):
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    (world / "f.txt").write_text("x")
    with pytest.raises(_cl.ClusterError, match="nearline"):
        client.push(world / "f.txt", "/nearline/ctb-hallett/f.txt")


def test_submit_sends_results_to_the_experiment_tier(world, fake_cluster, monkeypatch):
    """An experiment that chose ``modifiable`` gets its results there, and the
    watcher is allowed to replace files of the same name when it copies back."""
    repo = world / "proj"
    exp = repo / "exp" / "1_build"
    exp.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("name: proj\n")
    (exp / "notebook.md").write_text("---\nexperiment: 1_build\noutput_tier: modifiable\n---\n")
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    card = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp))
    assert card.requested["output_tier"] == "modifiable"
    assert card.out == str(world / "data" / "modifiable" / "proj" / "1_build")

    calls, _answers = fake_cluster
    _cl.refresh(client, card)
    pulls = [c for c in calls if c[0] == "rsync" and c[-2].endswith("/out/")]
    assert pulls and "--ignore-existing" not in pulls[-1]
    assert any("replaced" in n["text"] for n in card.notes)


def test_submit_defaults_to_append_only_and_never_overwrites(world, fake_cluster):
    repo = world / "proj"
    exp = repo / "exp" / "1_fit"
    exp.mkdir(parents=True)
    (repo / ".murmurent.yaml").write_text("name: proj\n")
    client = _cl.ClusterClient(_cl.find_cluster("dusky"))
    card = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp))
    assert card.requested["output_tier"] == "append_only"
    assert card.out == str(world / "data" / "append_only" / "proj" / "1_fit")
    forced = _cl.submit(client, _cl.SubmitOptions(command=["true"], folder=exp, output_tier="modifiable"))
    assert forced.out == str(world / "data" / "modifiable" / "proj" / "1_fit")
