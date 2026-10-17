"""
Purpose: tests for issue #151, step 2, the space table for one project: what
         the scan suggests and why, what it never suggests, the table keeping
         decisions across scans, the ranking, and `murmurent space`.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-16
Input: temporary folders, fake git repositories and fake job cards only. No
       network, no real data root, no real lab records repository.
Output: pass or fail.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import project_unit as pu
from murmurent.core import repo_inventory as inv
from murmurent.core import run_cards as cards
from murmurent.core import space_scan as ss
from murmurent.core import space_table as st
from murmurent.core.millwright_policy import POLICY_ENV, load_policy

MB = 1024 * 1024
DAY = 86400
ME = ss.owner_name(os.getuid())


@pytest.fixture
def world(monkeypatch, tmp_path):
    """A repositories folder, a data root, a lab records folder and a small
    policy (1 MB thresholds), all under tmp_path. Members' logins are set by
    each test through ``logins``; by default the person running the tests is
    the only member."""
    repos = tmp_path / "repos"
    data = tmp_path / "data"
    lab_mgmt = tmp_path / "lab_mgmt"
    home = tmp_path / "mm_home"
    for d in (repos, data / "immutable", data / "append_only", lab_mgmt, home):
        d.mkdir(parents=True)
    policy = tmp_path / "policy.yaml"
    policy.write_text(yaml.safe_dump({
        "temporary_min_age_days": 7, "large_file_in_repo_mb": 1, "compress_min_mb": 1,
        "duplicate_min_mb": 1, "remake_cheap_below_cpu_hours": 10}))
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(data))
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(home))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv(POLICY_ENV, str(policy))
    monkeypatch.setattr(inv, "EXCLUDE_FILE", tmp_path / "exclude.yaml")
    logins = {"set": {ME}, "unknown": []}
    monkeypatch.setattr(ss, "member_logins",
                        lambda _cp: (set(logins["set"]), list(logins["unknown"])))
    return {"repos": repos, "data": data, "home": home, "tmp": tmp_path, "logins": logins}


def git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


def commit(repo: Path, *files: str, when: str | None = None) -> None:
    env = {**os.environ}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(repo), "add", *files], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x",
                    "commit", "-q", "-m", "c"], check=True, env=env)


def write(path: Path, size: int = 0, *, text: str | None = None, age_days: float = 0,
          seed: int = 0) -> Path:
    """A file of ``size`` bytes (distinct content per seed), aged ``age_days``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        path.write_text(text)
    else:
        block = (f"{seed}:{path.name}:".encode() * 64)[:4096]
        with open(path, "wb") as handle:
            for _ in range(size // len(block)):
                handle.write(block)
            handle.write(block[: size % len(block)])
    if age_days:
        then = time.time() - age_days * DAY
        os.utime(path, (then, then))
    return path


def project(world, name: str = "brca", **kw) -> cp.CertProject:
    repo = git_repo(world["repos"] / name)
    (repo / "exp" / "01_align").mkdir(parents=True)
    (world["data"] / "append_only" / name).mkdir(exist_ok=True)
    (world["data"] / "immutable" / name).mkdir(exist_ok=True)
    cp.upsert(name, lab="mh", lead="@tester", member="tester",
              repos=[cp.RepoRef(name=name, role="code", host="local", path=str(repo))], **kw)
    return cp.get(name)


def scan(project_record, **kw) -> st.ScanSummary:
    return ss.scan_project(project_record, options=ss.ScanOptions(**kw))


def by(summary: st.ScanSummary, category: str) -> dict[str, st.Item]:
    return {i.path: i for i in summary.items if i.category == category}


# ---------------------------------------------------------------------------
# 1. What is found, and what is not
# ---------------------------------------------------------------------------


def test_old_temporary_files_are_suggested_and_new_or_committed_ones_are_not(world):
    p = project(world)
    repo = world["repos"] / "brca"
    old = write(repo / "nohup.out", text="log\n", age_days=30)
    write(repo / "fresh.tmp", text="x", age_days=1)
    committed = write(repo / "kept.tmp", text="x")
    commit(repo, "kept.tmp")
    os.utime(committed, (time.time() - 30 * DAY,) * 2)
    checkpoints = world["data"] / "append_only" / "brca" / "01_align" / ".ipynb_checkpoints"
    write(checkpoints / "a-checkpoint.ipynb", text="{}", age_days=30)
    write(checkpoints / "b-checkpoint.ipynb", text="{}", age_days=30)

    found = by(scan(p), st.TEMPORARY)
    assert found[str(old)].suggestion == st.DELETE
    assert str(repo / "fresh.tmp") not in found
    assert str(committed) not in found
    folder = found[str(checkpoints)]
    assert folder.kind == "folder" and folder.n_files == 2


def test_a_large_file_in_a_repository_is_out_of_place_and_says_if_git_tracks_it(world):
    p = project(world)
    repo = world["repos"] / "brca"
    tracked = write(repo / "data" / "counts.rds", 2 * MB)
    commit(repo, "data/counts.rds")
    loose = write(repo / "big.h5", 2 * MB, seed=1)

    found = by(scan(p, checksums=False), st.OUT_OF_PLACE)
    assert found[str(tracked)].suggestion == st.MOVE
    assert "tracked by git" in found[str(tracked)].reason
    assert "tracked by git" not in found[str(loose)].reason
    assert "append_only/brca" in found[str(loose)].reason


def test_large_text_data_is_compressible_except_in_immutable(world):
    p = project(world)
    out = write(world["data"] / "append_only" / "brca" / "01_align" / "reads.fastq", 2 * MB)
    raw = write(world["data"] / "immutable" / "brca" / "reads.fastq", 2 * MB, seed=1)
    small = write(world["data"] / "append_only" / "brca" / "01_align" / "tiny.csv", text="a,b\n")

    found = by(scan(p, checksums=False), st.COMPRESSIBLE)
    assert found[str(out)].suggestion == st.COMPRESS
    assert "gzip" in found[str(out)].reason
    assert str(raw) not in found and str(small) not in found


def test_duplicates_keep_the_protected_copy_and_ignore_hard_links(world):
    p = project(world)
    raw = write(world["data"] / "immutable" / "brca" / "sample.bam", 2 * MB, seed=7)
    copy = world["data"] / "append_only" / "brca" / "01_align" / "sample_copy.bam"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(raw.read_bytes())
    linked = world["data"] / "append_only" / "brca" / "01_align" / "linked.bam"
    os.link(copy, linked)
    write(world["data"] / "append_only" / "brca" / "01_align" / "same_size.bam", 2 * MB, seed=8)

    found = by(scan(p), st.DUPLICATE)
    assert set(found) == {str(copy)} or set(found) == {str(linked)}
    row = next(iter(found.values()))
    assert row.suggestion == st.DELETE and str(raw) in row.reason


def test_past_the_reading_limit_a_match_is_only_a_probable_duplicate(world):
    p = project(world)
    raw = write(world["data"] / "immutable" / "brca" / "big.bam", 3 * MB, seed=5)
    big_copy = world["data"] / "append_only" / "brca" / "01_align" / "big_copy.bam"
    big_copy.parent.mkdir(parents=True)
    big_copy.write_bytes(raw.read_bytes())
    small = write(world["data"] / "append_only" / "brca" / "01_align" / "s.bam", 2 * MB, seed=6)
    small_copy = small.parent / "s_copy.bam"
    small_copy.write_bytes(small.read_bytes())

    candidates = []
    for f in (raw, big_copy, small, small_copy):
        st_ = f.stat()
        kind = ss.ROOT_IMMUTABLE if "immutable" in str(f) else ss.ROOT_APPEND_ONLY
        candidates.append(ss._Candidate(path=str(f), size=st_.st_size, mtime=st_.st_mtime,
                                        owner=ME, root_kind=kind, disk="", dev=st_.st_dev,
                                        ino=st_.st_ino))
    rows = {i.path: i for i in ss.duplicate_items(candidates, retention_blocked=False,
                                                    max_read_bytes=5 * MB)}
    assert rows[str(big_copy)].suggestion == st.ASK_OWNER
    assert "Not confirmed" in rows[str(big_copy)].reason
    assert rows[str(small_copy)].suggestion == st.DELETE or rows[str(small)].suggestion == st.DELETE


def test_no_checksums_means_no_duplicates(world):
    p = project(world)
    a = write(world["data"] / "append_only" / "brca" / "01_align" / "a.bam", 2 * MB, seed=3)
    (a.parent / "b.bam").write_bytes(a.read_bytes())
    summary = scan(p, checksums=False)
    assert not by(summary, st.DUPLICATE)
    assert any("not looked for" in n for n in summary.notes)


def test_files_owned_by_a_non_member_are_grouped_with_their_first_lines(world):
    p = project(world)
    world["logins"]["set"] = {"someone_else"}
    folder = world["data"] / "append_only" / "brca" / "scratch_by_visitor"
    write(folder / "notes.csv", text="gene,score\nTP53,0.9\nBRCA1,0.8\nMORE,1\n")
    write(folder / "more.csv", text="x\n")

    found = by(scan(p, checksums=False), st.UNATTRIBUTED)
    row = found[str(folder)]
    assert row.owner == ME and row.n_files == 2 and row.suggestion == st.ASK_OWNER
    assert row.peek.splitlines() == ["gene,score", "TP53,0.9", "BRCA1,0.8"]


def test_a_clinical_project_never_reads_inside_a_file(world):
    p = project(world, sensitivity="clinical")
    world["logins"]["set"] = {"someone_else"}
    write(world["data"] / "append_only" / "brca" / "01_align" / "ids.csv", text="patient,1\n")
    rows = by(scan(p, checksums=False), st.UNATTRIBUTED)
    assert rows and all(r.peek == "" for r in rows.values())


def test_with_no_member_login_known_nothing_is_called_unattributed(world):
    p = project(world)
    world["logins"].update(set=set(), unknown=["tester"])
    write(world["data"] / "append_only" / "brca" / "01_align" / "x.csv", text="x\n")
    summary = scan(p, checksums=False)
    assert not by(summary, st.UNATTRIBUTED)
    assert any(g.kind == "members" for g in summary.sop_gaps)


def test_a_folder_the_project_only_reads_is_never_walked(world):
    shared = world["data"] / "append_only" / "brca" / "shared_cohort"
    p = project(world, reads_from=[str(shared)])
    write(shared / "huge.fastq", 2 * MB, age_days=30)
    write(shared / "nohup.out", text="x", age_days=30)
    summary = scan(p, checksums=False)
    assert not [i for i in summary.items if str(shared) in i.path]


def test_a_keep_until_date_turns_every_delete_into_keep(world):
    future = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    p = project(world, retain_until=future)
    write(world["repos"] / "brca" / "nohup.out", text="x", age_days=30)
    rows = by(scan(p, checksums=False), st.TEMPORARY)
    row = rows[str(world["repos"] / "brca" / "nohup.out")]
    assert row.suggestion == st.KEEP and future in row.reason


def test_files_listed_in_ready_to_delete_are_rows(world):
    p = project(world)
    old = write(world["data"] / "append_only" / "brca" / "01_align" / "counts_1.csv", text="1\n")
    raw = write(world["data"] / "immutable" / "brca" / "old_run.txt", text="1\n")
    listing = world["repos"] / "brca" / "src" / "ready_to_delete.md"
    write(listing, text=("# Ready to delete\n\n- `01_align/counts_1.csv` superseded by _2\n"
                         f"- `{raw}`\n- `01_align/already_gone.csv`\n"))
    found = by(scan(p, checksums=False), st.LISTED)
    assert found[str(old)].suggestion == st.DELETE
    assert found[str(raw)].suggestion == st.ASK_OWNER
    assert len(found) == 2


def test_data_folders_that_match_no_experiment_are_out_of_place(world):
    p = project(world)
    write(world["data"] / "append_only" / "brca" / "01_align" / "a.txt", text="a")
    stray = world["data"] / "append_only" / "brca" / "misc_stuff"
    write(stray / "b.txt", text="b")
    loose = write(world["data"] / "append_only" / "brca" / "loose.txt", text="c")
    found = by(scan(p, checksums=False), st.OUT_OF_PLACE)
    assert str(stray) in found and found[str(stray)].kind == "folder"
    assert str(loose) in found
    assert str(world["data"] / "append_only" / "brca" / "01_align") not in found


def test_world_writable_files_are_referred_to_the_security_guard(world):
    p = project(world)
    f = write(world["data"] / "append_only" / "brca" / "01_align" / "open.txt", text="x")
    os.chmod(f, 0o666)
    rows = by(scan(p, checksums=False), st.ACCESS)
    [row] = rows.values()
    assert row.suggestion == st.REFER_SECURITY and row.n_files == 1


def test_a_large_file_of_an_unknown_type_is_a_gap_in_the_procedures(world):
    p = project(world)
    write(world["data"] / "append_only" / "brca" / "01_align" / "model.weird", 2 * MB)
    gaps = [g for g in scan(p, checksums=False).sop_gaps if g.kind == "file type"]
    assert gaps and ".weird" in gaps[0].detail and gaps[0].count == 1


def test_the_scan_changes_nothing(world):
    p = project(world)
    write(world["repos"] / "brca" / "nohup.out", text="x", age_days=30)
    write(world["data"] / "append_only" / "brca" / "01_align" / "r.fastq", 2 * MB)
    before = {str(f): (f.stat().st_mtime, f.read_bytes())
              for f in world["data"].rglob("*") if f.is_file()}
    scan(p)
    after = {str(f): (f.stat().st_mtime, f.read_bytes())
             for f in world["data"].rglob("*") if f.is_file()}
    assert before == after


# ---------------------------------------------------------------------------
# 2. Intermediate files, from job cards
# ---------------------------------------------------------------------------


def _job(world, out: Path, *, inputs: list[str], script: Path, hours: float = 1.0,
         cores: int = 1) -> cards.JobCard:
    end = dt.datetime.now().astimezone() - dt.timedelta(minutes=5)
    start = end - dt.timedelta(hours=hours)
    card = cards.JobCard(
        id=cards.new_job_id(start), name="align", user=ME, host=cards.this_host(),
        command=["python", str(script)], workdir=str(script.parent), log="/tmp/l",
        watch="/tmp/l", out=str(out), inputs=inputs, project="brca", cores=cores,
        state=cards.STATE_FINISHED, exit_code=0, started_at=cards.to_iso(start),
        ended_at=cards.to_iso(end), created_at=cards.to_iso(start))
    cards.write_card(card)
    then = (start + dt.timedelta(minutes=10)).timestamp()
    for f in out.rglob("*"):
        os.utime(f, (then, then))
    return card


def _committed_script(world) -> Path:
    repo = world["repos"] / "brca"
    script = write(repo / "exp" / "01_align" / "align.py", text="print('hi')\n")
    commit(repo, "exp/01_align/align.py", when="2026-01-01T00:00:00")
    return script


def test_cheap_output_from_committed_code_and_existing_inputs_is_suggested_for_deletion(world):
    p = project(world)
    script = _committed_script(world)
    raw = write(world["data"] / "immutable" / "brca" / "reads.fq.gz", text="@r\n")
    out = world["data"] / "append_only" / "brca" / "01_align"
    write(out / "aligned.bam", text="bam")
    _job(world, out, inputs=[str(raw)], script=script, hours=2, cores=2)

    row = by(scan(p, checksums=False), st.INTERMEDIATE)[str(out)]
    assert row.suggestion == st.DELETE and row.cost_cpu_hours == pytest.approx(4, abs=0.1)
    assert "committed" in row.evidence and "inputs still exist" in row.evidence


@pytest.mark.parametrize("problem,expect", [
    ("no_inputs", "did not record its inputs"),
    ("missing_input", "no longer exist"),
    ("expensive", "CPU hours"),
    ("uncommitted", "not committed"),
])
def test_any_doubt_makes_an_intermediate_ask_the_owner(world, problem, expect):
    p = project(world)
    if problem == "uncommitted":
        script = write(world["repos"] / "brca" / "exp" / "01_align" / "align.py", text="x\n")
    else:
        script = _committed_script(world)
    raw = write(world["data"] / "immutable" / "brca" / "reads.fq.gz", text="@r\n")
    out = world["data"] / "append_only" / "brca" / "01_align"
    write(out / "aligned.bam", text="bam")
    inputs = {"no_inputs": [], "missing_input": [str(raw) + ".gone"]}.get(problem, [str(raw)])
    _job(world, out, inputs=inputs, script=script,
         hours=20 if problem == "expensive" else 1)

    row = by(scan(p, checksums=False), st.INTERMEDIATE)[str(out)]
    assert row.suggestion == st.ASK_OWNER and expect in row.reason


def test_files_in_the_output_folder_the_job_did_not_write_make_it_ask(world):
    p = project(world)
    script = _committed_script(world)
    raw = write(world["data"] / "immutable" / "brca" / "reads.fq.gz", text="@r\n")
    out = world["data"] / "append_only" / "brca" / "01_align"
    write(out / "aligned.bam", text="bam")
    _job(world, out, inputs=[str(raw)], script=script)
    write(out / "notes_added_later.txt", text="mine")

    row = by(scan(p, checksums=False), st.INTERMEDIATE)[str(out)]
    assert row.suggestion == st.ASK_OWNER and "did not write" in row.reason
    assert row.n_files == 1


# ---------------------------------------------------------------------------
# 3. When data last changed, for step 0
# ---------------------------------------------------------------------------


def test_the_scan_records_when_data_folders_changed_and_step_0_reads_it(world):
    p = project(world)
    write(world["data"] / "append_only" / "brca" / "01_align" / "a.txt", text="a", age_days=40)
    scan(p, checksums=False)
    record = json.loads(pu.data_dates_path().read_text())
    assert record["schema"] == pu.DATA_DATES_SCHEMA
    key = str(world["data"] / "append_only" / "brca" / "01_align")
    assert key in record["folders"] and "scanned_at" in record["folders"][key]
    [evidence] = pu.data_change_evidence(p)
    assert evidence.source == "data"
    days = (dt.datetime.now(dt.timezone.utc) - evidence.when).days
    assert 39 <= days <= 41


def test_data_dates_from_other_projects_are_kept(world):
    pu.data_dates_path().parent.mkdir(parents=True, exist_ok=True)
    pu.data_dates_path().write_text(json.dumps(
        {"schema": 1, "folders": {"/elsewhere/x": {"newest_change": "2020-01-01T00:00:00+00:00",
                                                   "scanned_at": "2020-01-02T00:00:00+00:00"}}}))
    p = project(world)
    write(world["data"] / "append_only" / "brca" / "01_align" / "a.txt", text="a")
    scan(p, checksums=False)
    folders = json.loads(pu.data_dates_path().read_text())["folders"]
    assert "/elsewhere/x" in folders and len(folders) > 1


# ---------------------------------------------------------------------------
# 4. The table
# ---------------------------------------------------------------------------


def _summary(*items: st.Item, disks: dict | None = None) -> st.ScanSummary:
    return st.ScanSummary(project="brca", started_at=st.now_iso(), finished_at=st.now_iso(),
                          items=list(items), disks=disks or {})


def test_the_table_is_private(world):
    st.connect().close()
    assert oct(st.table_path().stat().st_mode & 0o777) == "0o600"
    assert oct(st.table_path().parent.stat().st_mode & 0o777) == "0o700"


def test_a_rescan_keeps_decisions_and_drops_undecided_rows_that_are_gone(world):
    conn = st.connect()
    a = st.Item(path="/x/a", category=st.TEMPORARY, suggestion=st.DELETE, reason="r", size=10)
    b = st.Item(path="/x/b", category=st.TEMPORARY, suggestion=st.DELETE, reason="r", size=20)
    st.record_scan(conn, _summary(a, b))
    row_a = next(r for r in st.rows(conn, "brca") if r["path"] == "/x/a")
    st.decide(conn, row_a["id"], "keep", by="tester", note="needed for the paper")

    a.size = 15
    st.record_scan(conn, _summary(a))
    kept = st.get_row(conn, row_a["id"])
    assert kept["decision"] == "keep" and kept["decision_note"] == "needed for the paper"
    assert kept["previous_size"] == 10 and kept["size"] == 15
    assert [r["path"] for r in st.rows(conn, "brca", include_settled=True)] == ["/x/a"]

    st.record_scan(conn, _summary())
    assert st.get_row(conn, row_a["id"])["gone"] == 1


def test_decisions_are_checked_and_can_be_undone(world):
    conn = st.connect()
    st.record_scan(conn, _summary(st.Item(path="/x/a", category=st.DUPLICATE,
                                          suggestion=st.DELETE, reason="r")))
    row = st.rows(conn, "brca")[0]
    with pytest.raises(st.DecisionError):
        st.decide(conn, row["id"], "burn it", by="tester")
    with pytest.raises(st.DecisionError):
        st.decide(conn, 9999, "keep", by="tester")
    st.decide(conn, row["id"], "delete", by="tester")
    assert st.rows(conn, "brca") == []
    st.decide(conn, row["id"], "undo", by="tester")
    assert st.get_row(conn, row["id"])["decision"] is None


def test_the_biggest_comes_first_and_a_full_disk_raises_the_stakes(world):
    conn = st.connect()
    disks = {"full": st.Disk(label="/full", total=100 * 10**9, free=2 * 10**9),
             "empty": st.Disk(label="/empty", total=100 * 10**9, free=90 * 10**9)}
    st.record_scan(conn, _summary(
        st.Item(path="/empty/big", category=st.DUPLICATE, suggestion=st.DELETE, reason="r",
                size=3 * 10**9, disk="empty"),
        st.Item(path="/full/medium", category=st.DUPLICATE, suggestion=st.DELETE, reason="r",
                size=2 * 10**9, disk="full"),
        st.Item(path="/empty/small", category=st.DUPLICATE, suggestion=st.DELETE, reason="r",
                size=1 * 10**9, disk="empty"),
        st.Item(path="/empty/kept", category=st.DUPLICATE, suggestion=st.KEEP, reason="r",
                size=50 * 10**9, disk="empty"),
        disks=disks))
    order = [r["path"] for _s, r in st.ranked(conn, "brca")]
    assert order == ["/full/medium", "/empty/big", "/empty/small"]

    found = st.emergencies(conn, "brca", disk_fill_limit=0.9, item_share_of_free=0.25)
    texts = " ".join(e.text for e in found)
    assert "/full is 98% full" in texts
    assert any(e.item_id for e in found)          # /full/medium is all of its disk's free space


# ---------------------------------------------------------------------------
# 5. The commands
# ---------------------------------------------------------------------------


def test_scan_show_decide_and_gaps_from_the_command_line(world):
    project(world)
    write(world["repos"] / "brca" / "nohup.out", text="x", age_days=30)
    write(world["data"] / "append_only" / "brca" / "01_align" / "r.fastq", 2 * MB)
    write(world["data"] / "append_only" / "brca" / "01_align" / "m.weird", 2 * MB, seed=2)
    runner = CliRunner()

    out = runner.invoke(cli, ["space", "scan", "brca"])
    assert out.exit_code == 0, out.output
    assert "Look at these first" in out.output
    assert "Nothing was changed, moved or deleted." in out.output
    assert "procedures do not cover: 1" in out.output

    shown = runner.invoke(cli, ["space", "show", "brca", "--category", "compressible"])
    assert shown.exit_code == 0, shown.output
    assert "r.fastq" in shown.output and "nohup.out" not in shown.output
    row_id = st.rows(st.connect(), "brca", category="compressible")[0]["id"]

    decided = runner.invoke(cli, ["space", "decide", str(row_id), "compress", "--note", "ok"])
    assert decided.exit_code == 0 and "recorded 'compress'" in decided.output
    assert st.get_row(st.connect(), row_id)["decided_by"] == "tester"

    gaps = runner.invoke(cli, ["space", "gaps", "brca"])
    assert ".weird" in gaps.output


def test_show_before_any_scan_says_how_to_scan(world):
    project(world)
    out = CliRunner().invoke(cli, ["space", "show", "brca"])
    assert out.exit_code != 0 and "murmurent space scan brca" in out.output


def test_the_policy_reads_the_space_settings(world, tmp_path):
    policy = load_policy()
    assert policy.problems == ()
    assert (policy.large_file_in_repo_mb, policy.compress_min_mb) == (1, 1)
    bad = tmp_path / "bad.yaml"
    bad.write_text("disk_emergency_fill_fraction: 3\n")
    checked = load_policy({POLICY_ENV: str(bad), "MURMURENT_LAB_MGMT_REPO": "/nonexistent"})
    assert checked.disk_emergency_fill_fraction == 0.90 and checked.problems
